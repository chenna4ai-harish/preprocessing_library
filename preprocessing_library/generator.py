"""
Data Preprocessing Script Library — Core Generator
====================================================
Single public function: generate_preprocessor()

How it works
------------
1. Reads the template file  (templates/{template_name}_template.py)
2. Finds every {{PLACEHOLDER}} token in the file
3. Validates that all placeholders are covered by *parameters*
4. Replaces every {{PLACEHOLDER}} with its value from *parameters*
5. Writes the resulting Python script to *output_dir*
6. Returns the absolute path to the generated script

No LLM or external API is involved — pure string substitution.
"""
from __future__ import annotations

import re
import warnings
from datetime import datetime
from pathlib import Path

try:
    # When imported as a package: `from preprocessing_library.generator import ...`
    from .exceptions import (
        ExtraParameterWarning,
        MissingParameterError,
        OutputWriteError,
        TemplateNotFoundError,
    )
except ImportError:  # pragma: no cover
    # When run as a script from within the folder: `python generator.py`
    from exceptions import (  # type: ignore
        ExtraParameterWarning,
        MissingParameterError,
        OutputWriteError,
        TemplateNotFoundError,
    )


_DEFAULT_TEMPLATES_DIR = Path("./templates")
_DEFAULT_OUTPUT_DIR = Path("./generated_scripts")


def _module_dir() -> Path:
    return Path(__file__).resolve().parent


def _resolve_templates_dir(templates_dir: str) -> Path:
    """
    Resolve templates_dir robustly:
    - if it exists relative to CWD, use it
    - otherwise, if it matches the default, resolve relative to this module
    """
    p = Path(templates_dir)
    if p.is_dir():
        return p
    if p == _DEFAULT_TEMPLATES_DIR:
        candidate = (_module_dir() / p).resolve()
        if candidate.is_dir():
            return candidate
    return p


def _resolve_output_dir(output_dir: str) -> Path:
    """
    Resolve output_dir robustly:
    - if caller uses the default, write next to this module (preprocessing_library/generated_scripts)
    - otherwise, respect the caller's path (relative to CWD or absolute)
    """
    p = Path(output_dir)
    if p == _DEFAULT_OUTPUT_DIR:
        return (_module_dir() / p).resolve()
    return p

# Matches every {{PLACEHOLDER_NAME}} token (UPPERCASE + underscores)
_PLACEHOLDER_RE = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")


# ── Public API ────────────────────────────────────────────────────────────────

def generate_preprocessor(
    template_name: str,
    parameters: dict,
    output_script_name: str | None = None,
    output_dir: str = "./generated_scripts",
    templates_dir: str = "./templates",
) -> str:
    """
    Read a preprocessing template, substitute all {{PLACEHOLDERS}}, and write
    the generated Python script to *output_dir*.

    Parameters
    ----------
    template_name : str
        Template identifier, e.g. ``'file_split_by_value'``.
        The generator looks for ``{templates_dir}/{template_name}_template.py``.

    parameters : dict
        Key-value pairs whose keys match the UPPERCASE placeholder names found
        in the template.  Values are converted to ``str`` before substitution.

        Example::

            {
                "JOIN_KEY":        "Account_Number",
                "JOIN_TYPE":       "inner",
                "OUTPUT_DIR":      "./output",
                "OUTPUT_FILENAME": "joined.csv",
                "OUTPUT_FORMAT":   "csv",
            }

    output_script_name : str, optional
        Filename for the generated ``.py`` script.
        If omitted, defaults to ``{template_name}_{YYYYMMDD_HHMMSS}.py``.

    output_dir : str
        Destination folder.  Created automatically if it does not exist.
        Defaults to ``"./generated_scripts"``.

    templates_dir : str
        Folder containing the ``*_template.py`` source files.
        Defaults to ``"./templates"``.

    Returns
    -------
    str
        Absolute path to the generated Python script.

    Raises
    ------
    TemplateNotFoundError
        Template file not found in *templates_dir*.
    MissingParameterError
        A ``{{PLACEHOLDER}}`` in the template has no matching key in
        *parameters*.
    OutputWriteError
        Generated script could not be written to *output_dir*.

    Warns
    -----
    ExtraParameterWarning
        A key in *parameters* has no matching ``{{PLACEHOLDER}}`` in the
        template.  Generation continues normally; the extra key is ignored.

    Examples
    --------
    >>> path = generate_preprocessor(
    ...     template_name="file_join_two",
    ...     parameters={
    ...         "JOIN_KEY":        "Account_Number",
    ...         "JOIN_TYPE":       "inner",
    ...         "LEFT_SUFFIX":     "_cust",
    ...         "RIGHT_SUFFIX":    "_inv",
    ...         "OUTPUT_DIR":      "./output",
    ...         "OUTPUT_FILENAME": "customer_invoice_joined.csv",
    ...         "OUTPUT_FORMAT":   "csv",
    ...     },
    ...     output_script_name="cust_inv_join.py",
    ... )
    >>> print(path)
    /absolute/path/to/generated_scripts/cust_inv_join.py
    """
    # ── 1. Locate template ────────────────────────────────────────────────────
    templates_dir_path = _resolve_templates_dir(templates_dir)
    template_path = templates_dir_path / f"{template_name}_template.py"
    if not template_path.is_file():
        available = _list_templates(str(templates_dir_path))
        raise TemplateNotFoundError(
            f"Template '{template_name}' not found.\n"
            f"Expected : {template_path.resolve()}\n"
            f"Available: {available if available else '(none — check templates_dir)'}"
        )

    # ── 2. Read template ──────────────────────────────────────────────────────
    content = template_path.read_text(encoding="utf-8")

    # ── 3. Discover placeholders ──────────────────────────────────────────────
    found_placeholders = set(_PLACEHOLDER_RE.findall(content))
    provided_keys = set(parameters.keys())

    # ── 4. Validate coverage ──────────────────────────────────────────────────
    missing = found_placeholders - provided_keys
    if missing:
        raise MissingParameterError(
            f"Template '{template_name}' requires parameters not provided: "
            f"{sorted(missing)}"
        )

    extra = provided_keys - found_placeholders
    if extra:
        warnings.warn(
            f"Parameters have no matching placeholder in template "
            f"'{template_name}': {sorted(extra)}",
            ExtraParameterWarning,
            stacklevel=2,
        )

    # ── 5. Substitute placeholders ────────────────────────────────────────────
    for key, value in parameters.items():
        placeholder = f"{{{{{key}}}}}"
        str_val = str(value)
        # If the placeholder appears inside quotes in the template, escape
        # backslashes so Windows paths don't produce a SyntaxError in the
        # generated script (e.g. "C:\Users\..." → "C:\\Users\\...").
        if f'"{placeholder}"' in content or f"'{placeholder}'" in content:
            str_val = str_val.replace("\\", "\\\\")
        content = content.replace(placeholder, str_val)

    # ── 6. Resolve output filename ────────────────────────────────────────────
    if output_script_name is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_script_name = f"{template_name}_{ts}.py"
    elif not output_script_name.endswith(".py"):
        output_script_name += ".py"

    # ── 7. Write generated script ─────────────────────────────────────────────
    out_dir = _resolve_output_dir(output_dir)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OutputWriteError(
            f"Cannot create output directory '{out_dir}': {exc}"
        ) from exc

    out_path = out_dir / output_script_name
    try:
        out_path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise OutputWriteError(
            f"Could not write generated script to '{out_path}': {exc}"
        ) from exc

    return str(out_path.resolve())


# ── Helpers ───────────────────────────────────────────────────────────────────

def _list_templates(templates_dir: str) -> list[str]:
    """Return sorted list of available template names (without _template suffix)."""
    d = Path(templates_dir)
    if not d.is_dir():
        return []
    return sorted(
        p.stem.removesuffix("_template")
        for p in d.glob("*_template.py")
    )


def list_templates(templates_dir: str = "./templates") -> list[str]:
    """Public helper — print or inspect available template names."""
    templates_dir_path = _resolve_templates_dir(templates_dir)
    return _list_templates(str(templates_dir_path))
