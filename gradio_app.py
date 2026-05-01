"""
gradio_app.py
-------------
Preprocessing Script Library — Gradio UI

Tabs
----
1. Explore Files  : Enter a folder path → validate file count (max 10) →
                    select a file → see extension, all columns, 10-row preview
2. Generate Script: Pick template → specify input file name(s) → set config
                    parameters → optional WHERE filter → Generate / Run script

Run:
    python gradio_app.py
    python gradio_app.py --port 7861 --share
"""
from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path

import gradio as gr
import pandas as pd

# PrepKit add-on modules
from app_profile import profile_file
import app_history as _hist
import app_pipeline as _pipe

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from preprocessing_library.generator import generate_preprocessor  # noqa: E402

_TEMPLATES_DIR = str(_HERE / "preprocessing_library" / "templates")

# ---------------------------------------------------------------------------
# Friendly error message translator  (Phase A2)
# ---------------------------------------------------------------------------
_ERROR_HINTS: list[tuple[str, str]] = [
    ("KeyError",          "Column not found — check the name matches a column shown in Tab 1."),
    ("FileNotFoundError", "File not found — verify the folder path and filename are correct."),
    ("PermissionError",   "Cannot read/write the file — it may be open in Excel or another app."),
    ("JSONDecodeError",   "Invalid JSON in parameters — check brackets, quotes and commas."),
    ("UnicodeDecodeError","Encoding error — try changing the ENCODING_PRIMARY parameter."),
    ("EmptyDataError",    "The file appears to be empty or unreadable."),
    ("MergeError",        "Join key not found in one of the files — check JOIN_KEY spelling."),
    ("ParserError",       "Could not parse the file — check the delimiter or file format."),
    ("ValueError",        "A value has the wrong type or format — check your parameter values."),
]

def _friendly_error(exc: Exception) -> str:
    """Return a plain-English error message for common exceptions."""
    exc_type = type(exc).__name__
    exc_str  = str(exc)
    for name, hint in _ERROR_HINTS:
        if name in exc_type or name in exc_str:
            return f"{hint}\n\nDetail: {exc_str[:300]}"
    return exc_str[:500]

# ---------------------------------------------------------------------------
# Large file threshold — files bigger than this are not fully column-scanned
# ---------------------------------------------------------------------------
_LARGE_FILE_MB = 50
_LARGE_FILE_BYTES = _LARGE_FILE_MB * 1_048_576

# ---------------------------------------------------------------------------
# Template category mapping  (Phase B1)
# ---------------------------------------------------------------------------
_TEMPLATE_CATEGORIES: dict[str, list[str]] = {
    "All":            [],  # filled after TEMPLATE_CATALOG is defined
    "Combine Files":  ["file_union","file_join_two","file_join_multi",
                       "file_join_multi_key","file_denormalize"],
    "Clean Data":     ["file_deduplicate","file_rename_columns",
                       "file_handle_nulls","file_cast_types"],
    "Split / Filter": ["file_split_by_value","file_filter_to_files",
                       "file_split_columns","file_filter_by_values"],
    "Summarise":      ["file_aggregate","file_rank_filter","file_join_filter_agg"],
    "Track Changes":  ["file_delta_load"],
}

# ---------------------------------------------------------------------------
# list-of-dicts param schemas for interactive table editors  (Phase C1)
# Keys map to the parameter name inside params_json.
# ---------------------------------------------------------------------------
_LOD_SCHEMAS: dict[str, dict] = {
    "JOIN_STEPS": {
        "label":       "Join Steps",
        "headers":     ["key", "how", "left_suffix", "right_suffix"],
        "default_row": ["id", "inner", "_l", "_r"],
    },
    "FILTER_RULES": {
        "label":       "Filter Rules",
        "headers":     ["condition", "output_filename"],
        "default_row": ["status == 'ACTIVE'", "active.csv"],
    },
    "NULL_RULES": {
        "label":       "Null Handling Rules",
        "headers":     ["column", "strategy", "fill_value"],
        "default_row": ["*", "fill", ""],
    },
    "TYPE_RULES": {
        "label":       "Type Cast Rules",
        "headers":     ["column", "target_type", "format"],
        "default_row": ["amount", "float", ""],
    },
    "VALUE_GROUPS": {
        "label":       "Value Groups  (comma-separate multiple values)",
        "headers":     ["values", "output_filename"],
        "default_row": ["ACTIVE,APPROVED", "active.csv"],
    },
    "COLUMN_GROUPS": {
        "label":       "Column Groups  (comma-separate column names)",
        "headers":     ["columns", "output_filename"],
        "default_row": ["name,email", "contacts.csv"],
    },
    "AGGREGATIONS": {
        "label":       "Aggregations",
        "headers":     ["column", "function", "output_column"],
        "default_row": ["amount", "sum", "total_amount"],
    },
}

# Which list-of-dicts param each template uses (first one wins for the editor)
_TEMPLATE_LOD_PARAM: dict[str, str] = {
    "file_join_multi":      "JOIN_STEPS",
    "file_filter_to_files": "FILTER_RULES",
    "file_handle_nulls":    "NULL_RULES",
    "file_cast_types":      "TYPE_RULES",
    "file_filter_by_values":"VALUE_GROUPS",
    "file_split_columns":   "COLUMN_GROUPS",
    "file_aggregate":       "AGGREGATIONS",
    "file_join_filter_agg": "AGGREGATIONS",
}

# WHERE condition operator choices  (Phase B3)
_WHERE_OPS = ["==", "!=", ">", ">=", "<", "<=", "contains", "startswith", "in"]

# ---------------------------------------------------------------------------
# Template Catalog  — parameter names MUST match {{PLACEHOLDER}} in templates
# ---------------------------------------------------------------------------
TEMPLATE_CATALOG: dict[str, dict] = {

    "file_detect_load": {
        "display_name": "PS-01 — Detect & Load",
        "description":  "Auto-detect file format and write a clean output file.",
        "function_sig": "preprocess(input_path: str) -> str",
        "input_type":   "single",
        "parameters": [
            {"name": "OUTPUT_DIR",            "type": "str", "default": "",    "help": "Directory to write the output file."},
            {"name": "OUTPUT_FORMAT",         "type": "str", "default": "csv",         "help": "csv | xlsx | json | parquet | tsv"},
            {"name": "OUTPUT_FILENAME_PREFIX","type": "str", "default": "loaded_",     "help": "Prefix added to the auto-named output filename."},
            {"name": "ENCODING_PRIMARY",      "type": "str", "default": "utf-8",       "help": "First encoding to try for text files."},
            {"name": "ENCODING_FALLBACK_1",   "type": "str", "default": "cp1252",      "help": "Second encoding to try."},
            {"name": "ENCODING_FALLBACK_2",   "type": "str", "default": "latin-1",     "help": "Third encoding to try."},
        ],
    },

    "file_union": {
        "display_name": "PS-02 — File Union (Vertical Stack)",
        "description":  "Vertically stack multiple files. Handles column mismatches, optional source tagging.",
        "function_sig": "preprocess(input_paths: list, output_columns=None) -> str",
        "input_type":   "multi",
        "parameters": [
            {"name": "OUTPUT_DIR",        "type": "str",  "default": "",     "help": "Directory to write the output file."},
            {"name": "OUTPUT_FILENAME",   "type": "str",  "default": "union.csv",    "help": "Name of the output file."},
            {"name": "OUTPUT_FORMAT",     "type": "str",  "default": "csv",          "help": "csv | xlsx | json | parquet | tsv"},
            {"name": "ADD_SOURCE_TAG",    "type": "bool", "default": "True",         "help": "Add a column showing which file each row came from."},
            {"name": "SOURCE_TAG_COLUMN", "type": "str",  "default": "_source_file", "help": "Name of the source-tag column."},
        ],
    },

    "file_join_two": {
        "display_name": "PS-03 — Join Two Files",
        "description":  "Join two files on a key column. Both files use the same key name by default; set LEFT_KEY / RIGHT_KEY to join on differently-named columns.",
        "function_sig": "preprocess(input_paths: list) -> str",
        "input_type":   "two",
        "parameters": [
            {"name": "JOIN_KEY",        "type": "str", "default": "id",
             "help": "Key column name (used for both files when LEFT_KEY / RIGHT_KEY are empty)."},
            {"name": "LEFT_KEY",        "type": "str", "default": "",
             "help": "Key column in the LEFT file. Leave blank to use JOIN_KEY. Use this when the two files have different column names for the same concept (e.g. 'customer_id' vs 'cust_num')."},
            {"name": "RIGHT_KEY",       "type": "str", "default": "",
             "help": "Key column in the RIGHT file. Leave blank to use JOIN_KEY."},
            {"name": "JOIN_TYPE",       "type": "str", "default": "inner",      "help": "inner | left | right | outer"},
            {"name": "LEFT_SUFFIX",     "type": "str", "default": "_left",      "help": "Suffix for overlapping columns from the left file."},
            {"name": "RIGHT_SUFFIX",    "type": "str", "default": "_right",     "help": "Suffix for overlapping columns from the right file."},
            {"name": "OUTPUT_DIR",      "type": "str", "default": "",           "help": "Directory to write the output file."},
            {"name": "OUTPUT_FILENAME", "type": "str", "default": "joined.csv", "help": "Name of the output file."},
            {"name": "OUTPUT_FORMAT",   "type": "str", "default": "csv",        "help": "csv | xlsx | json | parquet | tsv"},
        ],
    },

    "file_join_multi": {
        "display_name": "PS-04 — Join Multiple Files (Sequential)",
        "description":  "Join N files in sequence; each step has its own key, type, and suffixes.",
        "function_sig": "preprocess(input_paths: list) -> str",
        "input_type":   "multi",
        "parameters": [
            {"name": "JOIN_STEPS", "type": "list_of_dicts",
             "default": '[{"key": "id", "how": "inner", "left_suffix": "_l", "right_suffix": "_r"}]',
             "help": 'One entry per join step: {"key":"col","how":"inner|left|right|outer","left_suffix":"_l","right_suffix":"_r"}'},
            {"name": "OUTPUT_DIR",      "type": "str", "default": "",         "help": "Directory to write the output file."},
            {"name": "OUTPUT_FILENAME", "type": "str", "default": "multi_joined.csv", "help": "Name of the output file."},
            {"name": "OUTPUT_FORMAT",   "type": "str", "default": "csv",              "help": "csv | xlsx | json | parquet | tsv"},
        ],
    },

    "file_join_multi_key": {
        "display_name": "PS-05 — Join Two Files (Multi-Key)",
        "description":  "Join two files on multiple key columns simultaneously.",
        "function_sig": "preprocess(input_paths: list) -> str",
        "input_type":   "two",
        "parameters": [
            {"name": "JOIN_KEYS",       "type": "list", "default": '["id", "date"]',
             "help": "Key column names shared by both files. Leave LEFT_KEYS/RIGHT_KEYS blank to use this for both sides."},
            {"name": "LEFT_KEYS",       "type": "list", "default": '[]',
             "help": "Key columns in the LEFT file. Leave empty to use JOIN_KEYS. Use when left and right files have different column names for the same concept."},
            {"name": "RIGHT_KEYS",      "type": "list", "default": '[]',
             "help": "Key columns in the RIGHT file. Leave empty to use JOIN_KEYS. Must have the same length as LEFT_KEYS when specified."},
            {"name": "JOIN_TYPE",       "type": "str",  "default": "inner",              "help": "inner | left | right | outer"},
            {"name": "LEFT_SUFFIX",     "type": "str",  "default": "_left",              "help": "Suffix for overlapping columns from the left file."},
            {"name": "RIGHT_SUFFIX",    "type": "str",  "default": "_right",             "help": "Suffix for overlapping columns from the right file."},
            {"name": "OUTPUT_DIR",      "type": "str",  "default": "",           "help": "Directory to write the output file."},
            {"name": "OUTPUT_FILENAME", "type": "str",  "default": "multikey_join.csv",  "help": "Name of the output file."},
            {"name": "OUTPUT_FORMAT",   "type": "str",  "default": "csv",                "help": "csv | xlsx | json | parquet | tsv"},
        ],
    },

    "file_denormalize": {
        "display_name": "PS-06 — Denormalize (Header + Detail)",
        "description":  "Join a header file and a detail file; prefix all detail columns.",
        "function_sig": "preprocess(input_paths: list) -> str",
        "input_type":   "two",
        "parameters": [
            {"name": "JOIN_KEY",        "type": "str", "default": "id",               "help": "Column shared by header and detail. ← pick from columns"},
            {"name": "JOIN_TYPE",       "type": "str", "default": "left",             "help": "inner | left | right | outer"},
            {"name": "DETAIL_PREFIX",   "type": "str", "default": "detail_",          "help": "Prefix added to every detail column (except the join key)."},
            {"name": "OUTPUT_DIR",      "type": "str", "default": "",         "help": "Directory to write the output file."},
            {"name": "OUTPUT_FILENAME", "type": "str", "default": "denormalized.csv", "help": "Name of the output file."},
            {"name": "OUTPUT_FORMAT",   "type": "str", "default": "csv",              "help": "csv | xlsx | json | parquet | tsv"},
        ],
    },

    "file_split_by_value": {
        "display_name": "PS-07 — Split by Column Value",
        "description":  "Split a file into one output file per unique value in a chosen column.",
        "function_sig": "preprocess(input_path: str) -> str",
        "input_type":   "single",
        "parameters": [
            {"name": "SPLIT_COLUMN",         "type": "str",  "default": "category",    "help": "Column whose distinct values drive the split. ← pick from columns"},
            {"name": "FILENAME_TEMPLATE",    "type": "str",  "default": "{value}.csv", "help": "Output filename pattern — {value} is replaced by the column value."},
            {"name": "INCLUDE_SPLIT_COLUMN", "type": "bool", "default": "True",        "help": "Keep the split column in output files."},
            {"name": "OUTPUT_DIR",           "type": "str",  "default": "",    "help": "Directory to write split files."},
            {"name": "OUTPUT_FORMAT",        "type": "str",  "default": "csv",         "help": "csv | xlsx | json | parquet | tsv"},
        ],
    },

    "file_filter_to_files": {
        "display_name": "PS-08 — Filter Rows to Files (Query)",
        "description":  "Route rows to named output files using pandas query() expressions.",
        "function_sig": "preprocess(input_path: str) -> str",
        "input_type":   "single",
        "parameters": [
            {"name": "FILTER_RULES", "type": "list_of_dicts",
             "default": '[{"condition": "status == \'ACTIVE\'", "output_filename": "active.csv"}]',
             "help": 'Each: {"condition": "pandas query string", "output_filename": "name.csv"}'},
            {"name": "UNMATCHED_FILENAME", "type": "str", "default": "unmatched.csv", "help": "File for rows matching no rule. Empty string to discard."},
            {"name": "OUTPUT_DIR",         "type": "str", "default": "",      "help": "Directory to write output files."},
            {"name": "OUTPUT_FORMAT",      "type": "str", "default": "csv",           "help": "csv | xlsx | json | parquet | tsv"},
        ],
    },

    "file_split_columns": {
        "display_name": "PS-09 — Split Columns to Files",
        "description":  "Split a wide file into narrower files, each with a subset of columns.",
        "function_sig": "preprocess(input_path: str) -> str",
        "input_type":   "single",
        "parameters": [
            {"name": "COMMON_KEY_COLUMNS", "type": "list", "default": '["id"]',
             "help": "Columns repeated in every output file. ← pick from columns"},
            {"name": "COLUMN_GROUPS", "type": "list_of_dicts",
             "default": '[{"columns": ["name", "email"], "output_filename": "contacts.csv"}]',
             "help": 'Groups: [{"columns":["col1","col2"],"output_filename":"out.csv"}]'},
            {"name": "OUTPUT_DIR",    "type": "str", "default": "", "help": "Directory to write output files."},
            {"name": "OUTPUT_FORMAT", "type": "str", "default": "csv",      "help": "csv | xlsx | json | parquet | tsv"},
        ],
    },

    "file_deduplicate": {
        "display_name": "PS-10 — Deduplicate",
        "description":  "Remove duplicate rows based on selected key columns.",
        "function_sig": "preprocess(input_path: str) -> str",
        "input_type":   "single",
        "parameters": [
            {"name": "KEY_COLUMNS",                "type": "list", "default": '["id"]',         "help": "Columns that define a duplicate. ← pick from columns"},
            {"name": "KEEP",                       "type": "str",  "default": "first",           "help": "first | last | none  (none drops all duplicates)"},
            {"name": "OUTPUT_DIR",                 "type": "str",  "default": "",        "help": "Directory to write output files."},
            {"name": "OUTPUT_FILENAME",            "type": "str",  "default": "deduped.csv",     "help": "Name of the deduplicated output file."},
            {"name": "DUPLICATES_REPORT_FILENAME", "type": "str",  "default": "duplicates.csv",  "help": "File for removed duplicate rows. Empty string to discard."},
            {"name": "OUTPUT_FORMAT",              "type": "str",  "default": "csv",             "help": "csv | xlsx | json | parquet | tsv"},
        ],
    },

    "file_rename_columns": {
        "display_name": "PS-11 — Rename Columns",
        "description":  "Rename columns via a mapping dict; optionally drop unmapped columns.",
        "function_sig": "preprocess(input_path: str) -> str",
        "input_type":   "single",
        "parameters": [
            {"name": "COLUMN_MAPPING",  "type": "dict", "default": '{"OldName": "NewName", "Col2": "Column2"}',
             "help": "{old_name: new_name}. ← use detected column names as keys"},
            {"name": "DROP_UNMAPPED",   "type": "bool", "default": "False",
             "help": "If True, keep only columns present in COLUMN_MAPPING."},
            {"name": "OUTPUT_DIR",      "type": "str",  "default": "",    "help": "Directory to write the output file."},
            {"name": "OUTPUT_FILENAME", "type": "str",  "default": "renamed.csv", "help": "Name of the output file."},
            {"name": "OUTPUT_FORMAT",   "type": "str",  "default": "csv",         "help": "csv | xlsx | json | parquet | tsv"},
        ],
    },

    "file_handle_nulls": {
        "display_name": "PS-12 — Handle Nulls",
        "description":  "Audit and clean null values per column.",
        "function_sig": "preprocess(input_path: str) -> str",
        "input_type":   "single",
        "parameters": [
            {"name": "NULL_RULES", "type": "list_of_dicts",
             "default": '[{"column": "*", "strategy": "fill", "fill_value": ""}]',
             "help": 'Each: {"column":"col_or_*","strategy":"fill|mean|median|mode|forward_fill|backward_fill|drop_row","fill_value":"val"}'},
            {"name": "NULL_VALUES",          "type": "list", "default": '["", "N/A", "n/a", "NULL", "null", "None", "none", "-"]',
             "help": "Extra string values to treat as null."},
            {"name": "OUTPUT_DIR",           "type": "str",  "default": "",          "help": "Directory to write output files."},
            {"name": "OUTPUT_FILENAME",      "type": "str",  "default": "nulls_handled.csv", "help": "Name of the cleaned output file."},
            {"name": "NULL_REPORT_FILENAME", "type": "str",  "default": "null_audit.csv",    "help": "Null audit report filename. Empty string to skip."},
            {"name": "OUTPUT_FORMAT",        "type": "str",  "default": "csv",               "help": "csv | xlsx | json | parquet | tsv"},
        ],
    },

    "file_cast_types": {
        "display_name": "PS-13 — Cast Column Types",
        "description":  "Cast columns to string, integer, float, date, or boolean.",
        "function_sig": "preprocess(input_path: str) -> str",
        "input_type":   "single",
        "parameters": [
            {"name": "TYPE_RULES", "type": "list_of_dicts",
             "default": '[{"column": "amount", "target_type": "float"}, {"column": "date", "target_type": "date", "format": "%Y-%m-%d"}]',
             "help": 'Each: {"column":"col ← pick","target_type":"string|integer|float|date|boolean","format":"%Y-%m-%d" for date}'},
            {"name": "STRIP_CURRENCY",             "type": "bool", "default": "True",            "help": "Strip £$€ and commas before casting to float."},
            {"name": "TRIM_STRINGS",               "type": "bool", "default": "True",            "help": "Strip whitespace from string columns."},
            {"name": "ON_ERROR",                   "type": "str",  "default": "nullify",         "help": "nullify | keep_original | drop_row"},
            {"name": "OUTPUT_DIR",                 "type": "str",  "default": "",        "help": "Directory to write output files."},
            {"name": "OUTPUT_FILENAME",            "type": "str",  "default": "cast.csv",        "help": "Name of the output file."},
            {"name": "CAST_ERROR_REPORT_FILENAME", "type": "str",  "default": "cast_errors.csv", "help": "File for cast error rows. Empty string to discard."},
            {"name": "OUTPUT_FORMAT",              "type": "str",  "default": "csv",             "help": "csv | xlsx | json | parquet | tsv"},
        ],
    },

    "file_aggregate": {
        "display_name": "PS-14 — Aggregate / Group-By",
        "description":  "Group rows by key columns and apply aggregate functions.",
        "function_sig": "preprocess(input_path: str) -> str",
        "input_type":   "single",
        "parameters": [
            {"name": "GROUP_BY_COLUMNS", "type": "list", "default": '["category"]',
             "help": "Columns to group by. ← pick from columns"},
            {"name": "AGGREGATIONS", "type": "list_of_dicts",
             "default": '[{"column": "amount", "function": "sum", "output_column": "total_amount"}]',
             "help": 'Each: {"column":"col ← pick","function":"sum|mean|min|max|count|first|last|concat","output_column":"result"}'},
            {"name": "OUTPUT_DIR",      "type": "str", "default": "",       "help": "Directory to write the output file."},
            {"name": "OUTPUT_FILENAME", "type": "str", "default": "aggregated.csv", "help": "Name of the output file."},
            {"name": "OUTPUT_FORMAT",   "type": "str", "default": "csv",            "help": "csv | xlsx | json | parquet | tsv"},
        ],
    },

    "file_delta_load": {
        "display_name": "PS-15 — Delta Load (Change Detection)",
        "description":  "Compare new vs old file; tag rows NEW / DELETED / CHANGED / UNCHANGED.",
        "function_sig": "preprocess(input_paths: list) -> str",
        "input_type":   "two",
        "parameters": [
            {"name": "KEY_COLUMNS",        "type": "list", "default": '["id"]',
             "help": "Columns that uniquely identify a record. ← pick from columns"},
            {"name": "COMPARE_COLUMNS",    "type": "list", "default": '[]',
             "help": "Columns to check for changes. [] = compare all non-key columns."},
            {"name": "DELTA_MODE",         "type": "str",  "default": "all",
             "help": "all | new_only | deleted_only | changed_only | unchanged_only"},
            {"name": "DELTA_STATUS_COLUMN","type": "str",  "default": "_delta",
             "help": "Name of the status tag column added to output."},
            {"name": "OUTPUT_DIR",         "type": "str",  "default": "",   "help": "Directory to write the output file."},
            {"name": "OUTPUT_FILENAME",    "type": "str",  "default": "delta.csv",  "help": "Name of the output file."},
            {"name": "OUTPUT_FORMAT",      "type": "str",  "default": "csv",        "help": "csv | xlsx | json | parquet | tsv"},
        ],
    },

    "file_rank_filter": {
        "display_name": "PS-16 — Rank & Filter (Top-N per Group)",
        "description":  "Rank rows within groups, keep top-N, optionally write discarded rows.",
        "function_sig": "preprocess(input_path: str) -> str",
        "input_type":   "single",
        "parameters": [
            {"name": "PARTITION_BY",     "type": "list", "default": '["category"]',
             "help": "Columns to group by before ranking. [] = global rank. ← pick from columns"},
            {"name": "RANK_BY_COLUMN",   "type": "str",  "default": "score",
             "help": "Column whose values determine the rank. ← pick from columns"},
            {"name": "RANK_ORDER",       "type": "str",  "default": "desc",          "help": "asc (rank 1 = smallest) | desc (rank 1 = largest)"},
            {"name": "RANK_METHOD",      "type": "str",  "default": "row_number",    "help": "row_number | rank | dense_rank"},
            {"name": "RANK_COLUMN_NAME", "type": "str",  "default": "_rank",         "help": "Name of the rank column added to output."},
            {"name": "KEEP_TOP_N",       "type": "int",  "default": "1",             "help": "Keep rows with rank ≤ N. 0 = keep all (just adds rank column)."},
            {"name": "DISCARD_FILENAME", "type": "str",  "default": "discarded.csv", "help": "File for rows outside top-N. Empty string to drop silently."},
            {"name": "OUTPUT_DIR",       "type": "str",  "default": "",      "help": "Directory to write output files."},
            {"name": "OUTPUT_FILENAME",  "type": "str",  "default": "ranked.csv",    "help": "Name of the main output file."},
            {"name": "OUTPUT_FORMAT",    "type": "str",  "default": "csv",           "help": "csv | xlsx | json | parquet | tsv"},
        ],
    },

    "file_filter_by_values": {
        "display_name": "PS-17 — Filter by Value List",
        "description":  "Route rows to named files by matching a column against value lists (first-match-wins).",
        "function_sig": "preprocess(input_path: str) -> str",
        "input_type":   "single",
        "parameters": [
            {"name": "FILTER_COLUMN",   "type": "str", "default": "status",
             "help": "Column to match against value lists. ← pick from columns"},
            {"name": "VALUE_GROUPS", "type": "list_of_dicts",
             "default": '[{"values": ["ACTIVE", "APPROVED"], "output_filename": "active.csv"}, {"values": ["CLOSED"], "output_filename": "closed.csv"}]',
             "help": 'Groups (first-match-wins): [{"values":["V1","V2"],"output_filename":"name.csv"}]'},
            {"name": "CASE_SENSITIVE",  "type": "bool", "default": "False",      "help": "False = case-insensitive matching."},
            {"name": "OTHERS_FILENAME", "type": "str",  "default": "others.csv", "help": "File for unmatched rows + nulls. Empty string to discard."},
            {"name": "OUTPUT_DIR",      "type": "str",  "default": "",   "help": "Directory to write output files."},
            {"name": "OUTPUT_FORMAT",   "type": "str",  "default": "csv",        "help": "csv | xlsx | json | parquet | tsv"},
        ],
    },

    "file_join_filter_agg": {
        "display_name": "PS-18 — Join, Filter & Aggregate",
        "description":  "Join two files → WHERE filter on joined result → group-by aggregate → optional ranking.",
        "function_sig": "preprocess(input_paths: list) -> str",
        "input_type":   "two",
        "parameters": [
            {"name": "JOIN_KEYS",        "type": "list", "default": '["id"]',
             "help": "Column(s) to join on. ← pick from columns"},
            {"name": "JOIN_TYPE",        "type": "str",  "default": "inner",
             "help": "inner | left | right | outer"},
            {"name": "WHERE_CONDITION",  "type": "str",  "default": "",
             "help": "pandas query() on joined result. Leave empty for no filter. e.g.  amount > 0 and status == 'ACTIVE'"},
            {"name": "GROUP_BY_COLUMNS", "type": "list", "default": '["category"]',
             "help": "Columns to group by after filtering. ← pick from columns"},
            {"name": "AGGREGATIONS",     "type": "list_of_dicts",
             "default": '[{"column": "*", "function": "count", "output_column": "_row_count"}]',
             "help": 'Each: {"column":"col or *","function":"count|sum|mean|min|max|nunique|first|last|std","output_column":"name"}. Use "*" or "count" for row count.'},
            {"name": "RANK_BY_COLUMN",   "type": "str",  "default": "",
             "help": "Column in aggregated result to rank by. Leave empty to skip ranking. ← pick"},
            {"name": "RANK_ORDER",       "type": "str",  "default": "desc",
             "help": "asc (rank 1 = smallest) | desc (rank 1 = largest)"},
            {"name": "RANK_COLUMN_NAME", "type": "str",  "default": "_rank",
             "help": "Name of the rank column added to output."},
            {"name": "KEEP_TOP_N",       "type": "int",  "default": "0",
             "help": "Keep rows with rank <= N. 0 = keep all rows."},
            {"name": "OUTPUT_DIR",       "type": "str",  "default": "",
             "help": "Directory to write the output file."},
            {"name": "OUTPUT_FILENAME",  "type": "str",  "default": "join_filter_agg.csv",
             "help": "Name of the output file."},
            {"name": "OUTPUT_FORMAT",    "type": "str",  "default": "csv",
             "help": "csv | xlsx | json | parquet | tsv"},
        ],
    },
}

_TEMPLATE_CHOICES = [(v["display_name"], k) for k, v in TEMPLATE_CATALOG.items()]
_TEMPLATE_CATEGORIES["All"] = [k for k in TEMPLATE_CATALOG]

# ---------------------------------------------------------------------------
# Per-template input file configuration
# input_type: "single" | "two" | "multi"
#   single → 1 file field
#   two    → 2 file fields (left/right, header/detail, new/old)
#   multi  → 1 field accepting comma-separated paths (or folder + filenames)
# ---------------------------------------------------------------------------
_INPUT_FILE_CONFIG: dict[str, list[dict]] = {
    "file_detect_load":     [{"label": "Input File",                   "key": "input_path"}],
    "file_union":           [{"label": "Input Files (comma-separated paths or folder path)", "key": "input_paths", "multi": True}],
    "file_join_two":        [{"label": "Left File",                    "key": "left_path"},
                             {"label": "Right File",                   "key": "right_path"}],
    "file_join_multi":      [{"label": "Input Files (comma-separated paths)",                "key": "input_paths", "multi": True}],
    "file_join_multi_key":  [{"label": "Left File",                    "key": "left_path"},
                             {"label": "Right File",                   "key": "right_path"}],
    "file_denormalize":     [{"label": "Header File",                  "key": "header_path"},
                             {"label": "Detail File",                  "key": "detail_path"}],
    "file_split_by_value":  [{"label": "Input File",                   "key": "input_path"}],
    "file_filter_to_files": [{"label": "Input File",                   "key": "input_path"}],
    "file_split_columns":   [{"label": "Input File",                   "key": "input_path"}],
    "file_deduplicate":     [{"label": "Input File",                   "key": "input_path"}],
    "file_rename_columns":  [{"label": "Input File",                   "key": "input_path"}],
    "file_handle_nulls":    [{"label": "Input File",                   "key": "input_path"}],
    "file_cast_types":      [{"label": "Input File",                   "key": "input_path"}],
    "file_aggregate":       [{"label": "Input File",                   "key": "input_path"}],
    "file_delta_load":      [{"label": "New File (current data)",      "key": "new_path"},
                             {"label": "Old / Reference File",         "key": "old_path"}],
    "file_rank_filter":     [{"label": "Input File",                   "key": "input_path"}],
    "file_filter_by_values":[{"label": "Input File",                   "key": "input_path"}],
    "file_join_filter_agg": [{"label": "Left File",                    "key": "left_path"},
                              {"label": "Right File",                   "key": "right_path"}],
}
_MAX_FILE_SLOTS = 2   # maximum file inputs shown (single uses slot 1 only)

# Maps 2-file template names → (placeholder_for_file1, placeholder_for_file2)
# These are auto-injected from the UI file selectors — NOT shown in the params JSON.
_TWO_FILE_PLACEHOLDERS: dict[str, tuple[str, str]] = {
    "file_join_two":        ("LEFT_FILENAME",   "RIGHT_FILENAME"),
    "file_join_multi_key":  ("LEFT_FILENAME",   "RIGHT_FILENAME"),
    "file_denormalize":     ("HEADER_FILENAME", "DETAIL_FILENAME"),
    "file_delta_load":      ("NEW_FILENAME",    "OLD_FILENAME"),
    "file_join_filter_agg": ("LEFT_FILENAME",   "RIGHT_FILENAME"),
}


def _file_slot_labels(template_name: str) -> tuple:
    """Return (label_1, visible_1, label_2, visible_2) for the two file input slots."""
    slots = _INPUT_FILE_CONFIG.get(template_name, [{"label": "Input File", "key": "input_path"}])
    lbl1  = slots[0]["label"] if len(slots) > 0 else "Input File"
    vis1  = True
    lbl2  = slots[1]["label"] if len(slots) > 1 else "File 2"
    vis2  = len(slots) > 1
    return lbl1, vis1, lbl2, vis2


# ---------------------------------------------------------------------------
# File inspection helpers
# ---------------------------------------------------------------------------
_ENCODINGS = ["utf-8", "cp1252", "latin-1"]


def _count_rows_fast(file_path: str, sample_df: pd.DataFrame | None = None) -> int:
    """
    Fast row count — never reads the whole file.
    - CSV/TSV/TXT: samples first 64 KB to get avg bytes/line, extrapolates.
      Exact for files ≤ 64 KB; ±5 % estimate for larger files.
    - parquet: reads metadata (no data loaded).
    - Excel/JSON: uses already-loaded sample_df length (scan always passes one).
    Returns -1 on failure.
    """
    ext = Path(file_path).suffix.lower()
    if ext in (".csv", ".tsv", ".txt", ""):
        try:
            file_size = Path(file_path).stat().st_size
            if file_size == 0:
                return 0
            sample_size = min(65_536, file_size)
            with open(file_path, "rb") as fh:
                chunk = fh.read(sample_size)
            newlines = chunk.count(b"\n")
            if newlines <= 1:
                # Very few lines in sample — just count them all (tiny file)
                with open(file_path, "rb") as fh:
                    total = sum(1 for _ in fh)
                return max(0, total - 1)
            avg_bytes_per_line = sample_size / newlines
            estimated = int(file_size / avg_bytes_per_line)
            return max(0, estimated - 1)  # subtract header row
        except Exception:
            pass
    # For binary formats, re-use the already-loaded sample if provided
    if sample_df is not None:
        return len(sample_df)
    try:
        if ext in (".xlsx", ".xls"):
            return len(pd.read_excel(file_path, usecols=[0]))
        if ext == ".parquet":
            import pyarrow.parquet as _pq  # type: ignore
            return _pq.read_metadata(file_path).num_rows
        if ext == ".json":
            with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                data = json.load(fh)
            return len(data) if isinstance(data, list) else 1
    except Exception:
        pass
    return -1


def _sniff_load(file_path: str, max_rows: int = 200) -> pd.DataFrame:
    ext = Path(file_path).suffix.lower()
    try:
        if ext in (".xlsx", ".xls"):
            return pd.read_excel(file_path, engine="openpyxl" if ext == ".xlsx" else "xlrd", nrows=max_rows)
        if ext == ".json":
            with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                data = json.load(fh)
            return pd.json_normalize(data if isinstance(data, list) else [data]).head(max_rows)
        if ext == ".parquet":
            return pd.read_parquet(file_path).head(max_rows)
        if ext in (".html", ".htm"):
            tables = pd.read_html(file_path)
            return tables[0].head(max_rows) if tables else pd.DataFrame()
        if ext == ".zip":
            return _sniff_load_zip(file_path, max_rows)
        for enc in _ENCODINGS:
            try:
                with open(file_path, "r", encoding=enc, errors="replace") as fh:
                    sample = fh.read(8192)
                try:
                    sep = csv.Sniffer().sniff(sample).delimiter
                except csv.Error:
                    sep = ","
                return pd.read_csv(file_path, sep=sep, encoding=enc,
                                   on_bad_lines="skip", low_memory=False, nrows=max_rows)
            except Exception:
                continue
    except Exception as exc:
        return pd.DataFrame({"error": [str(exc)]})
    return pd.DataFrame()


def _sniff_load_zip(file_path: str, max_rows: int) -> pd.DataFrame:
    supported = {".csv", ".tsv", ".txt", ".xlsx", ".xls", ".json"}
    with zipfile.ZipFile(file_path, "r") as z:
        for name in z.namelist():
            if Path(name).suffix.lower() in supported:
                with tempfile.TemporaryDirectory() as tmp:
                    z.extract(name, tmp)
                    return _sniff_load(os.path.join(tmp, name), max_rows)
    return pd.DataFrame({"error": ["No loadable file found in ZIP"]})


_MAX_FOLDER_FILES = 10   # hard limit on files per folder scan

# ---------------------------------------------------------------------------
# Folder scan cache — keyed on (folder_path, folder_mtime) so rescanning
# a folder that hasn't changed on disk is instant.
# Stores raw data only (no gr.update() objects — those are single-use).
# ---------------------------------------------------------------------------
_scan_cache: dict[tuple, dict] = {}


def _scan_one_file(fpath: Path) -> dict:
    """Scan a single file and return a result dict. Runs in a thread."""
    name = fpath.name
    ext  = fpath.suffix.lower() or "(none)"
    file_size = fpath.stat().st_size

    # Large-file guard: skip full column read for very large files
    if file_size > _LARGE_FILE_BYTES:
        size_mb = file_size / 1_048_576
        return {
            "name": name, "path": str(fpath), "ext": ext,
            "rows": -1, "cols": -1, "columns": [], "preview": {},
            "status": "⚠️",
            "error": f"Large file ({size_mb:.0f} MB) — select in Tab 1 to inspect columns.",
            "large": True,
        }

    try:
        # Load 10 rows — enough for columns + cached preview in show_file_detail
        df    = _sniff_load(str(fpath), max_rows=10)
        ncol  = len(df.columns)
        cols  = [str(c) for c in df.columns.tolist()]
        nrow  = _count_rows_fast(str(fpath), df)
        # Serialise the preview now so show_file_detail never re-reads disk
        preview_records = df.head(10).astype(str).to_dict(orient="split")
        status = "✅"
    except Exception as exc:
        nrow, ncol, cols = 0, 0, []
        preview_records  = {}
        status = "⚠️"
        exc_str = str(exc)

    return {
        "name":    name,
        "path":    str(fpath),
        "ext":     ext,
        "rows":    nrow,
        "cols":    ncol,
        "columns": cols,
        "preview": preview_records,   # cached — no second disk read in show_file_detail
        "status":  status,
        "error":   locals().get("exc_str", ""),
        "large":   False,
    }


def scan_folder(folder_path: str):
    """
    Scan *folder_path* for files (non-recursive, top-level only).
    Files are scanned in parallel (ThreadPoolExecutor).
    Results are cached per (folder_path, folder_mtime) for instant repeated scans.

    Returns:
        status_html, file_selector_update, file_data_json,
        cols_info_html, filename_choices_update, base_location_value
    """
    _EMPTY_CHOICES = gr.update(choices=[], value=None)
    _EMPTY_FILE_DD = gr.update(choices=["(none)"], value="(none)")

    folder_path = (folder_path or "").strip()
    if not folder_path:
        msg = "<p style='color:gray'>Enter a folder path above and click <b>Scan Folder</b>.</p>"
        return msg, _EMPTY_CHOICES, "{}", msg, _EMPTY_FILE_DD, ""

    folder = Path(folder_path)
    if not folder.exists():
        msg = f"<p style='color:red'>Folder not found: <code>{folder_path}</code></p>"
        return msg, _EMPTY_CHOICES, "{}", msg, _EMPTY_FILE_DD, ""
    if not folder.is_dir():
        msg = f"<p style='color:red'>Path is not a folder: <code>{folder_path}</code></p>"
        return msg, _EMPTY_CHOICES, "{}", msg, _EMPTY_FILE_DD, ""

    # Collect only files (no sub-directories), ignore hidden files
    all_files = sorted(
        p for p in folder.iterdir()
        if p.is_file() and not p.name.startswith(".")
    )

    if len(all_files) > _MAX_FOLDER_FILES:
        msg = (
            f"<p style='color:red'><b>File count exceeds the maximum allowed limit of "
            f"{_MAX_FOLDER_FILES} files.</b><br/>"
            f"Found {len(all_files)} files in <code>{folder_path}</code>.<br/>"
            f"Please use a sub-folder with 10 or fewer files.</p>"
        )
        return msg, _EMPTY_CHOICES, "{}", msg, _EMPTY_FILE_DD, ""

    if not all_files:
        msg = f"<p style='color:orange'>No files found in <code>{folder_path}</code>.</p>"
        return msg, _EMPTY_CHOICES, "{}", msg, _EMPTY_FILE_DD, ""

    # ── Cache check — use folder mtime as freshness key ─────────────────────
    folder_mtime = folder.stat().st_mtime
    cache_key    = (str(folder), folder_mtime)
    if cache_key in _scan_cache:
        return _make_scan_result(_scan_cache[cache_key])

    # ── Parallel scan ────────────────────────────────────────────────────────
    results_by_name: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=min(len(all_files), 6)) as pool:
        future_map = {pool.submit(_scan_one_file, fpath): fpath for fpath in all_files}
        for future in as_completed(future_map):
            r = future.result()
            results_by_name[r["name"]] = r

    # Restore original sort order (as_completed returns in completion order)
    ordered = [results_by_name[fpath.name] for fpath in all_files if fpath.name in results_by_name]

    file_data: dict[str, dict] = {}
    rows_html = ""
    all_columns: dict[str, list[str]] = {}
    filename_choices = ["(none)"]

    for r in ordered:
        name     = r["name"]
        ext      = r["ext"]
        nrow     = r["rows"]
        ncol     = r["cols"]
        cols     = r["columns"]
        cols_all = ", ".join(cols)
        status   = r["status"]

        file_data[name] = {
            "path":    r["path"],
            "ext":     ext,
            "rows":    nrow,
            "cols":    ncol,
            "columns": cols,
            "preview": r["preview"],
        }
        if cols:
            all_columns[name] = cols
        filename_choices.append(name)
        rows_html += (
            f"<tr style='vertical-align:top'>"
            f"<td style='padding:6px 12px'>{status}</td>"
            f"<td style='padding:6px 12px;white-space:nowrap'><b>{name}</b></td>"
            f"<td style='padding:6px 12px'>{ext}</td>"
            f"<td style='padding:6px 12px'>{nrow:,}</td>"
            f"<td style='padding:6px 12px'>{ncol}</td>"
            f"<td style='padding:6px 12px;color:#333;font-size:0.85em'>{cols_all}</td>"
            f"</tr>"
        )

    total = len(all_files)
    summary_html = (
        f"<div style='margin-bottom:8px;color:#555'>📂 <b>{folder_path}</b> &nbsp;—&nbsp; "
        f"{total} file(s) found</div>"
        "<table style='border-collapse:collapse;width:100%'>"
        "<thead><tr style='background:#f0f0f0'>"
        "<th style='padding:6px 12px'></th>"
        "<th style='padding:6px 12px;text-align:left'>File Name</th>"
        "<th style='padding:6px 12px;text-align:left'>Ext</th>"
        "<th style='padding:6px 12px;text-align:left'>Rows</th>"
        "<th style='padding:6px 12px;text-align:left'>Cols</th>"
        "<th style='padding:6px 12px;text-align:left'>All Column Names</th>"
        "</tr></thead>"
        f"<tbody>{rows_html}</tbody></table>"
    )

    col_sections = ""
    for fname, cols in all_columns.items():
        chips = "".join(
            f"<span style='display:inline-block;background:#e8f0fe;color:#1a6e9e;"
            f"border-radius:3px;padding:2px 8px;margin:2px 3px;font-family:monospace;font-size:0.85em'>{c}</span>"
            for c in cols
        )
        col_sections += (
            f"<div style='margin-bottom:12px'>"
            f"<b>{fname}</b> <span style='color:#888;font-size:0.85em'>({len(cols)} columns)</span>"
            f"<br/><div style='margin-top:4px'>{chips}</div></div>"
        )

    cols_info_html = (
        "<details open><summary style='cursor:pointer;font-weight:600'>"
        "All columns — use these names in your parameters</summary>"
        f"<div style='margin-top:8px'>{col_sections}</div></details>"
        if col_sections
        else "<p style='color:gray'>No columns detected.</p>"
    )

    filenames = list(file_data.keys())
    # Cache raw data only — gr.update() objects are single-use Gradio descriptors
    # and must be freshly created on every return.
    _scan_cache[cache_key] = {
        "summary_html":      summary_html,
        "filenames":         filenames,
        "file_data_json":    json.dumps(file_data),
        "cols_info_html":    cols_info_html,
        "filename_choices":  filename_choices,
        "base_location":     str(folder),
    }
    return _make_scan_result(_scan_cache[cache_key])


def _make_scan_result(cached: dict) -> tuple:
    """Reconstruct the scan return tuple from cached raw data (fresh gr.update() each time)."""
    filenames        = cached["filenames"]
    filename_choices = cached["filename_choices"]
    return (
        cached["summary_html"],
        gr.update(choices=filenames, value=filenames[0] if filenames else None),
        cached["file_data_json"],
        cached["cols_info_html"],
        gr.update(choices=filename_choices, value="(none)"),
        cached["base_location"],
    )


def show_file_detail(selected_name: str, file_data_json: str, selected_sheet: str = ""):
    """
    Return (file_info_html, preview_df, profile_df, sheet_picker_update, col_profile_update)
    for the selected file.
    Uses the preview cached during scan_folder — no disk read on selection.
    When selected_sheet is set (Excel), re-reads from disk using that sheet.
    """
    _EMPTY = (
        "<p style='color:gray'>Select a file above.</p>",
        pd.DataFrame(), pd.DataFrame(),
        gr.update(choices=[], visible=False, value=None),
        gr.update(visible=False),
    )
    if not selected_name or not file_data_json:
        return _EMPTY
    try:
        file_data = json.loads(file_data_json)
    except Exception:
        return ("<p style='color:red'>State error.</p>", pd.DataFrame(), pd.DataFrame(),
                gr.update(choices=[], visible=False, value=None), gr.update(visible=False))
    entry = file_data.get(selected_name)
    if not entry:
        return ("<p style='color:red'>File not found in state.</p>", pd.DataFrame(), pd.DataFrame(),
                gr.update(choices=[], visible=False, value=None), gr.update(visible=False))

    file_path = entry["path"]
    ext = entry.get("ext", "").lower()

    # Sheet picker — detect sheets for Excel files
    sheet_names: list[str] = []
    sheet_picker_update = gr.update(choices=[], visible=False, value=None)
    if ext in (".xlsx", ".xls"):
        try:
            xf = pd.ExcelFile(file_path)
            sheet_names = xf.sheet_names
            if sheet_names:
                current_sheet = selected_sheet if selected_sheet in sheet_names else sheet_names[0]
                sheet_picker_update = gr.update(
                    choices=sheet_names, value=current_sheet, visible=True
                )
        except Exception:
            pass

    # Load data — use cached preview unless a specific sheet is requested
    df: pd.DataFrame = pd.DataFrame()
    if ext in (".xlsx", ".xls") and selected_sheet and sheet_names:
        try:
            df = pd.read_excel(file_path, sheet_name=selected_sheet, nrows=10)
        except Exception:
            df = pd.DataFrame()
    else:
        preview = entry.get("preview")
        if preview and preview.get("data") and preview.get("columns"):
            df = pd.DataFrame(preview["data"], columns=preview["columns"])
        else:
            df = _sniff_load(file_path, max_rows=10)

    if df.empty:
        return (
            "<p style='color:orange'>File loaded but no data found.</p>",
            pd.DataFrame(), pd.DataFrame(), sheet_picker_update, gr.update(visible=False),
        )

    # Column chips
    cols_to_show = [str(c) for c in df.columns.tolist()] if df is not None else entry.get("columns", [])
    col_chips = "".join(
        f"<span style='display:inline-block;background:#e8f0fe;color:#1a6e9e;"
        f"border-radius:3px;padding:2px 8px;margin:2px 3px;font-family:monospace;"
        f"font-size:0.85em'>{c}</span>"
        for c in cols_to_show
    )

    rows_val = entry.get('rows', 0)
    rows_display = f"{rows_val:,}" if isinstance(rows_val, int) and rows_val >= 0 else "?"
    info_html = (
        f"<div style='padding:10px 14px;background:#f8f9fa;border-left:4px solid #1a6e9e;"
        f"border-radius:4px;margin-bottom:10px'>"
        f"<b>File:</b> {selected_name} &nbsp;|&nbsp; "
        f"<b>Extension:</b> {ext} &nbsp;|&nbsp; "
        f"<b>Rows:</b> {rows_display} &nbsp;|&nbsp; "
        f"<b>Columns ({len(cols_to_show)}):</b><br/>"
        f"<div style='margin-top:6px'>{col_chips}</div>"
        f"</div>"
    )

    # Build profile
    profile_df = profile_file(df=df.copy())

    return info_html, df.head(10), profile_df, sheet_picker_update, gr.update(visible=True)


# ---------------------------------------------------------------------------
# Column dropdown helper
# ---------------------------------------------------------------------------

def _get_all_columns(file_data_json: str) -> list[str]:
    try:
        file_data = json.loads(file_data_json)
    except Exception:
        return []
    seen: list[str] = []
    for entry in file_data.values():
        for col in entry.get("columns", []):
            if col not in seen:
                seen.append(col)
    return seen


# ---------------------------------------------------------------------------
# Template UI helpers
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def _params_to_json_str(template_name: str) -> str:
    info = TEMPLATE_CATALOG.get(template_name)
    if not info:
        return "{}"
    d: dict = {}
    for p in info["parameters"]:
        raw, ptype = p["default"], p["type"]
        if ptype in ("list", "dict", "list_of_dicts"):
            try:
                d[p["name"]] = json.loads(raw)
            except Exception:
                d[p["name"]] = raw
        elif ptype == "bool":
            d[p["name"]] = raw.strip().lower() == "true"
        elif ptype == "int":
            try:
                d[p["name"]] = int(raw)
            except Exception:
                d[p["name"]] = raw
        else:
            d[p["name"]] = raw
    return json.dumps(d, indent=2)


@lru_cache(maxsize=None)
def _build_param_help_html(template_name: str) -> str:
    info = TEMPLATE_CATALOG.get(template_name)
    if not info:
        return ""
    rows = "".join(
        f"<tr><td style='padding:4px 8px;font-family:monospace;color:#1a6e9e;white-space:nowrap'>{p['name']}</td>"
        f"<td style='padding:4px 8px;color:#777;white-space:nowrap'>{p['type']}</td>"
        f"<td style='padding:4px 8px;font-size:0.85em'>{p['help']}</td></tr>"
        for p in info["parameters"]
    )
    return (
        "<details open><summary style='cursor:pointer;font-weight:600;margin-bottom:4px'>"
        "Parameter Reference</summary>"
        "<table style='border-collapse:collapse;width:100%;font-size:0.88em'>"
        "<thead><tr style='background:#f5f5f5'>"
        "<th style='padding:4px 8px;text-align:left'>Parameter</th>"
        "<th style='padding:4px 8px;text-align:left'>Type</th>"
        "<th style='padding:4px 8px;text-align:left'>Description</th>"
        "</tr></thead>"
        f"<tbody>{rows}</tbody></table></details>"
    )


def update_template_ui(template_name: str):
    """Returns (desc_html, params_json, param_help_html,
                lbl1, vis1_update, lbl2, vis2_update)."""
    info = TEMPLATE_CATALOG.get(template_name)
    if not info:
        return "", "{}", "", "Input File", gr.update(visible=True), "File 2", gr.update(visible=False)
    desc_html = (
        f"<div style='padding:8px 14px;background:#f8f9fa;border-left:4px solid #1a6e9e;border-radius:4px'>"
        f"<b>{info['display_name']}</b>&nbsp;&nbsp;"
        f"<span style='color:#444'>{info['description']}</span><br/>"
        f"<code style='color:#555;font-size:0.88em'>def {info['function_sig']}</code>"
        f"</div>"
    )
    lbl1, vis1, lbl2, vis2 = _file_slot_labels(template_name)
    return (
        desc_html,
        _params_to_json_str(template_name),
        _build_param_help_html(template_name),
        lbl1, gr.update(visible=vis1),
        lbl2, gr.update(visible=vis2),
    )


# ---------------------------------------------------------------------------
# Column pickers
# ---------------------------------------------------------------------------
_COL_PICKER_PARAMS = [
    ("JOIN_KEY",       "PS-03/06: join key"),
    ("SPLIT_COLUMN",   "PS-07: split column"),
    ("FILTER_COLUMN",  "PS-17: filter column"),
    ("RANK_BY_COLUMN", "PS-16: rank by column"),
]
_COL_LIST_PARAMS = [
    ("KEY_COLUMNS",        "PS-10/15: key columns"),
    ("PARTITION_BY",       "PS-16: partition by"),
    ("GROUP_BY_COLUMNS",   "PS-14: group by"),
    ("COMPARE_COLUMNS",    "PS-15: compare columns"),
    ("COMMON_KEY_COLUMNS", "PS-09: key columns"),
    ("JOIN_KEYS",          "PS-05: join keys"),
]


def _set_col_in_json(col_val: str, param_key: str, current_json: str) -> str:
    if not col_val or col_val == "(none)" or not current_json.strip():
        return current_json
    try:
        d = json.loads(current_json)
    except Exception:
        return current_json
    if param_key in d:
        d[param_key] = col_val
    return json.dumps(d, indent=2)


def _append_col_to_list(col_val: str, param_key: str, current_json: str) -> str:
    if not col_val or col_val == "(none)" or not current_json.strip():
        return current_json
    try:
        d = json.loads(current_json)
    except Exception:
        return current_json
    existing = d.get(param_key)
    if isinstance(existing, list) and col_val not in existing:
        existing.append(col_val)
        d[param_key] = existing
    return json.dumps(d, indent=2)


def _auto_fill_output_params(
    params_json: str,
    template_name: str,
    file1_val: str,
    base_loc: str,
) -> str:
    """
    Keep OUTPUT_DIR = "" (empty = same folder as input at runtime) and derive a
    default OUTPUT_FILENAME from the master file name and the template shortcut.

    Naming convention: pp_{file1_stem}_{template_shortcut}.{OUTPUT_FORMAT}
    OUTPUT_DIR is intentionally left empty so the generated script writes its
    output next to the input file rather than to a hardcoded path.
    """
    try:
        d = json.loads(params_json) if (params_json or "").strip() else {}
    except Exception:
        return params_json

    # Always keep OUTPUT_DIR empty — templates resolve it to input file's directory
    if "OUTPUT_DIR" in d:
        d["OUTPUT_DIR"] = ""

    if "OUTPUT_FILENAME" in d:
        stem = Path(file1_val).stem if file1_val and file1_val.strip() else "output"
        shortcut = template_name.removeprefix("file_") if template_name else "out"
        fmt = str(d.get("OUTPUT_FORMAT", "csv")).lower().replace("excel", "xlsx")
        d["OUTPUT_FILENAME"] = f"pp_{stem}_{shortcut}.{fmt}"

    return json.dumps(d, indent=2)


# ---------------------------------------------------------------------------
# WHERE condition injection
# ---------------------------------------------------------------------------
_WHERE_FILTER_CODE = '''\

def _load_and_filter(file_path: str) -> "pd.DataFrame":
    """Load file then apply WHERE_CONDITION pre-filter if set."""
    df = _load_file(file_path)
    if WHERE_CONDITION:
        try:
            df = df.query(WHERE_CONDITION)
            df = df.reset_index(drop=True)
        except Exception as _exc:
            import warnings as _w
            _w.warn(f"WHERE_CONDITION filter failed ({_exc}). Returning unfiltered data.")
    return df

'''


def _inject_where_condition(script: str, where: str) -> str:
    """
    1. Inject WHERE_CONDITION constant after the config closing line.
    2. Add _load_and_filter() wrapper before _write_output.
    3. Replace all _load_file( calls inside preprocess() with _load_and_filter(.
    """
    # 1 — inject constant after config block end marker
    marker = "# " + "─" * 77
    config_end_idx = script.rfind(marker, 0, script.index("\ndef _load_file("))
    if config_end_idx == -1:
        # fallback: inject after the last config assignment before first def
        config_end_idx = script.index("\ndef _load_file(")
    inject_const = f'\nWHERE_CONDITION = {json.dumps(where)}  # pre-filter: pandas query string, "" = no filter\n'
    script = script[:config_end_idx] + inject_const + script[config_end_idx:]

    # 2 — add wrapper before _write_output
    target = "\ndef _write_output("
    if target in script:
        script = script.replace(target, _WHERE_FILTER_CODE + target, 1)

    # 3 — replace _load_file( → _load_and_filter( only inside preprocess()
    preprocess_start = script.index("\ndef preprocess(")
    script = (
        script[:preprocess_start]
        + script[preprocess_start:].replace("_load_file(", "_load_and_filter(")
    )
    return script


# ---------------------------------------------------------------------------
# __main__ block builder
# ---------------------------------------------------------------------------

def _build_main_block(template_name: str, base_location: str, file1: str, file2: str) -> str:
    """
    Build a runnable __main__ block.

    *base_location* is the folder that was scanned in Tab 1.
    *file1* / *file2* are plain file names (not full paths).
    The block emits BASE_LOCATION + os.path.join(BASE_LOCATION, filename) so users
    only need to update the one BASE_LOCATION variable if the folder moves.
    """
    slots = _INPUT_FILE_CONFIG.get(template_name, [{"key": "input_path"}])
    base  = (base_location or "").strip().replace("\\", "/")
    f1    = (file1 or "").strip()
    f2    = (file2 or "").strip()

    base_line = f'BASE_LOCATION = r"{base}"' if base else 'BASE_LOCATION = r"./input_folder"   # ← update'

    lines = [
        "",
        "",
        "import os as _os",
        "",
        "# " + "─" * 77,
        "# ── Run Configuration ───────────────────────────────────────────────────────",
        "# ── Set BASE_LOCATION to your input folder. File names are resolved from it. ",
        "# " + "─" * 77,
        base_line,
        "",
    ]

    def _join(fname: str, placeholder: str) -> str:
        """Emit os.path.join(BASE_LOCATION, fname) or a placeholder comment."""
        if fname:
            return f'_os.path.join(BASE_LOCATION, "{fname}")'
        return f'"./{ placeholder }"   # ← update'

    if len(slots) == 1:
        if slots[0].get("multi"):
            # comma-separated filenames
            raw_names = [n.strip() for n in f1.split(",") if n.strip()] if f1 else []
            if raw_names:
                var_lines, var_names = [], []
                for i, nm in enumerate(raw_names, 1):
                    vname = f"INPUT_FILE_{i}"
                    var_lines.append(f'{vname} = _os.path.join(BASE_LOCATION, "{nm}")')
                    var_names.append(vname)
                lines += var_lines
                lines.append(f"INPUT_FILES = [{', '.join(var_names)}]")
            else:
                lines += [
                    'INPUT_FILE_1 = _os.path.join(BASE_LOCATION, "file1.csv")   # ← update',
                    'INPUT_FILE_2 = _os.path.join(BASE_LOCATION, "file2.csv")   # ← update',
                    "INPUT_FILES  = [INPUT_FILE_1, INPUT_FILE_2]",
                ]
            lines += [
                "",
                'if __name__ == "__main__":',
                "    result = preprocess(INPUT_FILES)",
                '    print(f"Output: {result}")',
            ]
        else:
            lines += [
                f"INPUT_FILE = {_join(f1, 'input.csv')}",
                "",
                'if __name__ == "__main__":',
                "    result = preprocess(INPUT_FILE)",
                '    print(f"Output: {result}")',
            ]
    elif len(slots) == 2:
        lbl1 = slots[0].get("label", "File 1")
        lbl2 = slots[1].get("label", "File 2")
        lines += [
            f"INPUT_FILE_1 = {_join(f1, 'input_1.csv')}   # {lbl1}",
            f"INPUT_FILE_2 = {_join(f2, 'input_2.csv')}   # {lbl2}",
            "INPUT_FILES  = [INPUT_FILE_1, INPUT_FILE_2]",
            "",
            'if __name__ == "__main__":',
            "    result = preprocess(INPUT_FILES)",
            '    print(f"Output: {result}")',
        ]

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Parameter conversion → generator format
# ---------------------------------------------------------------------------

def _json_val_to_python_literal(val, ptype: str) -> str:
    if isinstance(val, bool):
        return "True" if val else "False"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, (list, dict)):
        return json.dumps(val)
    return str(val)


def _params_json_to_generator_format(params_dict: dict, template_name: str) -> dict:
    info     = TEMPLATE_CATALOG.get(template_name, {})
    type_map = {p["name"]: p["type"] for p in info.get("parameters", [])}
    return {k: _json_val_to_python_literal(v, type_map.get(k, "str")) for k, v in params_dict.items()}


# ---------------------------------------------------------------------------
# Script generation
# ---------------------------------------------------------------------------

def _inject_filename_placeholders(
    gen_params: dict, template_name: str, file1_val: str, file2_val: str
) -> dict:
    """Auto-inject LEFT_FILENAME/RIGHT_FILENAME (or equivalent) for 2-file templates."""
    placeholders = _TWO_FILE_PLACEHOLDERS.get(template_name)
    if placeholders:
        k1, k2 = placeholders
        gen_params[k1] = (file1_val or "input_1.csv").strip()
        gen_params[k2] = (file2_val or "input_2.csv").strip()
    return gen_params


def generate_script(
    template_name: str,
    params_json: str,
    script_name: str,
    base_location: str,
    file1_val: str,
    file2_val: str,
    where_condition: str,
):
    if not template_name:
        return "<p style='color:red'>Select a template first.</p>", "", None

    try:
        params_dict = json.loads(params_json)
    except json.JSONDecodeError as exc:
        return f"<p style='color:red'><b>Invalid JSON in parameters:</b> {exc}</p>", "", None
    try:
        gen_params = _params_json_to_generator_format(params_dict, template_name)
        gen_params = _inject_filename_placeholders(gen_params, template_name, file1_val, file2_val)
    except Exception as exc:
        return f"<p style='color:red'><b>Parameter error:</b> {exc}</p>", "", None

    safe_name = (script_name or "").strip()
    if not safe_name:
        safe_name = f"{template_name}_preprocess.py"
    elif not safe_name.endswith(".py"):
        safe_name += ".py"

    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            generated_path = generate_preprocessor(
                template_name=template_name,
                parameters=gen_params,
                output_script_name=safe_name,
                output_dir=tmp_dir,
                templates_dir=_TEMPLATES_DIR,
            )
            script_content = Path(generated_path).read_text(encoding="utf-8")
        except Exception as exc:
            return f"<p style='color:red'><b>Generation failed:</b> {exc}</p>", "", None

    # Inject WHERE condition
    where = (where_condition or "").strip()
    if where:
        try:
            script_content = _inject_where_condition(script_content, where)
        except Exception as exc:
            return f"<p style='color:red'><b>WHERE injection failed:</b> {exc}</p>", "", None

    # Append __main__ block (uses base_location + filenames)
    script_content += _build_main_block(
        template_name, base_location or "", file1_val or "", file2_val or ""
    )

    dl_dir  = tempfile.mkdtemp(prefix="pplib_dl_")
    dl_path = os.path.join(dl_dir, safe_name)
    Path(dl_path).write_text(script_content, encoding="utf-8")

    info = TEMPLATE_CATALOG[template_name]
    where_note = f" &nbsp;|&nbsp; WHERE: <code>{where}</code>" if where else ""
    status_html = (
        f"<div style='padding:8px 14px;background:#eafaf1;border-left:4px solid #27ae60;border-radius:4px'>"
        f"✅ <b>Script generated:</b> <code>{safe_name}</code> &nbsp;|&nbsp; "
        f"{info['display_name']}{where_note}"
        f"</div>"
    )
    return status_html, script_content, dl_path


# ---------------------------------------------------------------------------
# Script runner  — exec() the generated script in an isolated namespace,
# call preprocess() with the specified input files, show output previews
# ---------------------------------------------------------------------------

def _resolve_full_path(base_location: str, filename: str) -> str:
    """
    Resolve a full file path from base_location + filename.
    - If filename is already absolute, return it as-is.
    - If filename has no directory, join with base_location.
    - base_location may be empty (user running without scanning a folder).
    """
    filename = (filename or "").strip()
    if not filename:
        return ""
    p = Path(filename)
    if p.is_absolute():
        return str(p)
    if base_location:
        return str(Path(base_location) / filename)
    return filename   # relative — will work if script is run from the right directory


def run_script(
    template_name: str,
    params_json: str,
    script_name: str,
    base_location: str,
    file1_val: str,
    file2_val: str,
    where_condition: str,
):
    """
    1. Re-generate the script content (no WHERE / __main__ injected — clean exec).
    2. exec() in an isolated namespace.
    3. Resolve filenames against base_location and call preprocess().
    4. Read every output file and return: status, file-list HTML, preview DF, download.
    """
    EMPTY = (
        "<p style='color:gray'>No results yet.</p>",
        "<p style='color:gray'></p>",
        pd.DataFrame(),
        None,
    )

    if not template_name:
        return ("<p style='color:red'>Select a template first.</p>",) + EMPTY[1:]

    # ── 1. Generate script content ────────────────────────────────────────
    try:
        params_dict = json.loads(params_json)
    except json.JSONDecodeError as exc:
        return (f"<p style='color:red'><b>Invalid JSON:</b> {exc}</p>",) + EMPTY[1:]
    try:
        gen_params = _params_json_to_generator_format(params_dict, template_name)
        gen_params = _inject_filename_placeholders(gen_params, template_name, file1_val, file2_val)
    except Exception as exc:
        return (f"<p style='color:red'><b>Parameter error:</b> {exc}</p>",) + EMPTY[1:]

    safe_name = ((script_name or "").strip() or f"{template_name}_preprocess") + ".py"
    if not safe_name.endswith(".py"):
        safe_name += ".py"

    with tempfile.TemporaryDirectory() as tmp_gen:
        try:
            gpath = generate_preprocessor(
                template_name, gen_params, safe_name, tmp_gen, _TEMPLATES_DIR,
            )
            script_content = Path(gpath).read_text(encoding="utf-8")
        except Exception as exc:
            return (f"<p style='color:red'><b>Generation failed:</b> {exc}</p>",) + EMPTY[1:]

    # Inject WHERE condition if set (before exec, so filter runs inside preprocess)
    where = (where_condition or "").strip()
    if where:
        try:
            script_content = _inject_where_condition(script_content, where)
        except Exception as exc:
            return (f"<p style='color:red'><b>WHERE injection failed:</b> {exc}</p>",) + EMPTY[1:]

    # ── 2. Execute script in isolated namespace ───────────────────────────
    ns: dict = {"__name__": "<pplib_run>"}
    try:
        exec(compile(script_content, safe_name, "exec"), ns)
    except Exception as exc:
        import traceback as _tb
        return (
            f"<p style='color:red'><b>Script load error:</b><br/><pre style='font-size:0.8em'>"
            f"{_tb.format_exc()}</pre></p>",
        ) + EMPTY[1:]

    preprocess_fn = ns.get("preprocess")
    if not preprocess_fn:
        return ("<p style='color:red'>preprocess() function not found in script.</p>",) + EMPTY[1:]

    # ── 2b. Redirect output to a temp dir when OUTPUT_DIR is empty ────────
    # Prevents PermissionError when the input folder is read-only (e.g. git
    # archive, OneDrive, network share). The generated script's OUTPUT_DIR
    # global is patched here — preprocess() reads it at call time from ns.
    if not (ns.get("OUTPUT_DIR") or "").strip():
        ns["OUTPUT_DIR"] = tempfile.mkdtemp(prefix="pplib_run_")

    # ── 3. Resolve input paths: join base_location + filename ────────────
    base = (base_location or "").strip()
    f1   = _resolve_full_path(base, file1_val or "")
    f2   = _resolve_full_path(base, file2_val or "")

    if not f1:
        return (
            "<p style='color:red'>No input file specified — select or type a <b>File 1</b> name.</p>",
        ) + EMPTY[1:]

    # ── 4. Call preprocess() — inspect actual signature to determine args ────
    import inspect as _inspect
    sig_params   = list(_inspect.signature(preprocess_fn).parameters.values())
    n_required   = sum(
        1 for p in sig_params
        if p.default is _inspect.Parameter.empty
        and p.kind not in (_inspect.Parameter.VAR_POSITIONAL, _inspect.Parameter.VAR_KEYWORD)
    )
    first_ann    = str(sig_params[0].annotation) if sig_params else ""
    first_is_list = (
        "list" in first_ann.lower()
        or (sig_params and sig_params[0].name in ("input_paths", "paths"))
    )

    try:
        if n_required == 1 and first_is_list:
            # preprocess(input_paths: list)
            if f2:
                path_list = [f1, f2]
            else:
                # multi: f1 might be comma-separated filenames
                names = [n.strip() for n in f1.split(",") if n.strip()]
                path_list = [_resolve_full_path(base, n) for n in names] if len(names) > 1 else [f1]
                if not path_list:
                    return (
                        "<p style='color:red'>No input files — fill File 1.</p>",
                    ) + EMPTY[1:]
            result = preprocess_fn(path_list)
        elif n_required >= 2:
            if not f2:
                return (
                    "<p style='color:red'>This template needs 2 input files — fill in <b>File 2</b>.</p>",
                ) + EMPTY[1:]
            result = preprocess_fn(f1, f2)
        else:
            # preprocess(input_path: str)
            result = preprocess_fn(f1)
    except Exception:
        import traceback as _tb
        return (
            f"<p style='color:red'><b>preprocess() raised an exception:</b>"
            f"<br/><pre style='font-size:0.8em;white-space:pre-wrap'>{_tb.format_exc()}</pre></p>",
        ) + EMPTY[1:]

    # ── 5. Collect output files ───────────────────────────────────────────
    result_path = Path(str(result))
    if result_path.is_file():
        output_files = [result_path]
    elif result_path.is_dir():
        output_files = sorted(
            f for f in result_path.iterdir()
            if f.is_file() and not f.name.startswith(".")
        )
    else:
        output_files = []

    if not output_files:
        return (
            "<p style='color:orange'>Script ran but no output files were found. "
            "Check the OUTPUT_DIR parameter.</p>",
        ) + EMPTY[1:]

    # ── 6. Build output summary HTML ─────────────────────────────────────
    info_rows = ""
    total_rows = 0
    for fpath in output_files:
        try:
            df_tmp = _sniff_load(str(fpath), max_rows=5)   # headers only for ncol
            ncol = len(df_tmp.columns)
            nrow = _count_rows_fast(str(fpath), df_tmp)
            if nrow < 0:
                nrow = "?"
        except Exception:
            nrow, ncol = "?", "?"
        if isinstance(nrow, int):
            total_rows += nrow
        size_kb = fpath.stat().st_size / 1024
        info_rows += (
            f"<tr>"
            f"<td style='padding:5px 10px;font-weight:600'>{fpath.name}</td>"
            f"<td style='padding:5px 10px;text-align:right'>"
            f"{nrow:,}" if isinstance(nrow, int) else f"{nrow}"
            f"</td>"
            f"<td style='padding:5px 10px;text-align:right'>{ncol}</td>"
            f"<td style='padding:5px 10px;text-align:right'>{size_kb:.1f} KB</td>"
            f"<td style='padding:5px 10px;color:#666;font-size:0.85em'>{fpath.parent}</td>"
            f"</tr>"
        )

    output_info_html = (
        "<table style='border-collapse:collapse;width:100%;font-size:0.9em'>"
        "<thead><tr style='background:#f0f0f0'>"
        "<th style='padding:5px 10px;text-align:left'>Output File</th>"
        "<th style='padding:5px 10px;text-align:right'>Rows</th>"
        "<th style='padding:5px 10px;text-align:right'>Cols</th>"
        "<th style='padding:5px 10px;text-align:right'>Size</th>"
        "<th style='padding:5px 10px;text-align:left'>Location</th>"
        "</tr></thead>"
        f"<tbody>{info_rows}</tbody></table>"
    )

    # ── 7. Preview first output file ─────────────────────────────────────
    try:
        preview_df = _sniff_load(str(output_files[0]), max_rows=25)
        # Truncate long strings so the Gradio JSON payload stays small
        for col in preview_df.select_dtypes(include="object").columns:
            preview_df[col] = preview_df[col].astype(str).str.slice(0, 120)
    except Exception:
        preview_df = pd.DataFrame()

    # ── 8. Package output files for download ─────────────────────────────
    if len(output_files) == 1:
        dl_path = str(output_files[0])
    else:
        dl_dir   = tempfile.mkdtemp(prefix="pplib_out_")
        zip_path = os.path.join(dl_dir, f"{template_name}_output.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for fpath in output_files:
                zf.write(str(fpath), fpath.name)
        dl_path = zip_path

    where_note = f" &nbsp;|&nbsp; WHERE: <code>{where}</code>" if where else ""
    run_status = (
        f"<div style='padding:8px 14px;background:#eafaf1;border-left:4px solid #27ae60;border-radius:4px'>"
        f"✅ <b>Run complete</b> &nbsp;|&nbsp; {len(output_files)} output file(s) &nbsp;|&nbsp; "
        f"{total_rows:,} total rows{where_note}"
        f"</div>"
    )
    return run_status, output_info_html, preview_df, dl_path


# ---------------------------------------------------------------------------
# Phase B helpers — presets, WHERE builder, validation, output-col preview
# ---------------------------------------------------------------------------

def _save_preset(template_name: str, params_json: str, where: str) -> str:
    """Serialize current config to a JSON file path for download."""
    data = {"template_name": template_name, "params_json": params_json, "where": where}
    tmp = tempfile.mkdtemp(prefix="pplib_preset_")
    path = os.path.join(tmp, f"{template_name}_preset.json")
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _load_preset(file_obj) -> tuple:
    """Load a preset JSON file; return (template_name, params_json, where)."""
    if file_obj is None:
        return None, "{}", ""
    try:
        content = Path(file_obj.name).read_text(encoding="utf-8")
        data = json.loads(content)
        return data.get("template_name"), data.get("params_json", "{}"), data.get("where", "")
    except Exception:
        return None, "{}", ""


def _build_where_from_rows(
    col1: str, op1: str, val1: str,
    col2: str, op2: str, val2: str, conn2: str,
    col3: str, op3: str, val3: str, conn3: str,
) -> str:
    """Convert visual WHERE builder rows to a pandas query() string."""
    def _clause(col: str, op: str, val: str) -> str:
        if not col or col == "(none)" or not val.strip():
            return ""
        val = val.strip()
        if op == "contains":
            return f"{col}.str.contains('{val}', na=False)"
        if op == "startswith":
            return f"{col}.str.startswith('{val}', na=False)"
        if op == "in":
            items = ", ".join(f"'{v.strip()}'" for v in val.split(","))
            return f"{col} in [{items}]"
        # Numeric or quoted string
        try:
            float(val)
            return f"{col} {op} {val}"
        except ValueError:
            return f"{col} {op} '{val}'"

    parts = []
    c1 = _clause(col1, op1, val1)
    if c1:
        parts.append(c1)
    c2 = _clause(col2, op2, val2)
    if c2:
        parts.append((conn2 or "and") + " " + c2)
    c3 = _clause(col3, op3, val3)
    if c3:
        parts.append((conn3 or "and") + " " + c3)
    return " ".join(parts)


def validate_params(
    template_name: str,
    params_json: str,
    file1: str,
    file2: str,
    file_data_json: str,
) -> str:
    """
    Run pre-flight checks on parameters. Returns HTML with warnings, or "" if all OK.
    """
    warnings: list[str] = []

    # 1. JSON parse check
    try:
        params = json.loads(params_json)
    except json.JSONDecodeError as exc:
        return (
            f"<div style='padding:8px 14px;background:#fff3cd;border-left:4px solid #f0ad4e;"
            f"border-radius:4px'><b>⚠ JSON Error:</b> {exc}</div>"
        )

    # 2. File check
    if not (file1 or "").strip():
        warnings.append("No input file specified — please select or type a File 1 name.")

    # 3. Column existence check (if we have scanned file data)
    try:
        file_data = json.loads(file_data_json) if file_data_json else {}
    except Exception:
        file_data = {}

    all_cols: set[str] = set()
    for entry in file_data.values():
        all_cols.update(entry.get("columns", []))

    col_params = ["JOIN_KEY", "SPLIT_COLUMN", "RANK_BY_COLUMN", "FILTER_COLUMN"]
    for pname in col_params:
        if pname in params and all_cols:
            val = params[pname]
            if val and val not in all_cols:
                warnings.append(
                    f"<b>{pname}</b> = '{val}' is not in the scanned columns — check the name."
                )

    list_col_params = ["KEY_COLUMNS", "JOIN_KEYS", "GROUP_BY_COLUMNS", "PARTITION_BY",
                       "COMPARE_COLUMNS", "COMMON_KEY_COLUMNS"]
    for pname in list_col_params:
        if pname in params and all_cols and isinstance(params[pname], list):
            for col in params[pname]:
                if col and col not in all_cols:
                    warnings.append(
                        f"<b>{pname}</b>: '{col}' is not in the scanned columns."
                    )

    if not warnings:
        return (
            "<div style='padding:8px 14px;background:#eafaf1;border-left:4px solid #27ae60;"
            "border-radius:4px'>✅ Parameters look good — ready to run.</div>"
        )
    items = "".join(f"<li>{w}</li>" for w in warnings)
    return (
        f"<div style='padding:8px 14px;background:#fff3cd;border-left:4px solid #f0ad4e;"
        f"border-radius:4px'><b>⚠ Warnings ({len(warnings)}):</b><ul>{items}</ul></div>"
    )


def _preview_output_columns(
    template_name: str, params_json: str, file1: str, file_data_json: str
) -> str:
    """
    Best-effort estimate of the output column list based on template config.
    Returns an HTML chip display. Reads only the scanned file metadata — no preprocess() call.
    """
    try:
        params = json.loads(params_json)
    except Exception:
        return "<p style='color:red'>Invalid JSON — fix parameters first.</p>"

    try:
        file_data = json.loads(file_data_json) if file_data_json else {}
    except Exception:
        file_data = {}

    # Get columns from scanned files
    left_cols  = file_data.get(file1, {}).get("columns", []) if file1 else []
    all_cols   = left_cols or []
    for e in file_data.values():
        for c in e.get("columns", []):
            if c not in all_cols:
                all_cols.append(c)

    # Template-specific estimation
    out_cols: list[str] = []
    if template_name in ("file_join_two", "file_join_multi_key", "file_denormalize",
                         "file_join_filter_agg"):
        out_cols = list(all_cols)  # simplified: union of all scanned cols
    elif template_name == "file_aggregate":
        gb = params.get("GROUP_BY_COLUMNS", [])
        agg = params.get("AGGREGATIONS", [])
        out_cols = list(gb) + [a.get("output_column", a.get("column", "?")) for a in agg if isinstance(a, dict)]
    elif template_name == "file_rename_columns":
        mapping = params.get("COLUMN_MAPPING", {})
        if params.get("DROP_UNMAPPED"):
            out_cols = list(mapping.values())
        else:
            out_cols = [mapping.get(c, c) for c in all_cols]
    elif template_name == "file_deduplicate":
        out_cols = list(all_cols)
    elif template_name == "file_cast_types":
        out_cols = list(all_cols)
    else:
        out_cols = list(all_cols)

    if not out_cols:
        return "<p style='color:gray'>No column info available — scan a folder in Tab 1 first.</p>"

    chips = "".join(
        f"<span style='display:inline-block;background:#e8f0fe;color:#1a6e9e;"
        f"border-radius:3px;padding:2px 8px;margin:2px 3px;font-family:monospace;"
        f"font-size:0.85em'>{c}</span>"
        for c in out_cols
    )
    return (
        f"<details open><summary style='cursor:pointer;font-weight:600'>"
        f"Estimated output columns ({len(out_cols)}) "
        f"<span style='font-weight:normal;color:#888'>— actual may vary</span></summary>"
        f"<div style='margin-top:6px'>{chips}</div></details>"
    )


def _lod_df_to_json(df_data, param_key: str) -> list:
    """Convert gr.Dataframe value (list of lists) to list-of-dicts for params JSON."""
    schema = _LOD_SCHEMAS.get(param_key, {})
    headers = schema.get("headers", [])
    result = []
    if df_data is None:
        return result
    # df_data can be a list of lists or a DataFrame
    if hasattr(df_data, "values"):
        rows = df_data.values.tolist()
    else:
        rows = df_data
    for row in rows:
        if not any(str(v).strip() for v in row):
            continue   # skip blank rows
        d: dict = {}
        for i, h in enumerate(headers):
            val = row[i] if i < len(row) else ""
            if h in ("values", "columns"):
                # Convert comma-separated string to list
                d[h] = [v.strip() for v in str(val).split(",") if v.strip()]
            else:
                d[h] = val
        result.append(d)
    return result


def _json_to_lod_df(params_json: str, param_key: str):
    """Extract list-of-dicts from params JSON and return as list-of-lists for gr.Dataframe."""
    schema = _LOD_SCHEMAS.get(param_key, {})
    headers = schema.get("headers", [])
    default_row = schema.get("default_row", [""] * len(headers))
    try:
        params = json.loads(params_json)
        lod = params.get(param_key, [])
        if not isinstance(lod, list) or not lod:
            return [default_row]
        rows = []
        for item in lod:
            if not isinstance(item, dict):
                continue
            row = []
            for h in headers:
                val = item.get(h, "")
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val)
                row.append(str(val))
            rows.append(row)
        return rows if rows else [default_row]
    except Exception:
        return [default_row]


