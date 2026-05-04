"""
app_pipeline.py
---------------
Pipeline chaining executor for PrepKit.

A pipeline is a list of step dicts:
  [
    {"template": "file_cast_types",  "params": {...}, "file1": "raw.csv",    "file2": ""},
    {"template": "file_aggregate",   "params": {...}, "file1": "__prev__",  "file2": ""},
    {"template": "file_rank_filter", "params": {...}, "file1": "__prev__",  "file2": ""},
  ]

"__prev__" as file1 or file2 means "use the output file of the previous step".
Each step generates its script, exec()s it in an isolated namespace, and calls preprocess().
The pipeline stops on the first failed step and reports the error.
"""
from __future__ import annotations

import inspect as _inspect
import tempfile
import traceback
from pathlib import Path

import pandas as pd

_PREV = "__prev__"   # sentinel meaning "previous step's output"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _exec_step(
    template_name: str,
    params_dict: dict,
    file1: str,
    file2: str,
    templates_dir: str,
    base_location: str,
) -> tuple[str | None, str]:
    """
    Generate + exec one pipeline step.

    Returns
    -------
    (output_path, "")        on success
    (None, error_message)    on failure
    """
    # Lazy imports from gradio_app to avoid circular dependency at module load
    from gradio_app import (
        _params_json_to_generator_format,
        _inject_filename_placeholders,
        _resolve_full_path,
        _friendly_error,
    )
    from preprocessing_library.generator import generate_preprocessor

    # 1. Build generator parameters
    try:
        gen_params = _params_json_to_generator_format(params_dict, template_name)
        gen_params = _inject_filename_placeholders(
            gen_params, template_name, file1, file2
        )
    except Exception as exc:
        return None, f"Parameter error: {_friendly_error(exc)}"

    # 2. Generate script content
    with tempfile.TemporaryDirectory() as tmp_gen:
        try:
            gpath = generate_preprocessor(
                template_name,
                gen_params,
                f"{template_name}_pipe.py",
                tmp_gen,
                templates_dir,
            )
            script_content = Path(gpath).read_text(encoding="utf-8")
        except Exception as exc:
            return None, f"Generation failed: {_friendly_error(exc)}"

    # 3. Execute script in isolated namespace
    ns: dict = {"__name__": "<pplib_pipe>"}
    try:
        exec(compile(script_content, f"{template_name}_pipe.py", "exec"), ns)
    except Exception as exc:
        return None, f"Script load error: {_friendly_error(exc)}"

    preprocess_fn = ns.get("preprocess")
    if not preprocess_fn:
        return None, "preprocess() function not found in generated script."

    # Redirect OUTPUT_DIR to a temp folder (avoid permission errors)
    if not (ns.get("OUTPUT_DIR") or "").strip():
        ns["OUTPUT_DIR"] = tempfile.mkdtemp(prefix="pplib_pipe_")

    # 4. Resolve input file paths
    base = (base_location or "").strip()
    f1 = _resolve_full_path(base, file1)
    f2 = _resolve_full_path(base, file2) if file2 else ""

    if not f1:
        return None, "No input file specified for this step."

    # 5. Inspect signature and call preprocess()
    sig_params = list(_inspect.signature(preprocess_fn).parameters.values())
    first_ann = str(sig_params[0].annotation) if sig_params else ""
    first_is_list = (
        "list" in first_ann.lower()
        or (sig_params and sig_params[0].name in ("input_paths", "paths"))
    )
    n_required = sum(
        1
        for p in sig_params
        if p.default is _inspect.Parameter.empty
        and p.kind
        not in (_inspect.Parameter.VAR_POSITIONAL, _inspect.Parameter.VAR_KEYWORD)
    )

    try:
        if n_required == 1 and first_is_list:
            path_list = [f1, f2] if f2 else [f1]
            result = preprocess_fn(path_list)
        elif n_required >= 2:
            if not f2:
                return None, "This step requires 2 input files — File 2 is missing."
            result = preprocess_fn(f1, f2)
        else:
            result = preprocess_fn(f1)
    except Exception as exc:
        return None, f"preprocess() failed:\n{traceback.format_exc(limit=8)}"

    return str(result), ""


