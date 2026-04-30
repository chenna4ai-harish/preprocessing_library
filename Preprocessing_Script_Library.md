# Data Preprocessing Script Library & Template Generator
### Comprehensive Technical Documentation
**Version 1.1 | Generic | Domain-Agnostic**  
**Generated: April 2026 | Updated: April 2026 | CONFIDENTIAL — INTERNAL USE ONLY**

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Overview](#2-system-overview)
3. [Placeholder Syntax](#3-placeholder-syntax)
4. [Generator Function Interface](#4-generator-function-interface)
5. [Directory Structure](#5-directory-structure)
6. [Preprocessing Scenarios & Templates](#6-preprocessing-scenarios--templates)
   - [PS-01 File Detection & Auto-Loading](#ps-01-file-detection--auto-loading)
   - [PS-02 File Union](#ps-02-file-union-stack-multiple-files-into-one)
   - [PS-03 Two-File Join](#ps-03-two-file-join)
   - [PS-04 Multi-File Join](#ps-04-multi-file-join-chain-three-or-more-files)
   - [PS-05 Multi-Key Join](#ps-05-multi-key-join-composite-key)
   - [PS-06 Denormalization](#ps-06-denormalization-flatten-master-detail)
   - [PS-07 Column-Value Split](#ps-07-column-value-split-by-cardinality)
   - [PS-08 Row Filter to Files](#ps-08-row-filter-to-files)
   - [PS-09 Vertical Column Split](#ps-09-vertical-column-split-wide-to-narrow)
   - [PS-10 Deduplication](#ps-10-deduplication)
   - [PS-11 Column Renaming](#ps-11-column-renaming--mapping)
   - [PS-12 Null Value Handling](#ps-12-null--missing-value-handling)
   - [PS-13 Data Type Casting](#ps-13-data-type-casting--standardisation)
   - [PS-14 Aggregation & Grouping](#ps-14-aggregation--grouping)
   - [PS-15 Incremental Delta Load](#ps-15-incremental--delta-load)
   - [PS-16 Rank Filter](#ps-16-rank-filter-window-rank-within-groups)
   - [PS-17 Filter by Value List](#ps-17-filter-by-value-list)
7. [Usage Examples](#7-usage-examples)
8. [Supported File Formats](#8-supported-file-formats)
9. [Output Structure](#9-output-structure)
10. [Integration with Ingestion Platform](#10-integration-with-ingestion-platform)
11. [Gradio UI](#11-gradio-ui-script-generator)

---

## 1. Executive Summary

The **Data Preprocessing Script Library** is a template-driven code generation system for building file preprocessing scripts in a data engineering pipeline. Instead of writing each preprocessing script from scratch, an engineer:

1. Calls the single **`generate_preprocessor()`** function
2. Passes the **template name** and **parameters** for that preprocessing operation
3. The generator reads the corresponding **template file**, replaces all **placeholders** with the provided parameter values
4. A ready-to-use **Python script** is written to disk — containing a single `preprocess()` function

Every generated script follows the **same contract**:

```python
def preprocess(input_path: str) -> str:
    ...
    return output_path
```

or for multi-file operations:

```python
def preprocess(input_paths: list) -> str:
    ...
    return output_path
```

Some templates accept **optional keyword arguments** that extend the base contract without breaking it. For example PS-02 accepts an optional `output_columns` parameter to enforce a specific output schema:

```python
def preprocess(input_paths: list, output_columns=None) -> str:
    ...
    return output_path
```

The ingestion platform can call all scripts uniformly via `preprocess(input_path)` or `preprocess(input_paths)`. Optional parameters are only used when explicitly passed.

No LLM is involved. The system uses **pure string placeholder replacement** — templates are static `.py` files with `{{PLACEHOLDER}}` tokens that get substituted at generation time.

---

## 2. System Overview

### 2.1 How It Works

```
Engineer calls generate_preprocessor()
         │
         ▼
Reads template file from templates/
         │
         ▼
Replaces {{PLACEHOLDERS}} with passed parameters
         │
         ▼
Writes generated .py file to output location
         │
         ▼
Generated script has one function: preprocess(input_path) -> str
         │
         ▼
Ingestion platform calls preprocess() on input files
```

### 2.2 Key Design Principles

| Principle | Description |
|---|---|
| Single function contract | Every generated script exposes exactly one function: `preprocess()` |
| No LLM dependency | Pure string replacement — no AI, no API calls needed to generate scripts |
| Template-driven | All logic lives in template files; generator only substitutes values |
| Plug-and-play | Generated scripts can be dropped into any pipeline that calls `preprocess()` |
| Format-agnostic | All scripts auto-detect file format (CSV, XLSX, JSON, ZIP, etc.) |
| Self-contained | Each generated script has all parameters baked in — no external config needed at runtime |

### 2.3 Script Summary

| ID | Template Name | Function Signature | Operation |
|---|---|---|---|
| PS-01 | `file_detect_load` | `preprocess(input_path: str)` | Auto-detect and load any file |
| PS-02 | `file_union` | `preprocess(input_paths: list, output_columns=None)` | Stack multiple files into one |
| PS-03 | `file_join_two` | `preprocess(input_paths: list)` | Join two files on a key column |
| PS-04 | `file_join_multi` | `preprocess(input_paths: list)` | Chain-join three or more files |
| PS-05 | `file_join_multi_key` | `preprocess(input_paths: list)` | Join on composite (multi-column) key |
| PS-06 | `file_denormalize` | `preprocess(input_paths: list)` | Flatten master-detail into one file |
| PS-07 | `file_split_by_value` | `preprocess(input_path: str)` | Split file by column cardinality |
| PS-08 | `file_filter_to_files` | `preprocess(input_path: str)` | Filter rows to separate output files |
| PS-09 | `file_split_columns` | `preprocess(input_path: str)` | Split wide file into narrow files |
| PS-10 | `file_deduplicate` | `preprocess(input_path: str)` | Remove duplicate rows |
| PS-11 | `file_rename_columns` | `preprocess(input_path: str)` | Rename columns via mapping |
| PS-12 | `file_handle_nulls` | `preprocess(input_path: str)` | Handle null/missing values |
| PS-13 | `file_cast_types` | `preprocess(input_path: str)` | Cast and standardise data types |
| PS-14 | `file_aggregate` | `preprocess(input_path: str)` | Group by and aggregate |
| PS-15 | `file_delta_load` | `preprocess(input_paths: list)` | Extract new/changed records only |
| PS-16 | `file_rank_filter` | `preprocess(input_path: str)` | Rank rows within groups, keep top-N |
| PS-17 | `file_filter_by_values` | `preprocess(input_path: str)` | Filter by value lists, remainder to others file |

---

## 3. Placeholder Syntax

All placeholders in template files use double curly brace syntax:

```
{{PLACEHOLDER_NAME}}
```

### 3.1 Placeholder Rules

- Placeholder names are always **UPPERCASE with underscores**
- Placeholders appear **inside the template `.py` file** as Python string values or constants
- The generator performs a **simple string replace** — `template_content.replace("{{PLACEHOLDER}}", value)`
- Placeholders can appear **multiple times** in the same template — all occurrences are replaced
- If a placeholder is not provided, the generator raises a `MissingParameterError`

### 3.2 Example — Placeholder in Template

```python
# Inside template file: file_split_by_value_template.py

SPLIT_COLUMN = "{{SPLIT_COLUMN}}"
OUTPUT_DIR   = "{{OUTPUT_DIR}}"
OUTPUT_FORMAT = "{{OUTPUT_FORMAT}}"
```

After generation with `split_column="Status", output_dir="./output"`:

```python
# Inside generated file: split_status_preprocessor.py

SPLIT_COLUMN  = "Status"
OUTPUT_DIR    = "./output"
OUTPUT_FORMAT = "csv"
```

---

## 4. Generator Function Interface

### 4.1 Main Generator Function

```python
def generate_preprocessor(
    template_name: str,
    parameters: dict,
    output_script_name: str | None = None,
    output_dir: str = "./generated_scripts",
    templates_dir: str = "./templates"
) -> str:
    """
    Reads a preprocessing template file, replaces all {{PLACEHOLDERS}}
    with values from the parameters dict, and writes the generated
    Python script to output_dir.

    Args:
        template_name     (str):  Template identifier e.g. 'file_split_by_value'
        parameters        (dict): Key-value pairs matching {{PLACEHOLDERS}} in the template
        output_script_name (str): Optional custom name for the output .py file
        output_dir        (str):  Folder where the generated script is saved
        templates_dir     (str):  Folder containing all template .py files

    Returns:
        str: Full path to the generated Python script

    Raises:
        TemplateNotFoundError:   If template_name does not match any template file
        MissingParameterError:   If a {{PLACEHOLDER}} in the template has no matching key in parameters
        OutputWriteError:        If the generated script cannot be written to output_dir
    """
```

### 4.2 Template File Naming Convention

Each template file is named:

```
{template_name}_template.py
```

Examples:
- `file_split_by_value_template.py`
- `file_union_template.py`
- `file_join_two_template.py`

### 4.3 Generated Script Naming Convention

If `output_script_name` is not provided, the generator creates the filename as:

```
{template_name}_{timestamp}.py
```

Example: `file_split_by_value_20260429_143822.py`

### 4.4 Error Handling

| Error | When Raised |
|---|---|
| `TemplateNotFoundError` | Template file not found in `templates_dir` |
| `MissingParameterError` | A `{{PLACEHOLDER}}` in template has no matching key in `parameters` dict |
| `ExtraParameterWarning` | A key in `parameters` has no matching `{{PLACEHOLDER}}` in template (warning only, not error) |
| `OutputWriteError` | Output directory does not exist or is not writable |

---

## 5. Directory Structure

```
(repo root)/
│
├── gradio_app.py                 ← Optional Gradio UI entry point
├── requirements.txt              ← Python package dependencies
│
└── preprocessing_library/
    │
    ├── exceptions.py             ← Custom error types (TemplateNotFoundError etc.)
    ├── generator.py              ← Main generate_preprocessor() function
    ├── template_catalog.json     ← Drives Gradio UI: display names, descriptions, parameter help
    │
    ├── templates/                ← 17 template files (one per scenario)
    │   ├── file_detect_load_template.py
    │   ├── file_union_template.py
    │   ├── file_join_two_template.py
    │   ├── file_join_multi_template.py
    │   ├── file_join_multi_key_template.py
    │   ├── file_denormalize_template.py
    │   ├── file_split_by_value_template.py
    │   ├── file_filter_to_files_template.py
    │   ├── file_split_columns_template.py
    │   ├── file_deduplicate_template.py
    │   ├── file_rename_columns_template.py
    │   ├── file_handle_nulls_template.py
    │   ├── file_cast_types_template.py
    │   ├── file_aggregate_template.py
    │   ├── file_delta_load_template.py
    │   ├── file_rank_filter_template.py
    │   └── file_filter_by_values_template.py
    │
    └── generated_scripts/        ← Output folder for all generated scripts
        └── *.py                  ← Generated preprocess() scripts land here
```

---

## 6. Preprocessing Scenarios & Templates

---

### PS-01: File Detection & Auto-Loading

**Purpose:** Auto-detect any file format from a given path (CSV, TSV, TXT, XLSX, XLS, JSON, XML, HTML, ZIP) and load it into a pandas DataFrame. Writes the loaded data as a normalised output file. This is the foundation script — used before any other preprocessing step.

**Template File:** `file_detect_load_template.py`

**Function Signature:**
```python
def preprocess(input_path: str) -> str:
```

**Placeholders:**

| Placeholder | Description | Example Value |
|---|---|---|
| `{{OUTPUT_DIR}}` | Folder where output file is saved | `./output` |
| `{{OUTPUT_FORMAT}}` | Output file format | `csv` |
| `{{ENCODING_PRIMARY}}` | First encoding to try | `utf-8` |
| `{{ENCODING_FALLBACK_1}}` | Second encoding fallback | `cp1252` |
| `{{ENCODING_FALLBACK_2}}` | Third encoding fallback | `latin-1` |
| `{{OUTPUT_FILENAME_PREFIX}}` | Prefix for output filename | `processed_` |

**Template Skeleton:**
```python
import os
import pandas as pd

OUTPUT_DIR             = "{{OUTPUT_DIR}}"
OUTPUT_FORMAT          = "{{OUTPUT_FORMAT}}"
ENCODING_ORDER         = ["{{ENCODING_PRIMARY}}", "{{ENCODING_FALLBACK_1}}", "{{ENCODING_FALLBACK_2}}"]
OUTPUT_FILENAME_PREFIX = "{{OUTPUT_FILENAME_PREFIX}}"

def preprocess(input_path: str) -> str:
    # Auto-detect format and load file
    # Write to OUTPUT_DIR as OUTPUT_FORMAT
    # Return output file path
    ...
    return output_path
```

**Output:** Normalised file at `OUTPUT_DIR/OUTPUT_FILENAME_PREFIX{original_name}.OUTPUT_FORMAT`

---

### PS-02: File Union (Stack Multiple Files into One)

**Purpose:** Vertically stack (union) selected files provided via `input_paths` into a single consolidated output file.

**Input Selection:**
- Classic: `preprocess(["./a.csv", "./b.csv"])`
- Folder + filenames: `preprocess(["./input_dir", "a.csv", "b.csv"])`

**Column/Schema Handling:**
- Default (no `output_columns`): output columns are the UNION of all columns across inputs (missing values filled with null/NaN)
- Optional schema (`output_columns`): enforce a specific output column list and order
  - Missing columns are created (null/NaN)
  - Extra columns are dropped
  - If none of the provided column names match a file, that file is mapped by POSITION into `output_columns`
  - If `ADD_SOURCE_TAG` is enabled, `SOURCE_TAG_COLUMN` is appended after `output_columns` unless you include it in `output_columns`

**Template File:** `file_union_template.py`

**Function Signature:**
```python
def preprocess(input_paths: list, output_columns=None) -> str:
```

**Optional Parameter:**
- `output_columns` can be a `list[str]`, a comma-separated string (`"A,B,C"`), or a JSON list string (`["A","B","C"]`).

**Placeholders:**

| Placeholder | Description | Example Value |
|---|---|---|
| `{{OUTPUT_DIR}}` | Folder where output file is saved | `./output` |
| `{{OUTPUT_FILENAME}}` | Name of the unified output file | `all_invoices_unioned.csv` |
| `{{OUTPUT_FORMAT}}` | Output file format | `csv` |
| `{{ADD_SOURCE_TAG}}` | Add source filename column (True/False) | `True` |
| `{{SOURCE_TAG_COLUMN}}` | Name of the source tracking column | `Source_Filename` |

**Template Skeleton:**
```python
import os
import pandas as pd

OUTPUT_DIR       = "{{OUTPUT_DIR}}"
OUTPUT_FILENAME  = "{{OUTPUT_FILENAME}}"
OUTPUT_FORMAT    = "{{OUTPUT_FORMAT}}"
ADD_SOURCE_TAG   = {{ADD_SOURCE_TAG}}
SOURCE_TAG_COLUMN = "{{SOURCE_TAG_COLUMN}}"

def preprocess(input_paths: list, output_columns=None) -> str:
    # Load all files, tag each with source filename
    # Concatenate all DataFrames
    # Write to OUTPUT_DIR/OUTPUT_FILENAME
    # Return output file path
    ...
    return output_path
```

**Output:** Single file at `OUTPUT_DIR/OUTPUT_FILENAME` containing all rows from all input files.

---

### PS-03: Two-File Join

**Purpose:** Join exactly two files on a specified key column. The first file in `input_paths` is the left (primary) file; the second is the right file. Produces a single merged output file with columns from both sources.

**Template File:** `file_join_two_template.py`

**Function Signature:**
```python
def preprocess(input_paths: list) -> str:
```

**Placeholders:**

| Placeholder | Description | Example Value |
|---|---|---|
| `{{JOIN_KEY}}` | Column name to join on | `Account_Number` |
| `{{JOIN_TYPE}}` | Type of join | `inner` |
| `{{LEFT_SUFFIX}}` | Suffix for overlapping left columns | `_left` |
| `{{RIGHT_SUFFIX}}` | Suffix for overlapping right columns | `_right` |
| `{{OUTPUT_DIR}}` | Folder where output file is saved | `./output` |
| `{{OUTPUT_FILENAME}}` | Name of the merged output file | `joined_output.csv` |
| `{{OUTPUT_FORMAT}}` | Output file format | `csv` |

**Template Skeleton:**
```python
import os
import pandas as pd

JOIN_KEY        = "{{JOIN_KEY}}"
JOIN_TYPE       = "{{JOIN_TYPE}}"
LEFT_SUFFIX     = "{{LEFT_SUFFIX}}"
RIGHT_SUFFIX    = "{{RIGHT_SUFFIX}}"
OUTPUT_DIR      = "{{OUTPUT_DIR}}"
OUTPUT_FILENAME = "{{OUTPUT_FILENAME}}"
OUTPUT_FORMAT   = "{{OUTPUT_FORMAT}}"

def preprocess(input_paths: list) -> str:
    # input_paths[0] = left file, input_paths[1] = right file
    # Join on JOIN_KEY with JOIN_TYPE
    # Write merged result to OUTPUT_DIR/OUTPUT_FILENAME
    # Return output file path
    ...
    return output_path
```

**Output:** Merged file at `OUTPUT_DIR/OUTPUT_FILENAME`.

---

### PS-04: Multi-File Join (Chain Three or More Files)

**Purpose:** Join three or more files sequentially. The first file in `input_paths` is the base; each subsequent file is joined onto the cumulative result. The join chain is defined as a list of steps, each specifying which file to join, which key column to use, and what join type.

**Template File:** `file_join_multi_template.py`

**Function Signature:**
```python
def preprocess(input_paths: list) -> str:
```

**Placeholders:**

| Placeholder | Description | Example Value |
|---|---|---|
| `{{JOIN_STEPS}}` | Python list literal defining the join chain | `[{"file_index": 1, "join_key": "Product_ID", "join_type": "left"}, {"file_index": 2, "join_key": "Category_ID", "join_type": "inner"}]` |
| `{{OUTPUT_DIR}}` | Folder where output file is saved | `./output` |
| `{{OUTPUT_FILENAME}}` | Name of the final merged output file | `multi_joined_output.csv` |
| `{{OUTPUT_FORMAT}}` | Output file format | `csv` |

**Template Skeleton:**
```python
import os
import pandas as pd

JOIN_STEPS = {{JOIN_STEPS}}

OUTPUT_DIR      = "{{OUTPUT_DIR}}"
OUTPUT_FILENAME = "{{OUTPUT_FILENAME}}"
OUTPUT_FORMAT   = "{{OUTPUT_FORMAT}}"

def preprocess(input_paths: list) -> str:
    # Start with input_paths[0] as base DataFrame
    # For each step in JOIN_STEPS:
    #   Load input_paths[step['file_index']]
    #   Join base with this file on step['join_key'] using step['join_type']
    # Write final result to OUTPUT_DIR/OUTPUT_FILENAME
    # Return output file path
    ...
    return output_path
```

**Output:** Fully merged file at `OUTPUT_DIR/OUTPUT_FILENAME`.

---

### PS-05: Multi-Key Join (Composite Key)

**Purpose:** Join two files using multiple columns as the join key simultaneously (composite key join). Useful when a single column is not sufficient to identify the relationship, e.g. joining on `Account_Number` AND `Invoice_Date` together.

**Template File:** `file_join_multi_key_template.py`

**Function Signature:**
```python
def preprocess(input_paths: list) -> str:
```

**Placeholders:**

| Placeholder | Description | Example Value |
|---|---|---|
| `{{JOIN_KEYS}}` | Python list of column names for composite join | `["Account_Number", "Invoice_Date"]` |
| `{{JOIN_TYPE}}` | Type of join | `inner` |
| `{{LEFT_SUFFIX}}` | Suffix for overlapping left columns | `_left` |
| `{{RIGHT_SUFFIX}}` | Suffix for overlapping right columns | `_right` |
| `{{OUTPUT_DIR}}` | Folder where output file is saved | `./output` |
| `{{OUTPUT_FILENAME}}` | Name of the merged output file | `multikey_joined_output.csv` |
| `{{OUTPUT_FORMAT}}` | Output file format | `csv` |

**Template Skeleton:**
```python
import os
import pandas as pd

JOIN_KEYS       = {{JOIN_KEYS}}
JOIN_TYPE       = "{{JOIN_TYPE}}"
LEFT_SUFFIX     = "{{LEFT_SUFFIX}}"
RIGHT_SUFFIX    = "{{RIGHT_SUFFIX}}"
OUTPUT_DIR      = "{{OUTPUT_DIR}}"
OUTPUT_FILENAME = "{{OUTPUT_FILENAME}}"
OUTPUT_FORMAT   = "{{OUTPUT_FORMAT}}"

def preprocess(input_paths: list) -> str:
    # input_paths[0] = left file, input_paths[1] = right file
    # Join on all columns in JOIN_KEYS list
    # Write merged result to OUTPUT_DIR/OUTPUT_FILENAME
    # Return output file path
    ...
    return output_path
```

**Output:** Merged file at `OUTPUT_DIR/OUTPUT_FILENAME`.

---

### PS-06: Denormalization (Flatten Master-Detail)

**Purpose:** Flatten a normalised master-detail relationship into a single wide file by joining a master file (e.g. customers) with a detail file (e.g. invoices). Each master row is expanded with its matching detail rows. Useful for preparing flat files for analytics or reporting.

**Template File:** `file_denormalize_template.py`

**Function Signature:**
```python
def preprocess(input_paths: list) -> str:
```

**Placeholders:**

| Placeholder | Description | Example Value |
|---|---|---|
| `{{JOIN_KEY}}` | Shared key column between master and detail | `Account_Number` |
| `{{JOIN_TYPE}}` | Join type (usually left to keep all master rows) | `left` |
| `{{DETAIL_PREFIX}}` | Prefix to namespace detail columns | `DTL_` |
| `{{OUTPUT_DIR}}` | Folder where output file is saved | `./output` |
| `{{OUTPUT_FILENAME}}` | Name of the denormalized output file | `denormalized_output.csv` |
| `{{OUTPUT_FORMAT}}` | Output file format | `csv` |

**Template Skeleton:**
```python
import os
import pandas as pd

JOIN_KEY        = "{{JOIN_KEY}}"
JOIN_TYPE       = "{{JOIN_TYPE}}"
DETAIL_PREFIX   = "{{DETAIL_PREFIX}}"
OUTPUT_DIR      = "{{OUTPUT_DIR}}"
OUTPUT_FILENAME = "{{OUTPUT_FILENAME}}"
OUTPUT_FORMAT   = "{{OUTPUT_FORMAT}}"

def preprocess(input_paths: list) -> str:
    # input_paths[0] = master file, input_paths[1] = detail file
    # Add DETAIL_PREFIX to all detail columns (except JOIN_KEY)
    # Join master with detail on JOIN_KEY using JOIN_TYPE
    # Write flat result to OUTPUT_DIR/OUTPUT_FILENAME
    # Return output file path
    ...
    return output_path
```

**Output:** Single flat file at `OUTPUT_DIR/OUTPUT_FILENAME` with master + detail columns combined.

---

### PS-07: Column-Value Split (by Cardinality)

**Purpose:** Split a single input file into multiple output files based on the distinct values found in a specified column. One output file is created per unique value. If the column has 5 distinct values, 5 output files are produced. The number of output files equals the cardinality of the split column.

**Template File:** `file_split_by_value_template.py`

**Function Signature:**
```python
def preprocess(input_path: str) -> str:
```

**Placeholders:**

| Placeholder | Description | Example Value |
|---|---|---|
| `{{SPLIT_COLUMN}}` | Column whose distinct values drive the split | `Status` |
| `{{OUTPUT_DIR}}` | Folder where all split output files are saved | `./output/split_status` |
| `{{OUTPUT_FORMAT}}` | Output file format for all split files | `csv` |
| `{{FILENAME_TEMPLATE}}` | Template for split file names | `{split_column}_{value}.csv` |
| `{{INCLUDE_SPLIT_COLUMN}}` | Keep the split column in output files (True/False) | `True` |

**Template Skeleton:**
```python
import os
import pandas as pd

SPLIT_COLUMN         = "{{SPLIT_COLUMN}}"
OUTPUT_DIR           = "{{OUTPUT_DIR}}"
OUTPUT_FORMAT        = "{{OUTPUT_FORMAT}}"
FILENAME_TEMPLATE    = "{{FILENAME_TEMPLATE}}"
INCLUDE_SPLIT_COLUMN = {{INCLUDE_SPLIT_COLUMN}}

def preprocess(input_path: str) -> str:
    # Load input file
    # Get distinct values in SPLIT_COLUMN
    # For each distinct value: filter rows, write to separate output file
    # Null values go to {SPLIT_COLUMN}_NULL.OUTPUT_FORMAT
    # Return OUTPUT_DIR path
    ...
    return OUTPUT_DIR
```

**Output:** N files in `OUTPUT_DIR` where N = cardinality of `SPLIT_COLUMN`. Returns `OUTPUT_DIR`.

---

### PS-08: Row Filter to Files

**Purpose:** Apply one or more filter conditions to a source file and route matching rows to separate output files. Each filter condition produces its own named output file. Rows matching no condition can be written to a default unmatched file or discarded.

**Template File:** `file_filter_to_files_template.py`

**Function Signature:**
```python
def preprocess(input_path: str) -> str:
```

**Placeholders:**

| Placeholder | Description | Example Value |
|---|---|---|
| `{{FILTER_RULES}}` | Python list of filter rule dicts | `[{"condition": "Status == 'PAID'", "output_filename": "paid.csv"}, {"condition": "Status == 'OPEN'", "output_filename": "open.csv"}]` |
| `{{OUTPUT_DIR}}` | Folder where all filtered output files are saved | `./output/filtered` |
| `{{OUTPUT_FORMAT}}` | Output file format | `csv` |
| `{{UNMATCHED_FILENAME}}` | Filename for rows matching no rule (empty string to discard) | `unmatched.csv` |

**Template Skeleton:**
```python
import os
import pandas as pd

FILTER_RULES        = {{FILTER_RULES}}
OUTPUT_DIR          = "{{OUTPUT_DIR}}"
OUTPUT_FORMAT       = "{{OUTPUT_FORMAT}}"
UNMATCHED_FILENAME  = "{{UNMATCHED_FILENAME}}"

def preprocess(input_path: str) -> str:
    # Load input file
    # For each rule in FILTER_RULES:
    #   Apply rule['condition'] using DataFrame.query()
    #   Write matching rows to OUTPUT_DIR/rule['output_filename']
    # Collect unmatched rows, write to UNMATCHED_FILENAME if set
    # Return OUTPUT_DIR path
    ...
    return OUTPUT_DIR
```

**Output:** One file per filter rule in `OUTPUT_DIR`, plus optional unmatched file. Returns `OUTPUT_DIR`.

---

### PS-09: Vertical Column Split (Wide to Narrow)

**Purpose:** Split a wide file (many columns) into two or more narrower output files, each containing a defined subset of columns. A set of common key columns is retained in all output files to allow re-joining later. Useful for normalising flat files or separating logical groups of attributes.

**Template File:** `file_split_columns_template.py`

**Function Signature:**
```python
def preprocess(input_path: str) -> str:
```

**Placeholders:**

| Placeholder | Description | Example Value |
|---|---|---|
| `{{COMMON_KEY_COLUMNS}}` | Python list of columns to include in ALL output files | `["Account_Number"]` |
| `{{COLUMN_GROUPS}}` | Python list of column group dicts | `[{"columns": ["Name", "Address", "City"], "output_filename": "customer_address.csv"}, {"columns": ["Credit_Limit", "Currency"], "output_filename": "customer_finance.csv"}]` |
| `{{OUTPUT_DIR}}` | Folder where all split output files are saved | `./output/split_columns` |
| `{{OUTPUT_FORMAT}}` | Output file format | `csv` |

**Template Skeleton:**
```python
import os
import pandas as pd

COMMON_KEY_COLUMNS = {{COMMON_KEY_COLUMNS}}
COLUMN_GROUPS      = {{COLUMN_GROUPS}}
OUTPUT_DIR         = "{{OUTPUT_DIR}}"
OUTPUT_FORMAT      = "{{OUTPUT_FORMAT}}"

def preprocess(input_path: str) -> str:
    # Load input file
    # For each group in COLUMN_GROUPS:
    #   Select COMMON_KEY_COLUMNS + group['columns']
    #   Write to OUTPUT_DIR/group['output_filename']
    # Return OUTPUT_DIR path
    ...
    return OUTPUT_DIR
```

**Output:** One file per column group in `OUTPUT_DIR`. Each file contains `COMMON_KEY_COLUMNS` + group columns.

---

### PS-10: Deduplication

**Purpose:** Identify and remove duplicate rows from a file based on one or more key columns. Supports keeping the first occurrence, last occurrence, or flagging all duplicates. Produces a clean deduplicated file and a separate duplicates report file.

**Template File:** `file_deduplicate_template.py`

**Function Signature:**
```python
def preprocess(input_path: str) -> str:
```

**Placeholders:**

| Placeholder | Description | Example Value |
|---|---|---|
| `{{KEY_COLUMNS}}` | Python list of columns that define uniqueness | `["Invoice_Number"]` |
| `{{KEEP}}` | Which occurrence to keep | `first` |
| `{{OUTPUT_DIR}}` | Folder where output files are saved | `./output` |
| `{{OUTPUT_FILENAME}}` | Name of the deduplicated output file | `deduped_invoices.csv` |
| `{{DUPLICATES_REPORT_FILENAME}}` | Name of the duplicates report file | `duplicates_report.csv` |
| `{{OUTPUT_FORMAT}}` | Output file format | `csv` |

**Template Skeleton:**
```python
import os
import pandas as pd

KEY_COLUMNS                = {{KEY_COLUMNS}}
KEEP                       = "{{KEEP}}"
OUTPUT_DIR                 = "{{OUTPUT_DIR}}"
OUTPUT_FILENAME            = "{{OUTPUT_FILENAME}}"
DUPLICATES_REPORT_FILENAME = "{{DUPLICATES_REPORT_FILENAME}}"
OUTPUT_FORMAT              = "{{OUTPUT_FORMAT}}"

def preprocess(input_path: str) -> str:
    # Load input file
    # Identify duplicates based on KEY_COLUMNS
    # Write duplicates to DUPLICATES_REPORT_FILENAME
    # Remove duplicates using KEEP strategy
    # Write clean data to OUTPUT_DIR/OUTPUT_FILENAME
    # Return output file path
    ...
    return output_path
```

**Output:** Deduplicated file + duplicates report file in `OUTPUT_DIR`.

---

### PS-11: Column Renaming & Mapping

**Purpose:** Rename columns in a source file according to a provided mapping dictionary. Standardises inconsistent column names from different source systems before merging or loading into a canonical schema. Optionally drops columns not in the mapping.

**Template File:** `file_rename_columns_template.py`

**Function Signature:**
```python
def preprocess(input_path: str) -> str:
```

**Placeholders:**

| Placeholder | Description | Example Value |
|---|---|---|
| `{{COLUMN_MAPPING}}` | Python dict of source → target column names | `{"Acct_No": "Account_Number", "Inv_Dt": "Invoice_Date"}` |
| `{{DROP_UNMAPPED}}` | Drop columns not in mapping (True/False) | `False` |
| `{{OUTPUT_DIR}}` | Folder where output file is saved | `./output` |
| `{{OUTPUT_FILENAME}}` | Name of the renamed output file | `renamed_output.csv` |
| `{{OUTPUT_FORMAT}}` | Output file format | `csv` |

**Template Skeleton:**
```python
import os
import pandas as pd

COLUMN_MAPPING  = {{COLUMN_MAPPING}}
DROP_UNMAPPED   = {{DROP_UNMAPPED}}
OUTPUT_DIR      = "{{OUTPUT_DIR}}"
OUTPUT_FILENAME = "{{OUTPUT_FILENAME}}"
OUTPUT_FORMAT   = "{{OUTPUT_FORMAT}}"

def preprocess(input_path: str) -> str:
    # Load input file
    # Rename columns using COLUMN_MAPPING
    # If DROP_UNMAPPED: drop columns not in COLUMN_MAPPING values
    # Write result to OUTPUT_DIR/OUTPUT_FILENAME
    # Return output file path
    ...
    return output_path
```

**Output:** File with renamed columns at `OUTPUT_DIR/OUTPUT_FILENAME`.

---

### PS-12: Null & Missing Value Handling

**Purpose:** Detect and handle missing or null values in a file. Supports per-column strategies: fill with a fixed value, fill with mean/median/mode, forward-fill, backward-fill, or drop rows where a column is null. Produces a cleaned file and a null audit report.

**Template File:** `file_handle_nulls_template.py`

**Function Signature:**
```python
def preprocess(input_path: str) -> str:
```

**Placeholders:**

| Placeholder | Description | Example Value |
|---|---|---|
| `{{NULL_RULES}}` | Python list of per-column null handling rules | `[{"column": "Invoice_Amount", "strategy": "fill", "fill_value": "0"}, {"column": "*", "strategy": "drop_row"}]` |
| `{{NULL_VALUES}}` | Python list of strings to treat as null | `["", "NULL", "N/A", "NA", "none", "NONE"]` |
| `{{OUTPUT_DIR}}` | Folder where output files are saved | `./output` |
| `{{OUTPUT_FILENAME}}` | Name of the cleaned output file | `nulls_handled_output.csv` |
| `{{NULL_REPORT_FILENAME}}` | Name of the null audit report | `null_audit_report.csv` |
| `{{OUTPUT_FORMAT}}` | Output file format | `csv` |

**Template Skeleton:**
```python
import os
import pandas as pd

NULL_RULES           = {{NULL_RULES}}
NULL_VALUES          = {{NULL_VALUES}}
OUTPUT_DIR           = "{{OUTPUT_DIR}}"
OUTPUT_FILENAME      = "{{OUTPUT_FILENAME}}"
NULL_REPORT_FILENAME = "{{NULL_REPORT_FILENAME}}"
OUTPUT_FORMAT        = "{{OUTPUT_FORMAT}}"

def preprocess(input_path: str) -> str:
    # Load input file, replace NULL_VALUES strings with pd.NA
    # Apply each rule in NULL_RULES per column (or all columns if column='*')
    # Write null audit report to NULL_REPORT_FILENAME
    # Write cleaned data to OUTPUT_DIR/OUTPUT_FILENAME
    # Return output file path
    ...
    return output_path
```

**Supported Strategies:** `fill`, `mean`, `median`, `mode`, `forward_fill`, `backward_fill`, `drop_row`

**Output:** Cleaned file + null audit report in `OUTPUT_DIR`.

---

### PS-13: Data Type Casting & Standardisation

**Purpose:** Cast columns to specified data types (string, integer, float, date, boolean) and apply formatting standards such as date format normalisation, numeric precision, currency symbol stripping, and string trimming. Produces a type-safe standardised file and a cast error report.

**Template File:** `file_cast_types_template.py`

**Function Signature:**
```python
def preprocess(input_path: str) -> str:
```

**Placeholders:**

| Placeholder | Description | Example Value |
|---|---|---|
| `{{TYPE_RULES}}` | Python list of per-column type cast rules | `[{"column": "Invoice_Date", "target_type": "date", "format": "%d/%m/%Y"}, {"column": "Invoice_Amount", "target_type": "float"}]` |
| `{{STRIP_CURRENCY}}` | Strip currency symbols before numeric cast (True/False) | `True` |
| `{{TRIM_STRINGS}}` | Strip whitespace from string columns (True/False) | `True` |
| `{{ON_ERROR}}` | What to do when casting fails | `nullify` |
| `{{OUTPUT_DIR}}` | Folder where output files are saved | `./output` |
| `{{OUTPUT_FILENAME}}` | Name of the type-cast output file | `typed_output.csv` |
| `{{CAST_ERROR_REPORT_FILENAME}}` | Name of the cast error report | `cast_errors.csv` |
| `{{OUTPUT_FORMAT}}` | Output file format | `csv` |

**Template Skeleton:**
```python
import os
import pandas as pd

TYPE_RULES                = {{TYPE_RULES}}
STRIP_CURRENCY            = {{STRIP_CURRENCY}}
TRIM_STRINGS              = {{TRIM_STRINGS}}
ON_ERROR                  = "{{ON_ERROR}}"
OUTPUT_DIR                = "{{OUTPUT_DIR}}"
OUTPUT_FILENAME           = "{{OUTPUT_FILENAME}}"
CAST_ERROR_REPORT_FILENAME = "{{CAST_ERROR_REPORT_FILENAME}}"
OUTPUT_FORMAT             = "{{OUTPUT_FORMAT}}"

def preprocess(input_path: str) -> str:
    # Load input file
    # For each rule in TYPE_RULES: cast column to target_type
    # On cast failure: apply ON_ERROR strategy (nullify | keep_original | drop_row)
    # Log failed casts to CAST_ERROR_REPORT_FILENAME
    # Write typed data to OUTPUT_DIR/OUTPUT_FILENAME
    # Return output file path
    ...
    return output_path
```

**Supported Types:** `string`, `integer`, `float`, `date`, `boolean`
**ON_ERROR Options:** `nullify`, `keep_original`, `drop_row`

---

### PS-14: Aggregation & Grouping

**Purpose:** Group rows by one or more columns and apply aggregation functions to produce a summarised output file. Useful for rolling up transaction-level data to account-level, period-level, or category-level summaries.

**Template File:** `file_aggregate_template.py`

**Function Signature:**
```python
def preprocess(input_path: str) -> str:
```

**Placeholders:**

| Placeholder | Description | Example Value |
|---|---|---|
| `{{GROUP_BY_COLUMNS}}` | Python list of columns to group by | `["Account_Number", "Month"]` |
| `{{AGGREGATIONS}}` | Python list of aggregation rule dicts | `[{"column": "Invoice_Amount", "function": "sum"}, {"column": "Invoice_Number", "function": "count"}]` |
| `{{OUTPUT_DIR}}` | Folder where output file is saved | `./output` |
| `{{OUTPUT_FILENAME}}` | Name of the aggregated output file | `aggregated_output.csv` |
| `{{OUTPUT_FORMAT}}` | Output file format | `csv` |

**Template Skeleton:**
```python
import os
import pandas as pd

GROUP_BY_COLUMNS = {{GROUP_BY_COLUMNS}}
AGGREGATIONS     = {{AGGREGATIONS}}
OUTPUT_DIR       = "{{OUTPUT_DIR}}"
OUTPUT_FILENAME  = "{{OUTPUT_FILENAME}}"
OUTPUT_FORMAT    = "{{OUTPUT_FORMAT}}"

def preprocess(input_path: str) -> str:
    # Load input file
    # Build pandas agg dict from AGGREGATIONS list
    # Group by GROUP_BY_COLUMNS, apply aggregations
    # Write grouped result to OUTPUT_DIR/OUTPUT_FILENAME
    # Return output file path
    ...
    return output_path
```

**Supported Aggregation Functions:** `sum`, `count`, `mean`, `min`, `max`, `first`, `last`, `concat`

---

### PS-15: Incremental / Delta Load

**Purpose:** Compare a current (new) file against a previous (baseline) file and extract only the records that are new or have changed. Supports three modes: `new_only`, `changed_only`, and `full_delta`. A `Delta_Status` column is added to identify each record's change type.

**Template File:** `file_delta_load_template.py`

**Function Signature:**
```python
def preprocess(input_paths: list) -> str:
```

**Placeholders:**

| Placeholder | Description | Example Value |
|---|---|---|
| `{{KEY_COLUMNS}}` | Python list of columns that uniquely identify a record | `["Invoice_Number"]` |
| `{{DELTA_MODE}}` | What records to extract | `full_delta` |
| `{{COMPARE_COLUMNS}}` | Python list of columns to compare for changes (empty = all non-key columns) | `["Invoice_Amount", "Status"]` |
| `{{DELTA_STATUS_COLUMN}}` | Name of the status column added to output | `Delta_Status` |
| `{{OUTPUT_DIR}}` | Folder where output file is saved | `./output` |
| `{{OUTPUT_FILENAME}}` | Name of the delta output file | `delta_output.csv` |
| `{{OUTPUT_FORMAT}}` | Output file format | `csv` |

**Template Skeleton:**
```python
import os
import pandas as pd

KEY_COLUMNS         = {{KEY_COLUMNS}}
DELTA_MODE          = "{{DELTA_MODE}}"
COMPARE_COLUMNS     = {{COMPARE_COLUMNS}}
DELTA_STATUS_COLUMN = "{{DELTA_STATUS_COLUMN}}"
OUTPUT_DIR          = "{{OUTPUT_DIR}}"
OUTPUT_FILENAME     = "{{OUTPUT_FILENAME}}"
OUTPUT_FORMAT       = "{{OUTPUT_FORMAT}}"

def preprocess(input_paths: list) -> str:
    # input_paths[0] = current/new file
    # input_paths[1] = baseline/previous file
    # Identify NEW: in current but not in baseline (by KEY_COLUMNS)
    # Identify CHANGED: in both but COMPARE_COLUMNS differ
    # Identify DELETED: in baseline but not in current (full_delta only)
    # Add DELTA_STATUS_COLUMN with values: NEW | CHANGED | DELETED
    # Write delta records to OUTPUT_DIR/OUTPUT_FILENAME
    # Return output file path
    ...
    return output_path
```

**DELTA_MODE Options:** `new_only`, `changed_only`, `full_delta`
**Delta_Status Values:** `NEW`, `CHANGED`, `DELETED`

---

### PS-16: Rank Filter (Window Rank within Groups)

**Purpose:** Assign a sequential rank to every row within a group (or globally across the whole file if no grouping is specified), then optionally keep only the top-N ranked rows per group. Non-top-N rows can be written to a separate discard file or silently dropped. Useful for deduplication by recency, keeping the highest-value record per account, or any "best record per group" requirement.

**Template File:** `file_rank_filter_template.py`

**Function Signature:**
```python
def preprocess(input_path: str) -> str:
```

**Placeholders:**

| Placeholder | Description | Example Value |
|---|---|---|
| `{{PARTITION_BY}}` | Python list of columns to group by before ranking. Empty list `[]` = rank globally across all rows | `["Account_Number"]` |
| `{{RANK_BY_COLUMN}}` | Column whose value determines the rank order within each group | `Invoice_Date` |
| `{{RANK_ORDER}}` | `asc` → rank 1 = smallest value &nbsp;&nbsp; `desc` → rank 1 = largest value | `desc` |
| `{{RANK_METHOD}}` | Ranking method (see options below) | `row_number` |
| `{{RANK_COLUMN_NAME}}` | Name of the rank column added to every output row | `Row_Rank` |
| `{{KEEP_TOP_N}}` | Number of top-ranked rows to keep per group. `0` = keep all rows (no filtering, just adds rank column) | `1` |
| `{{DISCARD_FILENAME}}` | Filename for rows that don't make the top-N cut. Empty string `""` = silently drop them | `discarded_ranks.csv` |
| `{{OUTPUT_DIR}}` | Folder where output files are saved | `./output` |
| `{{OUTPUT_FILENAME}}` | Name of the ranked (and filtered) output file | `ranked_output.csv` |
| `{{OUTPUT_FORMAT}}` | Output file format | `csv` |

**RANK_METHOD Options:**

| Method | Behaviour | Pandas equivalent |
|---|---|---|
| `row_number` | Unique sequential rank; ties broken by row position | `rank(method='first')` |
| `rank` | Tied rows share the same (lowest) rank; gaps appear after ties | `rank(method='min')` |
| `dense_rank` | Tied rows share the same rank; no gaps in sequence | `rank(method='dense')` |

**Template Skeleton:**
```python
import os
import pandas as pd

PARTITION_BY     = {{PARTITION_BY}}
RANK_BY_COLUMN   = "{{RANK_BY_COLUMN}}"
RANK_ORDER       = "{{RANK_ORDER}}"
RANK_METHOD      = "{{RANK_METHOD}}"
RANK_COLUMN_NAME = "{{RANK_COLUMN_NAME}}"
KEEP_TOP_N       = {{KEEP_TOP_N}}
DISCARD_FILENAME = "{{DISCARD_FILENAME}}"
OUTPUT_DIR       = "{{OUTPUT_DIR}}"
OUTPUT_FILENAME  = "{{OUTPUT_FILENAME}}"
OUTPUT_FORMAT    = "{{OUTPUT_FORMAT}}"

def preprocess(input_path: str) -> str:
    # Load input file
    # Compute RANK_COLUMN_NAME using PARTITION_BY + RANK_BY_COLUMN + RANK_ORDER + RANK_METHOD
    # If KEEP_TOP_N > 0: split into top-N rows and discarded rows
    #   Write discarded rows to DISCARD_FILENAME if non-empty
    # Write kept rows to OUTPUT_DIR/OUTPUT_FILENAME
    # Return output file path
    ...
    return output_path
```

**Behaviour Summary:**

| KEEP_TOP_N | DISCARD_FILENAME | Result |
|---|---|---|
| `1` | `"discarded.csv"` | Keep rank-1 row per group; all others written to `discarded.csv` |
| `1` | `""` | Keep rank-1 row per group; all others silently dropped |
| `3` | `"rest.csv"` | Keep top-3 rows per group; remainder written to `rest.csv` |
| `0` | `""` | Keep all rows; rank column added but no filtering applied |

**Output:** Filtered file at `OUTPUT_DIR/OUTPUT_FILENAME` + optional discard file in same `OUTPUT_DIR`.

---

### PS-17: Filter by Value List

**Purpose:** Filter a single column against one or more explicit value lists, routing each matching group of rows to its own named output file. All rows that do not match any defined group — including null values — are routed to a single `OTHERS_FILENAME`. Supports case-insensitive matching. Designed as a simpler, safer alternative to PS-08 when filtering by known discrete values rather than arbitrary query expressions.

**Template File:** `file_filter_by_values_template.py`

**Function Signature:**
```python
def preprocess(input_path: str) -> str:
```

**Placeholders:**

| Placeholder | Description | Example Value |
|---|---|---|
| `{{FILTER_COLUMN}}` | The single column to test for membership | `Status` |
| `{{VALUE_GROUPS}}` | Python list of group dicts — each defines a value list and output filename (see format below) | see below |
| `{{CASE_SENSITIVE}}` | `True` = exact match &nbsp;&nbsp; `False` = case-insensitive string match | `False` |
| `{{OTHERS_FILENAME}}` | Filename for all rows not matched by any group (including nulls). Empty `""` = silently drop unmatched rows | `others.csv` |
| `{{OUTPUT_DIR}}` | Folder where all output files are saved | `./output/filtered` |
| `{{OUTPUT_FORMAT}}` | Output file format | `csv` |

**VALUE_GROUPS Format:**
```python
[
    {"values": ["PAID", "SETTLED"],    "output_filename": "paid_settled.csv"},
    {"values": ["OPEN", "PENDING"],    "output_filename": "open_pending.csv"},
    {"values": ["DISPUTED", "HOLD"],   "output_filename": "disputed.csv"},
]
```

**Template Skeleton:**
```python
import os
import pandas as pd

FILTER_COLUMN   = "{{FILTER_COLUMN}}"
VALUE_GROUPS    = {{VALUE_GROUPS}}
CASE_SENSITIVE  = {{CASE_SENSITIVE}}
OTHERS_FILENAME = "{{OTHERS_FILENAME}}"
OUTPUT_DIR      = "{{OUTPUT_DIR}}"
OUTPUT_FORMAT   = "{{OUTPUT_FORMAT}}"

def preprocess(input_path: str) -> str:
    # Load input file
    # For each group in VALUE_GROUPS:
    #   Match unclaimed rows where FILTER_COLUMN is in group['values'] (first-match wins)
    #   Write matching rows to OUTPUT_DIR/group['output_filename']
    # Write all unmatched rows (including nulls) to OTHERS_FILENAME if non-empty
    # Return OUTPUT_DIR path
    ...
    return OUTPUT_DIR
```

**Key Behaviours:**

| Behaviour | Detail |
|---|---|
| First-match wins | A row matched by an earlier group is not re-tested against later groups |
| Null handling | Null values in `FILTER_COLUMN` are never matched — always routed to `OTHERS_FILENAME` |
| Case-insensitive | When `CASE_SENSITIVE = False`, `"paid"` matches `"PAID"`, `"Paid"`, etc. |
| Empty others | If `OTHERS_FILENAME = ""`, unmatched rows are silently discarded (no file written) |

**Comparison with PS-08 (file_filter_to_files):**

| Feature | PS-08 | PS-17 |
|---|---|---|
| Condition type | Arbitrary pandas query expression | Value list membership (`.isin()`) |
| Multi-column conditions | Yes (`"Amount > 100 and Status == 'OPEN'"`) | No — single column only |
| Ease of configuration | Requires query syntax knowledge | Simple list of values |
| Null row handling | Manual (include in a condition explicitly) | Automatic — always to others file |
| Case-insensitive matching | Manual (`.str.lower()` in query) | Built-in flag |

**Output:** One file per group + optional others file, all in `OUTPUT_DIR`. Returns `OUTPUT_DIR`.

---

## 7. Usage Examples

### 7.1 Generate a Column-Value Split Script

```python
from preprocessing_library.generator import generate_preprocessor

output_script = generate_preprocessor(
    template_name="file_split_by_value",
    parameters={
        "SPLIT_COLUMN":          "Status",
        "OUTPUT_DIR":            "./output/split_status",
        "OUTPUT_FORMAT":         "csv",
        "FILENAME_TEMPLATE":     "{split_column}_{value}.csv",
        "INCLUDE_SPLIT_COLUMN":  "True"
    },
    output_script_name="split_by_status_preprocessor.py"
)

print(f"Generated: {output_script}")
# Output: ./generated_scripts/split_by_status_preprocessor.py
```

### 7.2 Generate a Two-File Join Script

```python
output_script = generate_preprocessor(
    template_name="file_join_two",
    parameters={
        "JOIN_KEY":        "Account_Number",
        "JOIN_TYPE":       "inner",
        "LEFT_SUFFIX":     "_cust",
        "RIGHT_SUFFIX":    "_inv",
        "OUTPUT_DIR":      "./output",
        "OUTPUT_FILENAME": "customer_invoice_joined.csv",
        "OUTPUT_FORMAT":   "csv"
    }
)
```

### 7.3 Generate a Row Filter Script

```python
output_script = generate_preprocessor(
    template_name="file_filter_to_files",
    parameters={
        "FILTER_RULES": '[{"condition": "filg_domain == \'UCC Lien\'", "output_filename": "ucc_lien.csv"}, {"condition": "filg_domain == \'Mortgage\'", "output_filename": "mortgage.csv"}]',
        "OUTPUT_DIR":            "./output/filtered",
        "OUTPUT_FORMAT":         "csv",
        "UNMATCHED_FILENAME":    "unmatched.csv"
    }
)
```

### 7.4 Generate a File Union Script — folder input + output schema enforcement

```python
# Pattern 1: folder + filenames (useful when orchestrator provides only filenames)
output_script = generate_preprocessor(
    template_name="file_union",
    parameters={
        "OUTPUT_DIR":         "./output",
        "OUTPUT_FILENAME":    "all_invoices.csv",
        "OUTPUT_FORMAT":      "csv",
        "ADD_SOURCE_TAG":     "True",
        "SOURCE_TAG_COLUMN":  "Source_Filename"
    },
    output_script_name="invoice_union.py"
)

# At runtime — pass folder path first, then filenames to pick from that folder:
# module.preprocess(["./input/invoices", "jan.csv", "feb.csv", "mar.csv"])
```

```python
# Pattern 2: enforce a specific output column list and order
output_script = generate_preprocessor(
    template_name="file_union",
    parameters={
        "OUTPUT_DIR":         "./output",
        "OUTPUT_FILENAME":    "standardised_union.csv",
        "OUTPUT_FORMAT":      "csv",
        "ADD_SOURCE_TAG":     "False",
        "SOURCE_TAG_COLUMN":  "Source_Filename"
    },
    output_script_name="schema_union.py"
)

# At runtime — pass output_columns to enforce schema (missing cols = NaN, extra cols dropped):
# module.preprocess(
#     ["./data/file_a.csv", "./data/file_b.xlsx"],
#     output_columns=["Account_Number", "Invoice_Date", "Invoice_Amount", "Status"]
# )
```

### 7.5 Generate a Delta Load Script

```python
output_script = generate_preprocessor(
    template_name="file_delta_load",
    parameters={
        "KEY_COLUMNS":         '["Invoice_Number"]',
        "DELTA_MODE":          "full_delta",
        "COMPARE_COLUMNS":     '["Invoice_Amount", "Status", "Due_Date"]',
        "DELTA_STATUS_COLUMN": "Delta_Status",
        "OUTPUT_DIR":          "./output/delta",
        "OUTPUT_FILENAME":     "invoice_delta.csv",
        "OUTPUT_FORMAT":       "csv"
    },
    output_script_name="invoice_delta_preprocessor.py"
)

# At runtime:
# module.preprocess(["./data/invoices_today.csv", "./data/invoices_yesterday.csv"])
# → output contains NEW, CHANGED and DELETED rows each tagged in Delta_Status column
```

### 7.6 Generate a Rank Filter Script (keep latest invoice per account)

```python
output_script = generate_preprocessor(
    template_name="file_rank_filter",
    parameters={
        "PARTITION_BY":     '["Account_Number"]',
        "RANK_BY_COLUMN":   "Invoice_Date",
        "RANK_ORDER":       "desc",
        "RANK_METHOD":      "row_number",
        "RANK_COLUMN_NAME": "Row_Rank",
        "KEEP_TOP_N":       "1",
        "DISCARD_FILENAME": "older_invoices.csv",
        "OUTPUT_DIR":       "./output",
        "OUTPUT_FILENAME":  "latest_invoice_per_account.csv",
        "OUTPUT_FORMAT":    "csv"
    }
)
```

### 7.7 Generate a Rank Filter Script (add rank column only, no filtering)

```python
output_script = generate_preprocessor(
    template_name="file_rank_filter",
    parameters={
        "PARTITION_BY":     '["Region", "Product_Category"]',
        "RANK_BY_COLUMN":   "Revenue",
        "RANK_ORDER":       "desc",
        "RANK_METHOD":      "dense_rank",
        "RANK_COLUMN_NAME": "Revenue_Rank",
        "KEEP_TOP_N":       "0",
        "DISCARD_FILENAME": "",
        "OUTPUT_DIR":       "./output",
        "OUTPUT_FILENAME":  "revenue_ranked.csv",
        "OUTPUT_FORMAT":    "csv"
    }
)
```

### 7.8 Generate a Value-List Filter Script

```python
output_script = generate_preprocessor(
    template_name="file_filter_by_values",
    parameters={
        "FILTER_COLUMN":   "Status",
        "VALUE_GROUPS":    '[{"values": ["PAID", "SETTLED"], "output_filename": "paid.csv"}, '
                           ' {"values": ["OPEN", "PENDING"], "output_filename": "open.csv"}, '
                           ' {"values": ["DISPUTED", "ON_HOLD"], "output_filename": "disputed.csv"}]',
        "CASE_SENSITIVE":  "False",
        "OTHERS_FILENAME": "others.csv",
        "OUTPUT_DIR":      "./output/by_status",
        "OUTPUT_FORMAT":   "csv"
    }
)
```

### 7.9 Run the Generated Script

Once generated, the script is called the same way regardless of which preprocessing type it is:

```python
import importlib.util

spec   = importlib.util.spec_from_file_location("preprocess", "./generated_scripts/split_by_status_preprocessor.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

output_path = module.preprocess("./data/invoices.csv")
print(f"Output: {output_path}")
```

---

## 8. Supported File Formats

All generated scripts use a common file loader that auto-detects format:

| Format | Extensions | Detection Method | Notes |
|---|---|---|---|
| CSV | `.csv` | Delimiter auto-detected via `csv.Sniffer` | Handles comma, pipe, semicolon |
| TSV | `.tsv` | Tab delimiter detected | Treated as CSV with tab |
| TXT | `.txt` | Sniffer fallback | Treated as delimited text |
| Excel | `.xlsx` | Extension + openpyxl | First sheet loaded by default (`sheet_name=0`) |
| Excel Legacy | `.xls` | Extension + xlrd | Legacy format support |
| JSON | `.json` | Extension + JSON parse | Arrays of objects |
| XML | `.xml` | Extension + lxml parse | Flattened to tabular |
| HTML | `.html` | Extension + table tags | All `<table>` elements |
| ZIP | `.zip` | Magic bytes check | Recursive extraction |

---

## 9. Output Structure

```
generated_scripts/
│
├── split_by_status_preprocessor.py       ← PS-07 generated script
├── customer_invoice_join_preprocessor.py ← PS-03 generated script
├── ucc_lien_filter_preprocessor.py       ← PS-08 generated script
├── latest_invoice_rank_preprocessor.py   ← PS-16 generated script
├── status_value_filter_preprocessor.py   ← PS-17 generated script
└── ...

output/
│
├── split_status/                         ← PS-07 output
│   ├── Status_PAID.csv
│   ├── Status_OPEN.csv
│   └── Status_NULL.csv
│
├── filtered/                             ← PS-08 output
│   ├── ucc_lien.csv
│   ├── mortgage.csv
│   └── unmatched.csv
│
├── ranked/                               ← PS-16 output (KEEP_TOP_N=1)
│   ├── latest_invoice_per_account.csv    ← top-ranked rows
│   └── older_invoices.csv                ← discarded non-rank-1 rows
│
├── by_status/                            ← PS-17 output
│   ├── paid.csv                          ← rows where Status IN ["PAID","SETTLED"]
│   ├── open.csv                          ← rows where Status IN ["OPEN","PENDING"]
│   ├── disputed.csv                      ← rows where Status IN ["DISPUTED","ON_HOLD"]
│   └── others.csv                        ← all unmatched + null rows
│
└── customer_invoice_joined.csv           ← PS-03 output
```

---

## 10. Integration with Ingestion Platform

The generated preprocessing scripts are designed to integrate directly with the **Universal Data Ingestion & Normalisation Platform**. The ingestion platform calls `preprocess()` on raw input files before passing them through the column mapping and DQ engine.

### Integration Flow

```
Raw Files (ZIP / CSV / XLSX / etc.)
         │
         ▼
 generate_preprocessor()  ← Engineer configures once
         │
         ▼
 preprocess(input_path)   ← Called by ingestion platform per file
         │
         ▼
 Preprocessed output file
         │
         ▼
 Universal Data Ingestion Platform
 (file_parser → column_mapper → dq_engine → output_writer)
```

### Configuration in Ingestion Platform

In the ingestion platform's domain config (`trade_system_config.json`), reference the generated preprocessing script:

```json
{
  "preprocessing": {
    "enabled": true,
    "script_path": "./generated_scripts/split_by_status_preprocessor.py",
    "function_name": "preprocess"
  }
}
```

The platform dynamically loads and calls `preprocess()` from the configured script before ingestion begins.

---

## 11. Gradio UI (Script Generator)

This repo includes an optional Gradio front-end that allows users to:

1. Select a preprocessing template from a dropdown
2. Read the template title, description, and per-parameter help text (driven by `template_catalog.json`)
3. Enter parameters as a JSON object
4. Click **Generate** to produce and download the corresponding `preprocess()` Python script

### 11.1 UI Entry Point

| File | Purpose |
|---|---|
| `gradio_app.py` | Gradio app — run this to start the UI |
| `preprocessing_library/template_catalog.json` | Drives all UI content: display names, descriptions, parameter metadata |

### 11.2 Run Instructions

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the UI from the repo root:

```bash
python gradio_app.py
```

The app starts on `http://localhost:7860` by default.

### 11.3 requirements.txt

```
pandas>=2.0.0
openpyxl>=3.1.0
xlrd>=2.0.1
lxml>=4.9.0
gradio>=4.0.0
```

> **Note:** `xlrd` only supports `.xls` (legacy Excel). For `.xlsx` use `openpyxl`.  
> `lxml` is optional — the XML loader falls back to the stdlib `xml.etree.ElementTree` if not installed.

### 11.4 template_catalog.json — Schema & Format

`template_catalog.json` is a JSON array. Each entry describes one template and drives what the UI displays for that template. When you add a new template, add a matching entry here.

**Full schema for one entry:**

```json
{
  "template_name":  "file_rank_filter",
  "display_name":   "PS-16 — Rank Filter",
  "description":    "Rank rows within groups and keep the top-N per group. Optionally route discarded rows to a separate file.",
  "function_sig":   "preprocess(input_path: str) -> str",
  "parameters": [
    {
      "name":     "PARTITION_BY",
      "type":     "list",
      "required": true,
      "default":  "[]",
      "help":     "Python list of columns to group by before ranking. Use [] to rank globally across all rows."
    },
    {
      "name":     "RANK_BY_COLUMN",
      "type":     "string",
      "required": true,
      "default":  "",
      "help":     "Column whose value determines the rank order within each group."
    },
    {
      "name":     "RANK_ORDER",
      "type":     "string",
      "required": true,
      "default":  "desc",
      "help":     "asc = rank 1 is smallest value. desc = rank 1 is largest value."
    },
    {
      "name":     "RANK_METHOD",
      "type":     "string",
      "required": true,
      "default":  "row_number",
      "help":     "row_number (unique), rank (ties share lowest rank), dense_rank (no gaps)."
    },
    {
      "name":     "RANK_COLUMN_NAME",
      "type":     "string",
      "required": true,
      "default":  "Row_Rank",
      "help":     "Name of the rank column added to every output row."
    },
    {
      "name":     "KEEP_TOP_N",
      "type":     "integer",
      "required": true,
      "default":  "1",
      "help":     "Number of top-ranked rows to keep per group. 0 = keep all rows (just adds rank column, no filtering)."
    },
    {
      "name":     "DISCARD_FILENAME",
      "type":     "string",
      "required": false,
      "default":  "",
      "help":     "Filename for rows that don't make the top-N cut. Leave empty to silently drop them."
    },
    {
      "name":     "OUTPUT_DIR",
      "type":     "string",
      "required": true,
      "default":  "./output",
      "help":     "Folder where output files are written."
    },
    {
      "name":     "OUTPUT_FILENAME",
      "type":     "string",
      "required": true,
      "default":  "ranked_output.csv",
      "help":     "Filename for the ranked (and optionally filtered) output file."
    },
    {
      "name":     "OUTPUT_FORMAT",
      "type":     "string",
      "required": true,
      "default":  "csv",
      "help":     "Output file format: csv, xlsx, json, parquet, tsv."
    }
  ]
}
```

**Field reference:**

| Field | Type | Description |
|---|---|---|
| `template_name` | string | Must exactly match the `{template_name}_template.py` filename stem |
| `display_name` | string | Human-readable label shown in the UI dropdown |
| `description` | string | Short purpose statement shown below the dropdown |
| `function_sig` | string | Contract signature displayed in the UI for reference |
| `parameters[].name` | string | Placeholder name (UPPERCASE) — must match `{{NAME}}` in the template |
| `parameters[].type` | string | `string` \| `integer` \| `boolean` \| `list` \| `dict` — used for UI input hints |
| `parameters[].required` | boolean | Whether the UI should flag this field as mandatory |
| `parameters[].default` | string | Pre-filled value shown in the UI input box |
| `parameters[].help` | string | Tooltip / helper text shown next to the input |

**Minimal entry (required fields only):**

```json
{
  "template_name": "file_union",
  "display_name":  "PS-02 — File Union",
  "description":   "Vertically stack multiple files into one consolidated output file.",
  "function_sig":  "preprocess(input_paths: list, output_columns=None) -> str",
  "parameters": [
    {"name": "OUTPUT_DIR",        "type": "string",  "required": true,  "default": "./output",              "help": "Folder where the output file is saved."},
    {"name": "OUTPUT_FILENAME",   "type": "string",  "required": true,  "default": "unioned_output.csv",    "help": "Name of the combined output file."},
    {"name": "OUTPUT_FORMAT",     "type": "string",  "required": true,  "default": "csv",                   "help": "Output format: csv, xlsx, json, parquet, tsv."},
    {"name": "ADD_SOURCE_TAG",    "type": "boolean", "required": true,  "default": "True",                  "help": "Add a column tracking which source file each row came from."},
    {"name": "SOURCE_TAG_COLUMN", "type": "string",  "required": false, "default": "Source_Filename",       "help": "Name of the source-tracking column (only used when ADD_SOURCE_TAG = True)."}
  ]
}
```

### 11.5 Parameter Input Format in the UI

The UI accepts parameters as a **JSON object**. For list/dict placeholders (e.g. `JOIN_STEPS`, `KEY_COLUMNS`, `VALUE_GROUPS`), provide standard JSON arrays or objects — the app converts them to Python literals before substitution.

**Example input for PS-05 (multi-key join):**

```json
{
  "JOIN_KEYS":       ["Account_Number", "Invoice_Date"],
  "JOIN_TYPE":       "inner",
  "LEFT_SUFFIX":     "_left",
  "RIGHT_SUFFIX":    "_right",
  "OUTPUT_DIR":      "./output",
  "OUTPUT_FILENAME": "multikey_joined.csv",
  "OUTPUT_FORMAT":   "csv"
}
```

### 11.6 Keeping the UI in Sync

When a template is modified or a new template is added:

1. Update or add the corresponding entry in `template_catalog.json`
2. Ensure `parameters[].name` matches every `{{PLACEHOLDER}}` in the template exactly
3. Restart `gradio_app.py` — it reads `template_catalog.json` at startup

> The UI only **generates** scripts. Running a generated script still requires runtime dependencies (`pandas`, `openpyxl`, etc.) to be installed in the execution environment.

*End of Documentation — Data Preprocessing Script Library v1.1*  
*v1.1 changes: PS-16 Rank Filter, PS-17 Filter by Value List, PS-02 folder-input + output_columns, Gradio UI section, template_catalog.json schema, requirements.txt, corrected directory structure and XLSX note*