def _merge_lod_into_params(params_json: str, param_key: str, df_data) -> str:
    """Update params_json with data from the interactive table editor."""
    try:
        params = json.loads(params_json)
    except Exception:
        params = {}
    params[param_key] = _lod_df_to_json(df_data, param_key)
    return json.dumps(params, indent=2)


# ---------------------------------------------------------------------------
# Step indicator HTML helper  (Phase A3)
# ---------------------------------------------------------------------------
_STEP_LABELS = ["① Scan Folder", "② Pick Template", "③ Set Parameters", "④ Generate / Run"]

def _step_indicator_html(active: int) -> str:
    parts = []
    for i, lbl in enumerate(_STEP_LABELS):
        if i == active:
            parts.append(
                f"<span style='font-weight:700;color:#1a6e9e;padding:4px 12px;"
                f"border-bottom:3px solid #1a6e9e'>{lbl}</span>"
            )
        else:
            parts.append(
                f"<span style='color:#aaa;padding:4px 12px'>{lbl}</span>"
            )
        if i < len(_STEP_LABELS) - 1:
            parts.append("<span style='color:#ccc;padding:0 4px'>→</span>")
    return (
        "<div style='display:flex;align-items:center;background:#f8f9fa;"
        "padding:8px 16px;border-radius:6px;margin-bottom:12px;flex-wrap:wrap'>"
        + "".join(parts) + "</div>"
    )