def _collect_first_output(result_path: str) -> tuple[str, int, int, pd.DataFrame]:
    """
    Given the return value of preprocess() (a file or folder path),
    find the first output file and return (path, nrows, ncols, preview_df).
    """
    from gradio_app import _sniff_load, _count_rows_fast

    p = Path(result_path)
    if p.is_file():
        out_files = [p]
    elif p.is_dir():
        out_files = sorted(
            f for f in p.iterdir()
            if f.is_file() and not f.name.startswith(".")
        )
    else:
        out_files = []

    if not out_files:
        return result_path, 0, 0, pd.DataFrame()

    first = out_files[0]
    preview_df = _sniff_load(str(first), max_rows=10)
    nrows = _count_rows_fast(str(first), preview_df)
    ncols = len(preview_df.columns)
    return str(first), max(0, nrows), ncols, preview_df


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_pipeline(
    steps: list[dict],
    base_location: str,
    templates_dir: str,
) -> list[dict]:
    """
    Execute all steps in sequence, wiring __prev__ between steps.

    Each step dict must have:
        template  (str)   — template key e.g. 'file_cast_types'
        params    (dict)  — parameter dict
        file1     (str)   — filename or '__prev__'
        file2     (str)   — filename, '__prev__', or ''

    Returns a list of result dicts (one per step):
        step_index    int
        template_name str
        status        'ok' | 'error'
        output_path   str | None
        first_file    str | None   (first output file, for __prev__ wiring)
        error         str
        rows          int
        cols          int
        preview_df    pd.DataFrame
    """
    results: list[dict] = []
    prev_output: str | None = None   # path to first file of previous step

    for i, step in enumerate(steps):
        template_name = step.get("template", "")
        params = step.get("params", {})
        file1 = step.get("file1", "")
        file2 = step.get("file2", "")

        # Substitute __prev__ sentinel
        if file1 == _PREV:
            if prev_output is None:
                results.append({
                    "step_index": i, "template_name": template_name,
                    "status": "error", "output_path": None, "first_file": None,
                    "error": "No previous step output available — this is the first step.",
                    "rows": 0, "cols": 0, "preview_df": pd.DataFrame(),
                })
                break
            file1 = prev_output

        if file2 == _PREV:
            file2 = prev_output or ""

        # Execute step
        output_path, error = _exec_step(
            template_name, params, file1, file2, templates_dir, base_location
        )

        if error:
            results.append({
                "step_index": i, "template_name": template_name,
                "status": "error", "output_path": None, "first_file": None,
                "error": error,
                "rows": 0, "cols": 0, "preview_df": pd.DataFrame(),
            })
            break   # pipeline stops on first failure

        # Collect stats on output and locate first file for __prev__ wiring
        first_file, nrows, ncols, preview_df = _collect_first_output(output_path)
        prev_output = first_file

        results.append({
            "step_index": i, "template_name": template_name,
            "status": "ok", "output_path": output_path, "first_file": first_file,
            "error": "",
            "rows": nrows, "cols": ncols, "preview_df": preview_df,
        })

    return results


def pipeline_summary_html(results: list[dict]) -> str:
    """Render a pipeline run summary as HTML for display in the UI."""
    if not results:
        return "<p style='color:gray'>No pipeline steps have been run yet.</p>"

    rows = ""
    for r in results:
        icon = "✅" if r["status"] == "ok" else "❌"
        step_n = r["step_index"] + 1
        tname = r["template_name"]
        if r["status"] == "ok":
            detail = (
                f"<span style='color:#27ae60'>{r['rows']:,} rows × {r['cols']} cols</span>"
                f" → <code style='font-size:0.83em'>{r['first_file'] or r['output_path']}</code>"
            )
        else:
            detail = f"<span style='color:#c0392b'>{r['error'][:200]}</span>"

        rows += (
            f"<tr style='vertical-align:top'>"
            f"<td style='padding:6px 10px;font-size:1.1em'>{icon}</td>"
            f"<td style='padding:6px 10px;font-weight:600'>Step {step_n}</td>"
            f"<td style='padding:6px 10px;font-family:monospace;color:#1a6e9e'>{tname}</td>"
            f"<td style='padding:6px 10px'>{detail}</td>"
            f"</tr>"
        )

    all_ok = all(r["status"] == "ok" for r in results)
    header_color = "#27ae60" if all_ok else "#e67e22"
    header_text = "Pipeline complete ✓" if all_ok else "Pipeline stopped — see error above"

    return (
        f"<div style='padding:8px 14px;background:#f8f9fa;"
        f"border-left:4px solid {header_color};border-radius:4px;margin-bottom:10px'>"
        f"<b style='color:{header_color}'>{header_text}</b> &nbsp;|&nbsp; "
        f"{len(results)} step(s) executed"
        f"</div>"
        f"<table style='border-collapse:collapse;width:100%;font-size:0.9em'>"
        f"<thead><tr style='background:#f0f0f0'>"
        f"<th style='padding:5px 10px'></th>"
        f"<th style='padding:5px 10px;text-align:left'>Step</th>"
        f"<th style='padding:5px 10px;text-align:left'>Template</th>"
        f"<th style='padding:5px 10px;text-align:left'>Result</th>"
        f"</tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )
