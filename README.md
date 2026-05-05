# PrepKit

**Generate ready-to-run Python data preprocessing scripts from a no-code UI.**

PrepKit is a Gradio-based desktop/web app that turns your file preprocessing configuration into a self-contained, portable `.py` script — no boilerplate, no runtime dependencies beyond `pandas`. Pick a template, set your parameters, click **Generate Script** or **Run Script** directly.

---

## Features

- **18 preprocessing templates** covering joins, filters, aggregations, deduplication, type casting, delta loads, and more
- **No-code UI** — configure via dropdowns and JSON parameters, no coding required
- **Self-contained generated scripts** — each `.py` file embeds its own file loader, runs standalone
- **Folder-based workflow** — scan a folder, explore columns, generate scripts, run and preview output
- **Output lands next to your input** — no hardcoded paths; `OUTPUT_DIR = ""` means same folder as input
- **Multi-format support** — reads CSV, TSV, XLSX, XLS, JSON, XML, HTML, ZIP; writes CSV, TSV, XLSX, JSON, Parquet
- **Auto encoding detection** — tries UTF-8 → cp1252 → latin-1 on text files
- **WHERE condition** — optional pandas `query()` pre-filter applied before any template logic

---

## Quick Start

```bash
# 0. (Recommended) Create a virtual environment
python -m venv .venv

# 1. Install dependencies
.venv\Scripts\python -m pip install -r requirements.txt

# 2. Launch the app
.venv\Scripts\python gradio_app.py
```

Open the URL printed in the terminal (default `http://127.0.0.1:7862`).

Optional flags:
- `python gradio_app.py --port 7860`
- `python gradio_app.py --host 0.0.0.0`
- `python gradio_app.py --share`

---

## How It Works

```
Scan Folder → Explore Columns → Configure Template → Generate Script → Run & Download
```

**Tab 1 — Explore Files**
- Enter a folder path and click **Scan Folder**
- Browse files, see all column names and a 10-row preview

**Tab 2 — Generate Script**
1. Column reference panel at the top — copy exact column names into parameters
2. Select a template and set parameters (JSON editor with inline help)
3. Pick input file(s) from the scanned folder
4. Optional WHERE condition to pre-filter rows
5. Click **Generate Script** to download a `.py` file, or **Run Script** to execute and preview output immediately

---

## Templates

| ID | Template | Purpose |
|----|----------|---------|
| PS-01 | Detect & Load | Auto-detect format, write clean output |
| PS-02 | File Union | Vertically stack multiple files, handle column mismatches |
| PS-03 | Join Two Files | Single-key join of two files |
| PS-04 | Join Multiple Files | Chain-join N files sequentially |
| PS-05 | Join Two Files (Multi-Key) | Composite-key join of two files |
| PS-06 | Denormalize | Flatten header + detail into one wide file |
| PS-07 | Split by Column Value | One output file per distinct value in a column |
| PS-08 | Filter Rows to Files | Route rows to named files via `query()` expressions |
| PS-09 | Split Columns to Files | Split a wide file into narrower column-group files |
| PS-10 | Deduplicate | Remove duplicate rows, report dropped rows |
| PS-11 | Rename Columns | Rename columns via a mapping dict |
| PS-12 | Handle Nulls | Audit and fill/drop nulls per column |
| PS-13 | Cast Column Types | Cast columns to str / int / float / date / bool |
| PS-14 | Aggregate / Group-By | Group-by with sum, count, mean, min, max, nunique, etc. |
| PS-15 | Delta Load | Compare new vs old file, tag rows NEW / CHANGED / DELETED |
| PS-16 | Rank & Filter | Rank within groups, keep top-N, optionally save discarded rows |
| PS-17 | Filter by Value List | Route rows to named files by value-list matching |
| PS-18 | Join, Filter & Aggregate | Join → WHERE filter → group-by aggregate → rank |

---

## Generated Script Structure

Every generated script is fully self-contained:

```python
# ── Configuration (all parameters hard-coded) ─────────────────────────────
JOIN_KEY        = "account_number"
JOIN_TYPE       = "inner"
LEFT_FILENAME   = "customers.csv"
RIGHT_FILENAME  = "invoices.csv"
OUTPUT_DIR      = ""          # empty = write next to input file
OUTPUT_FILENAME = "pp_customers_join_two.csv"
OUTPUT_FORMAT   = "csv"

# ── Embedded file loader (handles CSV/TSV/XLSX/JSON/XML/ZIP) ──────────────
def _load_file(file_path): ...

# ── Core logic ────────────────────────────────────────────────────────────
def preprocess(input_paths: list) -> str: ...

# ── Run block ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    result = preprocess(INPUT_FILES)
    print(f"Output: {result}")
```

Scripts can be run standalone (`python my_script.py`) or imported and called as a function (`preprocess(input_paths)`).

---

## Output File Naming

Default output filenames follow the convention:

```
pp_{master_file_stem}_{template_shortcut}.{format}
```

Examples:
- `customers.csv` + PS-03 Join Two Files → `pp_customers_join_two.csv`
- `invoices.csv` + PS-14 Aggregate → `pp_invoices_aggregate.csv`
- `orders.csv` + PS-15 Delta Load → `pp_orders_delta_load.csv`

---

## Input Format Support

| Format | Read | Write |
|--------|------|-------|
| CSV / TSV / TXT | ✓ auto-detect delimiter | ✓ |
| XLSX / XLS | ✓ | ✓ (xlsx only) |
| JSON | ✓ | ✓ |
| XML | ✓ | — |
| HTML table | ✓ | — |
| ZIP (containing any above) | ✓ | — |
| Parquet | — | ✓ |

Up to **10 files** per folder scan. Encoding fallback: UTF-8 → cp1252 → latin-1.

---

## Project Structure

```
.
├── gradio_app.py                  # Gradio UI + script generator/runner logic
├── app_history.py                  # SQLite-backed run history (prepkit_history.db)
├── app_pipeline.py                 # Multi-step pipeline runner (execs generated scripts)
├── app_profile.py                  # Column profiling stats for Tab 1
├── requirements.txt
├── tests/                          # Unit + end-to-end tests (unittest)
├── test_data/                     # Sample input files
├── preprocessing_library/
│   ├── __init__.py                # Exports generate_preprocessor()
│   ├── generator.py               # Template substitution engine
│   ├── exceptions.py              # Custom exceptions
│   └── templates/                 # Template .py files (placeholders: {{NAME}})
│       ├── file_detect_load_template.py
│       ├── file_union_template.py
│       ├── file_join_two_template.py
│       └── ... (PS-01..PS-18 + ZIP helpers)
```

---

## Requirements

- Python **3.10+** recommended.
- See `requirements.txt` for the **exact pinned versions** used for development.

---

## Running Tests

```bash
.venv\Scripts\python -m unittest discover -s tests -v
```

Includes unit tests for the generator plus end-to-end tests that generate + exec each template and validate outputs.

---

## Documentation

- `Preprocessing_Script_Library.md` — deeper technical reference (generator contract, placeholder syntax, template details).
- `DEVELOPMENT.md` — contributor/developer notes (tests, adding templates, troubleshooting).

---

## License

MIT
