# Data Preprocessing Library — Fix Plan & Requirements

---

## The 4 Issues — What They Are

### Issue 1 — str→list guard (multi-input templates)

**Problem**
`preprocess(input_paths: list)` crashes when a caller passes a single string
instead of a list.

**Requirement**
Every multi-input template must silently accept either form:
```python
preprocess("path/to/file.csv")          # string → normalise to list
preprocess(["path/to/file.csv"])        # list   → use as-is
```

**Fix**
```python
if isinstance(input_paths, str):
    input_paths = [input_paths]
```

**Templates (7):** union, join_two, join_multi, join_multi_key,
denormalize, delta_load, join_filter_agg

**Status:** ✅ Done

---

### Issue 2 — Multi-output templates return dir string instead of file list

**Problem**
Templates that write multiple files were returning `os.path.abspath(_out_dir)`
— a single directory string — not a list of the actual files written.

**Requirement**
Every `preprocess()` must return a `list` of absolute paths to every file it
wrote. Callers must be able to iterate the list to know exactly what was produced.

**Fix**
```python
output_paths: list = []
output_paths.append(_write_output(...))   # inside each write call
return output_paths                        # not the dir string
```

Also add the reverse guard for single-input templates called with a list:
```python
if isinstance(input_path, list):
    input_path = input_path[0]
```

**Templates (4):** split_by_value, filter_to_files, split_columns,
filter_by_values

**Status:** ✅ Done

---

### Issue 3 — ZIP expansion for multi-input templates (`_expand_zip_inputs`)

**Problem & Scenario**
A user bundles both input files (e.g. `left.csv` + `right.csv`) into ONE zip
and passes `["data.zip"]`. Multi-input templates need two named files and
`_find_input_file()` cannot find them inside the zip.

**Requirement**
When any path in `input_paths` is a `.zip`, expand it so all its contents
become individually addressable paths. The template's join/merge logic then
runs as normal using `_find_input_file()` to pick LEFT and RIGHT by filename.

**Key point — what this does NOT do**
`_expand_zip_inputs` does NOT process each file in the zip separately.
It only exposes the files so the template can find the two it needs.
The output is still ONE merged/joined file.

**Fix — `_expand_zip_inputs` helper**
```python
def _expand_zip_inputs(input_paths):
    tmp = TemporaryDirectory()
    expanded = []
    for p in input_paths:
        if p is a .zip:
            extract ALL supported files → tmp.name
            append each extracted path to expanded
        else:
            append p as-is
    return expanded, tmp          # caller must call tmp.cleanup()
```

Wired in `preprocess()`:
```python
_tmp = None
if any(p.endswith(".zip") for p in input_paths):
    input_paths, _tmp = _expand_zip_inputs(input_paths)
# ... join logic using _find_input_file() ...
if _tmp is not None:
    _tmp.cleanup()
return [_write_output(...)]       # ONE output file
```

**Templates (6):** join_two, join_multi_key, denormalize, delta_load,
join_filter_agg, union

**Status:** ✅ Done

---

### Issue 4 — All templates return `str` instead of `list`

**Problem**
Single-output templates return `_write_output(...)` which is a `str`.
Downstream code expects every `preprocess()` to return a `list`.

**Requirement**
Unified contract: every `preprocess()` → `list`, always, no exceptions.
Single-output → `[one_path]`. Multi-output → `[path1, path2, ...]`.

**Fix**
```python
return [_write_output(result, out_path, OUTPUT_FORMAT)]
```
Signature: `def preprocess(...) -> list:`

**Templates:** all 18 base templates

**Status:** ✅ Done

---

## ZIP Requirement — What Was Being Communicated From The Beginning

### The Reference: `Zsample.py`

`Zsample.py` is a hand-written example that shows the correct ZIP behaviour.
Reading it reveals the exact requirement:

```
ZIP contains:
  filings.txt           → extract to TEMP  (used as processing input, NOT in output)
  filingamendments.txt  → extract to OUTPUT DIR (pass-through + used in merge) → in output list
  other files           → extract to OUTPUT DIR (pure pass-through)             → in output list
  filings_processed.txt → created by merge logic                                → in output list

Output list = [filingamendments.txt, other_files..., filings_processed.txt]
```

**Pattern extracted from `Zsample.py`:**
1. Open ZIP, iterate ALL members
2. Extract every supported file
3. Files used purely as processing input → go to TEMP (not in output)
4. Files that are pass-through (not further processed) → go to OUTPUT DIR → added to output list
5. Files produced by the template's logic → added to output list
6. Return the combined list

---

### Mapping the Pattern to Multi-Output Templates

**`file_split_by_value` — example with `test_batch.zip`:**

```
ZIP contains:
  customers.csv   (has "Country Code" col)
  invoices.csv    (no "Country Code" col)

customers.csv  → HAS SPLIT_COLUMN
                 → used as processing INPUT (not copied to output as-is)
                 → split logic produces: customers_GB.csv, customers_US.csv
                 → BOTH split files → output list

invoices.csv   → NO SPLIT_COLUMN
                 → pass-through: written as-is to OUTPUT_DIR
                 → invoices.csv → output list

Final output = [customers_GB.csv, customers_US.csv, invoices.csv]
```