# ---------------------------------------------------------------------------
# Folder browser helper  (Phase A1)
# ---------------------------------------------------------------------------
def _browse_folder() -> str:
    """Open a native folder picker and return the selected path."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", True)
        path = filedialog.askdirectory(title="Select input folder")
        root.destroy()
        return path or ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Category filter helper  (Phase B1)
# ---------------------------------------------------------------------------
def _filter_template_choices(category: str) -> gr.update:
    keys = _TEMPLATE_CATEGORIES.get(category, _TEMPLATE_CATEGORIES["All"])
    choices = [(v["display_name"], k) for k, v in TEMPLATE_CATALOG.items() if k in keys]
    if not choices:
        choices = _TEMPLATE_CHOICES
    return gr.update(choices=choices, value=choices[0][1])


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------

def build_ui() -> gr.Blocks:
    # _hist.init_db()  # HISTORY_TAB — uncomment to re-enable

    with gr.Blocks(title="PrepKit — Preprocessing Script Library") as app:

        gr.Markdown("# PrepKit — Preprocessing Script Library\n"
                    "Generate a ready-to-use `preprocess()` script from **18 templates**.")

        # Step indicator (Phase A3)
        step_html    = gr.HTML(value=_step_indicator_html(0))
        step_state   = gr.State(0)

        # Shared state
        file_data_state     = gr.State("{}")
        base_location_state = gr.State("")
        pipeline_steps_state = gr.State([])   # Phase E

        with gr.Tabs():

            # ── Tab 1: Explore Files ──────────────────────────────────────────
            with gr.Tab("1 — Explore Files"):
                gr.Markdown(
                    "Enter your input folder path, or click **Browse** to pick one. "
                    "Maximum **10 files** per scan. Select a file to inspect columns and data."
                )

                # Folder path + Browse button (Phase A1)
                with gr.Row():
                    folder_path_box = gr.Textbox(
                        label="Input Folder Path",
                        placeholder="e.g.  C:/data/my_input_files",
                        interactive=True, scale=5,
                    )
                    browse_btn = gr.Button("📂 Browse", scale=1)
                    scan_btn   = gr.Button("Scan Folder", variant="primary", scale=1)

                scan_status_html = gr.HTML(
                    value="<p style='color:gray'>Enter a folder path and click <b>Scan Folder</b>.</p>"
                )

                file_selector = gr.Dropdown(label="Select a file to explore", choices=[], interactive=True)

                # Sheet picker (Phase A5) — visible only for Excel
                sheet_picker = gr.Dropdown(label="Sheet (Excel only)", choices=[], visible=False, interactive=True)

                file_info_html = gr.HTML()

                gr.Markdown("**Data Preview (first 10 rows)**")
                preview_df = gr.Dataframe(interactive=False, wrap=True)

                # Column profile (Phase A4)
                with gr.Accordion("📊 Column Profile", open=False) as profile_accordion:
                    profile_df_comp = gr.Dataframe(interactive=False, wrap=False)

            # ── Tab 2: Generate Script ────────────────────────────────────────
            with gr.Tab("2 — Generate Script"):

                # Column reference + column picker (C2)
                gr.Markdown("### All Columns — use these exact names in your parameters")
                cols_display = gr.HTML(
                    value="<p style='color:gray'>Scan a folder in Tab 1 first.</p>"
                )
                gr.Markdown("---")

                # Category filter (Phase B1)
                category_radio = gr.Radio(
                    choices=list(_TEMPLATE_CATEGORIES.keys()),
                    value="All", label="What do you want to do?", interactive=True,
                )

                template_dropdown  = gr.Dropdown(
                    label="Template",
                    choices=_TEMPLATE_CHOICES,
                    value=_TEMPLATE_CHOICES[0][1],
                    interactive=True,
                )
                template_desc_html = gr.HTML()

                gr.Markdown("### Input File Name(s)")
                with gr.Row():
                    file1_dropdown = gr.Dropdown(
                        label="File 1 — select from scanned folder",
                        choices=["(none)"], value="(none)", interactive=True, scale=2,
                    )
                    file1_text = gr.Textbox(
                        label="File 1 name",
                        placeholder="e.g.  sales.csv",
                        interactive=True, scale=3,
                    )

                with gr.Row(visible=False) as file2_row:
                    file2_dropdown = gr.Dropdown(
                        label="File 2 — select from scanned folder",
                        choices=["(none)"], value="(none)", interactive=True, scale=2,
                    )
                    file2_text = gr.Textbox(
                        label="File 2 name",
                        placeholder="e.g.  reference.csv",
                        interactive=True, scale=3,
                    )

                # WHERE condition (Phase B3)
                gr.Markdown("### WHERE Condition (optional pre-filter)")
                with gr.Row():
                    where_box = gr.Textbox(
                        label="WHERE — pandas query() syntax, leave blank for no filter",
                        placeholder="e.g.  status == 'ACTIVE'   or   amount > 0",
                        interactive=True, scale=4,
                    )
                    gr.HTML(
                        "<div style='font-size:0.82em;color:#555;padding-top:6px'>"
                        "Strings: <code>col == 'VALUE'</code><br/>"
                        "Numbers: <code>amount &gt; 100</code><br/>"
                        "Multiple: <code>a == 'X' and b &gt; 0</code>"
                        "</div>", scale=2,
                    )

                # Visual WHERE builder (Phase B3)
                with gr.Accordion("🔍 Build WHERE condition visually", open=False):
                    all_ops = _WHERE_OPS
                    with gr.Row():
                        wc1 = gr.Dropdown(label="Column", choices=["(none)"], value="(none)", scale=2, interactive=True)
                        wo1 = gr.Dropdown(label="Operator", choices=all_ops, value="==", scale=1, interactive=True)
                        wv1 = gr.Textbox(label="Value", placeholder="e.g. ACTIVE", scale=2, interactive=True)
                    with gr.Row():
                        wconn2 = gr.Dropdown(label="", choices=["and","or"], value="and", scale=1, interactive=True)
                        wc2 = gr.Dropdown(label="Column", choices=["(none)"], value="(none)", scale=2, interactive=True)
                        wo2 = gr.Dropdown(label="Operator", choices=all_ops, value="==", scale=1, interactive=True)
                        wv2 = gr.Textbox(label="Value", placeholder="", scale=2, interactive=True)
                    with gr.Row():
                        wconn3 = gr.Dropdown(label="", choices=["and","or"], value="and", scale=1, interactive=True)
                        wc3 = gr.Dropdown(label="Column", choices=["(none)"], value="(none)", scale=2, interactive=True)
                        wo3 = gr.Dropdown(label="Operator", choices=all_ops, value="==", scale=1, interactive=True)
                        wv3 = gr.Textbox(label="Value", placeholder="", scale=2, interactive=True)
                    where_build_btn = gr.Button("→ Apply to WHERE box", variant="secondary")

                # Preset save/load (Phase B2)
                with gr.Accordion("💾 Save / Load Presets", open=False):
                    with gr.Row():
                        save_preset_btn  = gr.Button("💾 Save current config as preset", scale=2)
                        preset_dl_file   = gr.File(label="Download preset", interactive=False, scale=2)
                    with gr.Row():
                        load_preset_file = gr.File(label="Load preset (.json)", file_types=[".json"],
                                                   interactive=True, scale=2)
                        load_preset_btn  = gr.Button("Load →", scale=1)

                # Parameters (Phase C1 — JSON + visual table editor)
                gr.Markdown("### Configuration Parameters")
                with gr.Row():
                    with gr.Column(scale=3):
                        params_json_box = gr.Textbox(
                            label="Parameters (JSON)",
                            lines=18, max_lines=40, placeholder="{}",
                        )
                    with gr.Column(scale=2):
                        param_help_html = gr.HTML()

                # Visual table editor for list-of-dicts params
                with gr.Accordion("📋 Visual Table Editor (for list parameters)", open=False) as lod_accordion:
                    lod_label_html = gr.HTML("<p style='color:gray'>Select a template with list parameters.</p>")
                    lod_editor = gr.Dataframe(
                        headers=["col1", "col2"], datatype=["str","str"],
                        interactive=True, wrap=True, row_count=(3,"dynamic"),
                    )
                    with gr.Row():
                        lod_apply_btn  = gr.Button("Apply table to params JSON →", variant="secondary")
                        lod_add_btn    = gr.Button("＋ Add Row")
                    lod_param_key_state = gr.State("")   # which param key the editor is for

                gr.Markdown("---")

                # Output column preview (Phase B5)
                with gr.Row():
                    preview_cols_btn = gr.Button("🔎 Preview Output Columns", scale=1)
                    col_preview_html = gr.HTML(scale=3)

                # Validation panel (Phase B4)
                validation_html = gr.HTML()

                # Generate & Run
                with gr.Row():
                    script_name_box = gr.Textbox(
                        label="Output script filename (optional)",
                        placeholder="e.g.  my_filter.py", scale=3,
                    )
                    generate_btn = gr.Button("Generate Script", variant="primary", scale=1)
                    run_btn      = gr.Button("▶ Run Script", variant="secondary", scale=1)

                gr.Markdown("---")

                # Run Results
                gr.Markdown("#### Run Results")
                run_status_html  = gr.HTML(value="<p style='color:gray'>Click <b>Run Script</b> to execute.</p>")
                output_info_html = gr.HTML()
                output_preview   = gr.Dataframe(label="Output preview (first 25 rows)", interactive=False, wrap=False)
                output_download  = gr.File(label="Download output file(s)", interactive=False)

                gr.Markdown("---")

                # Generated Script
                gr.Markdown("#### Generated Script")
                gen_status_html = gr.HTML()
                script_preview  = gr.Textbox(label="Script preview", lines=18, max_lines=60, interactive=False)
                download_file   = gr.File(label="Download .py script", interactive=False)

                gr.Markdown("---")

                # ── Phase E: Pipeline Builder ─────────────────────────────────
                with gr.Accordion("🔗 Pipeline Mode — chain multiple steps", open=False):
                    gr.Markdown(
                        "Configure a template above, then click **＋ Add Step** to add it to the pipeline. "
                        "Use `__prev__` as File 1 to chain from the previous step's output."
                    )
                    pipeline_display = gr.JSON(label="Pipeline steps", value=[])
                    with gr.Row():
                        pipeline_add_btn   = gr.Button("＋ Add current step", scale=1)
                        pipeline_clear_btn = gr.Button("🗑 Clear pipeline", scale=1)
                        pipeline_run_btn   = gr.Button("▶ Run Pipeline", variant="primary", scale=1)
                    pipeline_status_html = gr.HTML()
                    pipeline_preview_df  = gr.Dataframe(
                        label="Last step output preview", interactive=False, wrap=False
                    )

            # ── Tab 3: History ────────────────────────────────────────────────
            # HISTORY_TAB — uncomment the block below to re-enable
            # with gr.Tab("3 — History"):
            #     gr.Markdown("### Run History\nEvery Generate and Run action is logged here.")
            #     with gr.Row():
            #         hist_refresh_btn = gr.Button("🔄 Refresh", scale=1)
            #         hist_clear_btn   = gr.Button("🗑 Clear All History", scale=1)
            #     hist_table = gr.Dataframe(
            #         value=_hist.history_dataframe(),
            #         interactive=False, wrap=False,
            #         label="Last 100 runs (newest first)",
            #     )
            #     gr.Markdown("**Selected run detail** — enter an ID from the table above:")
            #     with gr.Row():
            #         hist_id_box = gr.Number(label="Run ID", precision=0, scale=1)
            #         hist_load_btn    = gr.Button("Re-load into Tab 2", scale=1)
            #         hist_dl_btn      = gr.Button("Download script", scale=1)
            #         hist_del_btn     = gr.Button("🗑 Delete this run", scale=1)
            #     hist_detail_html   = gr.HTML()
            #     hist_script_box    = gr.Textbox(label="Script content", lines=12, interactive=False)
            #     hist_dl_file       = gr.File(label="Script download", interactive=False)

        # ════════════════════════════════════════════════════════════════════
        # Event wiring
        # ════════════════════════════════════════════════════════════════════

        # ── Browse button (A1) ───────────────────────────────────────────
        browse_btn.click(fn=_browse_folder, inputs=[], outputs=[folder_path_box])

        # ── Scan folder ──────────────────────────────────────────────────
        def _scan_and_update(folder_path, template_name, file1_val, params_json):
            status, sel_upd, fdata, cols_html, fn_upd, base_loc = scan_folder(folder_path)
            new_params = _auto_fill_output_params(params_json, template_name, file1_val, base_loc)
            # Populate WHERE builder column dropdowns
            try:
                all_cols = _get_all_columns(fdata)
            except Exception:
                all_cols = []
            col_choices = ["(none)"] + all_cols
            return (
                status, sel_upd, fdata, cols_html,
                fn_upd, fn_upd,
                base_loc, new_params,
                _step_indicator_html(1), 1,
                gr.update(choices=col_choices, value="(none)"),
                gr.update(choices=col_choices, value="(none)"),
                gr.update(choices=col_choices, value="(none)"),
            )

        scan_btn.click(
            fn=_scan_and_update,
            inputs=[folder_path_box, template_dropdown, file1_text, params_json_box],
            outputs=[scan_status_html, file_selector, file_data_state, cols_display,
                     file1_dropdown, file2_dropdown,
                     base_location_state, params_json_box,
                     step_html, step_state,
                     wc1, wc2, wc3],
        )

        # ── File selection in Tab 1 ───────────────────────────────────────
        file_selector.change(
            fn=show_file_detail,
            inputs=[file_selector, file_data_state, sheet_picker],
            outputs=[file_info_html, preview_df, profile_df_comp,
                     sheet_picker, profile_accordion],
        )

        sheet_picker.change(
            fn=show_file_detail,
            inputs=[file_selector, file_data_state, sheet_picker],
            outputs=[file_info_html, preview_df, profile_df_comp,
                     sheet_picker, profile_accordion],
        )

        # ── File name dropdowns → text boxes ─────────────────────────────
        def _pick_and_autofill(dropdown_val, params_json, template_name, base_loc):
            fname = dropdown_val if dropdown_val and dropdown_val != "(none)" else ""
            new_params = _auto_fill_output_params(params_json, template_name, fname, base_loc)
            return fname, new_params

        def _pick_filename(dropdown_val):
            return "" if not dropdown_val or dropdown_val == "(none)" else dropdown_val

        file1_dropdown.change(
            fn=_pick_and_autofill,
            inputs=[file1_dropdown, params_json_box, template_dropdown, base_location_state],
            outputs=[file1_text, params_json_box],
        )
        file2_dropdown.change(fn=_pick_filename, inputs=[file2_dropdown], outputs=[file2_text])

        # ── Category filter (B1) ─────────────────────────────────────────
        category_radio.change(
            fn=_filter_template_choices,
            inputs=[category_radio],
            outputs=[template_dropdown],
        )

        # ── Template change ───────────────────────────────────────────────
        def _on_template_change(template_name, file1_val, base_loc):
            desc, params, help_html, lbl1, vis1, lbl2, vis2 = update_template_ui(template_name)
            params = _auto_fill_output_params(params, template_name, file1_val, base_loc)

            # LOD editor setup (C1)
            lod_param = _TEMPLATE_LOD_PARAM.get(template_name, "")
            if lod_param and lod_param in _LOD_SCHEMAS:
                schema = _LOD_SCHEMAS[lod_param]
                lod_rows = _json_to_lod_df(params, lod_param)
                lod_upd = gr.update(
                    headers=schema["headers"],
                    value=lod_rows,
                    visible=True,
                )
                lod_label = f"<b>{schema['label']}</b> — edit rows below, then click Apply."
            else:
                lod_upd   = gr.update(visible=False)
                lod_label = "<p style='color:gray'>This template has no list parameters to edit visually.</p>"

            return (
                desc, params, help_html,
                gr.update(label=f"{lbl1} — select from scanned folder"),  # file1_dropdown
                gr.update(label=lbl1),                                     # file1_text
                gr.update(label=f"{lbl2} — select from scanned folder"),  # file2_dropdown
                gr.update(label=lbl2),                                     # file2_text
                vis2,   # file2_row — vis2 is already gr.update(visible=...), don't double-wrap
                lod_upd, lod_label, lod_param,
                _step_indicator_html(2), 2,
            )

        template_dropdown.change(
            fn=_on_template_change,
            inputs=[template_dropdown, file1_text, base_location_state],
            outputs=[template_desc_html, params_json_box, param_help_html,
                     file1_dropdown, file1_text, file2_dropdown, file2_text, file2_row,
                     lod_editor, lod_label_html, lod_param_key_state,
                     step_html, step_state],
        )

        # ── LOD editor apply (C1) ─────────────────────────────────────────
        lod_apply_btn.click(
            fn=_merge_lod_into_params,
            inputs=[params_json_box, lod_param_key_state, lod_editor],
            outputs=[params_json_box],
        )

        def _lod_add_row(current_df, param_key):
            """Append a blank default row to the LOD editor."""
            schema = _LOD_SCHEMAS.get(param_key, {})
            default_row = schema.get("default_row", [])
            if hasattr(current_df, "values"):
                rows = current_df.values.tolist()
            else:
                rows = list(current_df) if current_df else []
            rows.append(default_row)
            return rows

        lod_add_btn.click(
            fn=_lod_add_row,
            inputs=[lod_editor, lod_param_key_state],
            outputs=[lod_editor],
        )

        # ── WHERE visual builder (B3) ─────────────────────────────────────
        where_build_btn.click(
            fn=_build_where_from_rows,
            inputs=[wc1, wo1, wv1, wc2, wo2, wv2, wconn2, wc3, wo3, wv3, wconn3],
            outputs=[where_box],
        )

        # ── Preset save/load (B2) ─────────────────────────────────────────
        save_preset_btn.click(
            fn=_save_preset,
            inputs=[template_dropdown, params_json_box, where_box],
            outputs=[preset_dl_file],
        )

        def _do_load_preset(file_obj):
            tname, params, where = _load_preset(file_obj)
            if tname and tname in TEMPLATE_CATALOG:
                info = TEMPLATE_CATALOG[tname]
                desc_html = (
                    f"<div style='padding:8px 14px;background:#f8f9fa;"
                    f"border-left:4px solid #1a6e9e;border-radius:4px'>"
                    f"<b>{info['display_name']}</b></div>"
                )
                return tname, params, where, desc_html
            return tname, params, where, ""

        load_preset_btn.click(
            fn=_do_load_preset,
            inputs=[load_preset_file],
            outputs=[template_dropdown, params_json_box, where_box, template_desc_html],
        )

        # ── Output column preview (B5) ────────────────────────────────────
        preview_cols_btn.click(
            fn=_preview_output_columns,
            inputs=[template_dropdown, params_json_box, file1_text, file_data_state],
            outputs=[col_preview_html],
        )

        # ── Validation (B4) — fires before Generate/Run via a wrapper ────
        def _validate_then_generate(template_name, params_json, script_name,
                                    base_loc, file1, file2, where, file_data_json):
            val_html = validate_params(template_name, params_json, file1, file2, file_data_json)
            gen_result = generate_script(template_name, params_json, script_name,
                                         base_loc, file1, file2, where)
            # HISTORY_TAB — uncomment to re-enable history logging
            # status_ok = "ok" if "✅" in (gen_result[0] or "") else "error"
            # _hist.log_run(
            #     template_name=template_name,
            #     display_name=TEMPLATE_CATALOG.get(template_name, {}).get("display_name", template_name),
            #     params_json=params_json,
            #     script_name=(script_name or template_name) + ".py",
            #     action="generate",
            #     status=status_ok,
            #     output_summary=gen_result[0] or "",
            #     script_content=gen_result[1] or "",
            # )
            return (val_html,) + gen_result + (_step_indicator_html(3), 3)

        generate_btn.click(
            fn=_validate_then_generate,
            inputs=[template_dropdown, params_json_box, script_name_box,
                    base_location_state, file1_text, file2_text, where_box,
                    file_data_state],
            outputs=[validation_html, gen_status_html, script_preview, download_file,
                     step_html, step_state],
        )

        def _validate_then_run(template_name, params_json, script_name,
                               base_loc, file1, file2, where, file_data_json):
            val_html = validate_params(template_name, params_json, file1, file2, file_data_json)
            run_result = run_script(template_name, params_json, script_name,
                                    base_loc, file1, file2, where)
            # HISTORY_TAB — uncomment to re-enable history logging
            # status_ok = "ok" if "✅" in (run_result[0] or "") else "error"
            # _hist.log_run(
            #     template_name=template_name,
            #     display_name=TEMPLATE_CATALOG.get(template_name, {}).get("display_name", template_name),
            #     params_json=params_json,
            #     script_name=(script_name or template_name) + ".py",
            #     action="run",
            #     status=status_ok,
            #     output_summary=run_result[0] or "",
            #     script_content="",
            # )
            return (val_html,) + run_result + (_step_indicator_html(3), 3)

        run_btn.click(
            fn=_validate_then_run,
            inputs=[template_dropdown, params_json_box, script_name_box,
                    base_location_state, file1_text, file2_text, where_box,
                    file_data_state],
            outputs=[validation_html, run_status_html, output_info_html,
                     output_preview, output_download,
                     step_html, step_state],
        )

        # ── Pipeline (Phase E) ────────────────────────────────────────────
        def _add_pipeline_step(steps, template_name, params_json, file1, file2):
            try:
                params = json.loads(params_json)
            except Exception:
                params = {}
            step = {"template": template_name, "params": params,
                    "file1": file1 or "", "file2": file2 or ""}
            steps = list(steps) + [step]
            return steps, steps

        pipeline_add_btn.click(
            fn=_add_pipeline_step,
            inputs=[pipeline_steps_state, template_dropdown,
                    params_json_box, file1_text, file2_text],
            outputs=[pipeline_steps_state, pipeline_display],
        )

        pipeline_clear_btn.click(
            fn=lambda: ([], []),
            inputs=[],
            outputs=[pipeline_steps_state, pipeline_display],
        )

        def _run_pipeline(steps, base_loc):
            if not steps:
                return ("<p style='color:orange'>No pipeline steps — add steps first.</p>",
                        pd.DataFrame())
            results = _pipe.run_pipeline(steps, base_loc, _TEMPLATES_DIR)
            html = _pipe.pipeline_summary_html(results)
            last_ok = next((r for r in reversed(results) if r["status"] == "ok"), None)
            preview = last_ok["preview_df"] if last_ok else pd.DataFrame()
            return html, preview

        pipeline_run_btn.click(
            fn=_run_pipeline,
            inputs=[pipeline_steps_state, base_location_state],
            outputs=[pipeline_status_html, pipeline_preview_df],
        )

        # ── History tab (Phase D) — HISTORY_TAB — uncomment to re-enable ──
        # hist_refresh_btn.click(
        #     fn=lambda: _hist.history_dataframe(),
        #     inputs=[], outputs=[hist_table],
        # )
        # hist_clear_btn.click(
        #     fn=lambda: (_hist.clear_history(), _hist.history_dataframe())[1],
        #     inputs=[], outputs=[hist_table],
        # )
        # def _hist_load_detail(run_id):
        #     if not run_id:
        #         return "<p style='color:gray'>Enter a Run ID above.</p>", ""
        #     run = _hist.get_run(int(run_id))
        #     if not run:
        #         return "<p style='color:red'>Run not found.</p>", ""
        #     html = (
        #         f"<div style='padding:8px 14px;background:#f8f9fa;"
        #         f"border-left:4px solid #1a6e9e;border-radius:4px'>"
        #         f"<b>ID {run['id']}</b> | {run['timestamp']} | "
        #         f"{run['action']} | {run['display_name']} | "
        #         f"<b>{run['status']}</b><br/>"
        #         f"<small>{run['output_summary'][:200]}</small></div>"
        #     )
        #     return html, run.get("script_content", "")
        # hist_id_box.change(
        #     fn=_hist_load_detail,
        #     inputs=[hist_id_box],
        #     outputs=[hist_detail_html, hist_script_box],
        # )
        # def _hist_reload(run_id):
        #     if not run_id:
        #         return None, "{}", ""
        #     run = _hist.get_run(int(run_id))
        #     if not run:
        #         return None, "{}", ""
        #     return run["template_name"], run["params_json"], ""
        # hist_load_btn.click(
        #     fn=_hist_reload,
        #     inputs=[hist_id_box],
        #     outputs=[template_dropdown, params_json_box, where_box],
        # )
        # def _hist_dl(run_id):
        #     if not run_id:
        #         return None
        #     run = _hist.get_run(int(run_id))
        #     if not run or not run.get("script_content"):
        #         return None
        #     tmp = tempfile.mkdtemp(prefix="pplib_hist_")
        #     path = os.path.join(tmp, run["script_name"])
        #     Path(path).write_text(run["script_content"], encoding="utf-8")
        #     return path
        # hist_dl_btn.click(fn=_hist_dl, inputs=[hist_id_box], outputs=[hist_dl_file])
        # def _hist_del(run_id):
        #     if run_id:
        #         _hist.delete_run(int(run_id))
        #     return _hist.history_dataframe()
        # hist_del_btn.click(fn=_hist_del, inputs=[hist_id_box], outputs=[hist_table])

        # ── Startup load ──────────────────────────────────────────────────
        app.load(
            fn=lambda t: update_template_ui(t)[:3],
            inputs=[template_dropdown],
            outputs=[template_desc_html, params_json_box, param_help_html],
        )

    try:
        app.queue(default_concurrency_limit=4)
    except Exception:
        pass
    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Preprocessing Script Library — Gradio UI")
    parser.add_argument("--port",  type=int, default=7867)
    parser.add_argument("--host",  type=str, default="127.0.0.1")
    parser.add_argument("--share", action="store_true")
    args = parser.parse_args()
    build_ui().launch(server_name=args.host, server_port=args.port, share=args.share,
                      max_threads=40, theme=gr.themes.Soft())
