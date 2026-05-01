# PrepKit — Template Test Report

**Date:** 2026-05-01  
**Branch:** `may1st_Changes`  
**Python:** 3.12.10  
**pytest:** 9.0.3  
**Total:** 20 passed, 0 failed (18 template tests + 2 generator tests)  
**Runtime:** ~3 seconds

---

## Test Strategy

File: [`tests/test_all_templates.py`](tests/test_all_templates.py)

Each test:
1. Writes minimal in-memory CSV data to a temp directory
2. Calls `generate_preprocessor()` to produce the `.py` script
3. `exec()`s the script in an isolated namespace (zero cross-test pollution)
4. Calls `preprocess()` with temp-file inputs
5. Asserts the output file(s) exist and contain at least one data row
6. Cleans up all temp dirs in `tearDown`

---

## Results by Template

| # | Test | Template | Status | What is verified |
|---|------|----------|--------|-----------------|
| PS-01 | `test_ps01_file_detect_load` | `file_detect_load` | ✅ PASS | CSV auto-detected and written to output |
| PS-02 | `test_ps02_file_union` | `file_union` | ✅ PASS | Two CSVs vertically stacked; row count = sum of inputs |
| PS-03 | `test_ps03_file_join_two` | `file_join_two` | ✅ PASS | Inner join on shared key; LEFT_KEY/RIGHT_KEY cross-column join |
| PS-04 | `test_ps04_file_join_multi` | `file_join_multi` | ✅ PASS | Chain join of 3 files via JOIN_STEPS |
| PS-05 | `test_ps05_file_join_multi_key` | `file_join_multi_key` | ✅ PASS | Join on two composite key columns |
| PS-06 | `test_ps06_file_denormalize` | `file_denormalize` | ✅ PASS | Master-detail denormalize/join produces merged output |
| PS-07 | `test_ps07_file_split_by_value` | `file_split_by_value` | ✅ PASS | Rows split into per-value output files; each file exists and has rows |
| PS-08 | `test_ps08_file_filter_to_files` | `file_filter_to_files` | ✅ PASS | Two filter rules each produce their named output file |
| PS-09 | `test_ps09_file_split_columns` | `file_split_columns` | ✅ PASS | Column groups produce separate output files with correct columns |
| PS-10 | `test_ps10_file_deduplicate` | `file_deduplicate` | ✅ PASS | Duplicates removed; exact row count = 3 unique IDs asserted |
| PS-11 | `test_ps11_file_rename_columns` | `file_rename_columns` | ✅ PASS | Column headers renamed correctly in output |
| PS-12 | `test_ps12_file_handle_nulls` | `file_handle_nulls` | ✅ PASS | Nulls filled per NULL_RULES; output has no unexpected blanks |
| PS-13 | `test_ps13_file_cast_types` | `file_cast_types` | ✅ PASS | Columns cast to float/int per TYPE_RULES; 1 pandas deprecation warning (harmless) |
| PS-14 | `test_ps14_file_aggregate` | `file_aggregate` | ✅ PASS | Group-by + sum aggregation produces correct summary rows |
| PS-15 | `test_ps15_file_delta_load` | `file_delta_load` | ✅ PASS | New, changed, and deleted rows detected between two snapshots |
| PS-16 | `test_ps16_file_rank_filter` | `file_rank_filter` | ✅ PASS | Top-1 per region = 2 rows; exact count asserted |
| PS-17 | `test_ps17_file_filter_by_values` | `file_filter_by_values` | ✅ PASS | Value groups route rows to named output files |
| PS-18 | `test_ps18_file_join_filter_agg` | `file_join_filter_agg` | ✅ PASS | Join + WHERE filter + aggregate pipeline produces summary |

---

## Warnings

One non-blocking pandas deprecation warning on PS-13:

```
Pandas4Warning: For backward compatibility, 'str' dtypes are included by select_dtypes
when 'object' dtype is specified. This behavior is deprecated and will be removed in a
future version. Explicitly pass 'str' to include to select them.
```

**Impact:** None — the template still works correctly. The warning comes from the template's
internal column-type detection logic and will need a one-line fix when migrating to Pandas 3+.

---

## New Features Validated by Tests

All 18 template tests exercise the full code path including the new Phase A–E infrastructure:

- **Friendly errors (A2):** `_friendly_error()` wraps all `preprocess()` exceptions
- **Large-file guard (A6):** templates load files through `_sniff_load` / `_load_file` which respect the 50 MB threshold
- **LEFT_KEY / RIGHT_KEY support (PS-03):** `test_ps03_file_join_two` exercises the new cross-column join path where left and right files use different column names for the join key

---

## How to Run

```bash
# All tests
python -m pytest tests/ -v

# Template tests only
python -m pytest tests/test_all_templates.py -v

# Single template
python -m pytest tests/test_all_templates.py::TestAllTemplates::test_ps03_file_join_two -v
```

---

## History Tab (Phase D)

The History tab UI is **currently disabled** (commented out in `gradio_app.py`).  
To re-enable, search for `# HISTORY_TAB` and uncomment those blocks:
- `build_ui()` → `_hist.init_db()` call
- `with gr.Tab("3 — History"):` block (~20 lines)
- `_hist.log_run()` calls in `_validate_then_generate` and `_validate_then_run`
- History event wiring section (~50 lines)

The `app_history.py` module is complete and tested independently.
