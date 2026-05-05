# Development Guide

This repo is a Gradio app (`gradio_app.py`) plus a template-based code generator (`preprocessing_library/`) for producing standalone preprocessing scripts.

## Local Setup

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

Run the UI:

```bash
.venv\Scripts\python gradio_app.py
```

## Running Tests

Run all tests (unit + end-to-end):

```bash
.venv\Scripts\python -m unittest discover -s tests -v
```

## Adding or Updating a Template

1. Create/update the template file in `preprocessing_library/templates/`:
   - Naming: `{template_name}_template.py`
   - Placeholders: `{{PLACEHOLDER_NAME}}` (uppercase + underscores)
2. Add/update the UI entry in `gradio_app.py`:
   - `TEMPLATE_CATALOG[template_name]` drives display name, description, input type, and parameter help.
   - Keep `parameters[].name` exactly aligned with placeholders in the template file.
3. Run tests (`tests/test_all_templates.py`) and add a new test case if the template introduces new behavior.

### Placeholder Conventions

- **String placeholders**: put the placeholder inside quotes in the template, e.g. `OUTPUT_DIR = "{{OUTPUT_DIR}}"`.
- **Python-literal placeholders** (lists/dicts/ints/bools): do **not** quote, e.g. `JOIN_KEYS = {{JOIN_KEYS}}`.
- The generator escapes backslashes for placeholders that appear inside quotes to keep Windows paths valid in the generated script.

## Runtime Artifacts

- `preprocessing_library/generated_scripts/` is the default output directory for `generate_preprocessor()` when you don’t pass an explicit `output_dir`.
- `prepkit_history.db` is an auto-created SQLite database used by `app_history.py` to store UI run history. It can be deleted safely if you want to reset history.

## Troubleshooting

- **Port already in use**: run `python gradio_app.py --port 7860` (or any free port).
- **File write PermissionError**: close the file in Excel or any other program and retry.
- **Invalid JSON parameters**: validate the JSON (quotes/commas/brackets) before generating.
- **Column not found (KeyError)**: copy exact column names from Tab 1 into the parameters.