**Same pattern for the other 3 templates:**

| Template | File HAS relevant column | File DOES NOT have column |
|---|---|---|
| `file_split_by_value` | split by SPLIT_COLUMN values → N files | write as-is → 1 file |
| `file_filter_to_files` | apply FILTER_RULES conditions → N files | write as-is → 1 file |
| `file_split_columns` | split into COLUMN_GROUPS subsets → N files | write as-is → 1 file |
| `file_filter_by_values` | route by VALUE_GROUPS → N files | write as-is → 1 file |

---

### How `_expand_zip_inputs` Differs From This ZIP Requirement

| | `_expand_zip_inputs` | ZIP loop (user requirement) |
|---|---|---|
| **Template type** | Multi-input JOIN/MERGE templates | Single-input SPLIT/FILTER templates |
| **Why ZIP is used** | User bundles BOTH input files in one ZIP | User provides a ZIP with multiple data files |
| **What happens to each file** | Just exposed as a path so `_find_input_file()` can locate LEFT/RIGHT | Each file is loaded as a DataFrame and processed |
| **Output count** | ONE merged/joined output file | MANY output files (one set per input file in ZIP) |
| **Files not relevant to template** | N/A — all files are candidates for LEFT/RIGHT matching | Written as-is to output dir |
| **Temp dir** | Returned to caller, explicitly cleaned up with `_tmp.cleanup()` | Used inside `with` block, auto-cleaned |

---

## Implementation Approach — Multi-Output ZIP Pattern

All 4 multi-output templates will use the same structure:

### Step 1 — Extract `_process_one_file()` helper

Move the core per-file logic out of `preprocess()` into a helper:

```python
def _process_one_file(df: pd.DataFrame, src_basename: str, out_dir: str) -> list:
    """
    Apply template logic to one DataFrame.
    If the relevant column is absent, write the file as-is (pass-through).
    Returns list of output paths written.
    """
    paths: list = []

    if RELEVANT_COLUMN not in df.columns:
        # Pass-through: write as-is using the source filename
        stem = Path(src_basename).stem
        out_path = os.path.join(out_dir, f"{stem}.{OUTPUT_FORMAT.lower()}")
        paths.append(_write_output(df, out_path, OUTPUT_FORMAT))
        return paths

    # ... template's normal logic here ...
    # paths.append(_write_output(...)) for each output produced
    return paths
```

### Step 2 — Restructure `preprocess()` to loop over ZIP contents

```python
def preprocess(input_path: str) -> list:
    if isinstance(input_path, list):
        input_path = input_path[0]

    _out_dir = OUTPUT_DIR or dirname(input_path)
    os.makedirs(_out_dir, exist_ok=True)
    output_paths: list = []

    # ── ZIP input: extract ALL files, process each ────────────────────────
    if _Path(input_path).suffix.lower() == ".zip":
        _supported = {".csv", ".tsv", ".txt", ".xlsx", ".xls", ".json", ".xml"}
        with _tempfile.TemporaryDirectory() as tmp_dir:
            with _zipfile.ZipFile(input_path, "r") as z:
                names = [n for n in z.namelist()
                         if _Path(n).suffix.lower() in _supported]
                for name in names:
                    z.extract(name, tmp_dir)
            for name in names:                              # process AFTER zip closed
                df = _load_file(os.path.join(tmp_dir, name))
                output_paths.extend(
                    _process_one_file(df, os.path.basename(name), _out_dir)
                )
        return output_paths

    # ── Single file input: existing behaviour ─────────────────────────────
    df = _load_file(input_path)
    output_paths.extend(_process_one_file(df, os.path.basename(input_path), _out_dir))
    return output_paths
```

### Why the loop runs AFTER `with _zipfile.ZipFile` closes

Files extracted to `tmp_dir` persist inside the `with _tempfile.TemporaryDirectory()`
block. Loading them after the zip is closed (but before tmp_dir is cleaned up)
is safe and avoids holding the zip file handle open during DataFrame loading.

---

## Status Summary

| Fix | Requirement | Status |
|---|---|---|
| Issue 1 — str→list guard | 7 multi-input templates | ✅ Done |
| Issue 2 — multi-output returns list | 4 split/filter templates | ✅ Done |
| Issue 3 — `_expand_zip_inputs` | 6 join/merge templates | ✅ Done |
| Issue 4 — all return `list` | all 18 templates | ✅ Done |
| ZIP requirement — `_process_one_file` + ZIP loop | `file_split_by_value` | ✅ Done |
| ZIP requirement — `_process_one_file` + ZIP loop | `file_filter_to_files` | ✅ Done |
| ZIP requirement — `_process_one_file` + ZIP loop | `file_split_columns` | ✅ Done |
| ZIP requirement — `_process_one_file` + ZIP loop | `file_filter_by_values` | ✅ Done |

---

## What Happens to `_load_zip` After This Change

For the 4 multi-output templates, `_load_zip` is no longer called from
`preprocess()` when the input is a ZIP — the ZIP loop in `preprocess()` handles
extraction directly and calls `_load_file()` on each already-extracted file.

`_load_zip` is still needed for the case where a single non-zip input path is
given and one of the files referenced inside it is itself a zip (nested case).
It remains unchanged.
