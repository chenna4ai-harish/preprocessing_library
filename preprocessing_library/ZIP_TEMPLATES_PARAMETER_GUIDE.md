# ZIP Templates — Parameter Reference Guide

This guide explains every parameter across the five ZIP-input templates.
It is written for end users — no coding knowledge required.

> **How ZIP templates work (all five)**
> When you provide a ZIP file as input, the template automatically extracts
> **every file** inside that ZIP to your output directory before doing any
> processing. If you provide two ZIPs that are the same file, it is extracted
> only once. The folder that contains your ZIP is also scanned — any other
> ZIPs sitting alongside are extracted automatically too.
> Your output directory will therefore contain all extracted files plus the
> processed result file(s).

---

## 1. PS-02Z — Union ZIP Files (`file_union_zip`)

**What it does:** Pulls the same data file out of multiple ZIPs and stacks
all the rows into one combined output file (a vertical union / append).

**Typical use case:** You receive a monthly sales ZIP every month. Each ZIP
contains `sales.csv`. You want one merged file covering all months.

---

### Parameters

#### `INNER_FILE`
| | |
|---|---|
| **Type** | Text |
| **Default** | *(blank)* |
| **Required?** | Recommended |

The **exact filename** that holds data inside each ZIP. Every ZIP you provide
must contain a file with this name.

**Why we use it:** Without this the template picks the first supported file
it finds in each ZIP, which may differ between ZIPs and produce a wrong union.

**Example:**
```
INNER_FILE = "sales.csv"
```
If your ZIPs contain `sales.csv`, `readme.txt`, and `schema.json`, only
`sales.csv` is used for the union. The others are still extracted but not merged.

Leave blank (`""`) to auto-pick the first CSV/Excel/JSON/XML found in each ZIP.

---

#### `OUTPUT_DIR`
| | |
|---|---|
| **Type** | Folder path |
| **Default** | Same folder as the first input ZIP |

Where all output files are written — both the extracted ZIP contents and the
merged union file.

**Example:**
```
OUTPUT_DIR = "C:\Reports\2025\merged"
```

---

#### `OUTPUT_FILENAME`
| | |
|---|---|
| **Type** | Text |
| **Default** | `union.csv` |

Name of the merged output file that contains all stacked rows.

**Example:**
```
OUTPUT_FILENAME = "all_sales_2025.csv"
```

---

#### `OUTPUT_FORMAT`
| | |
|---|---|
| **Type** | Text |
| **Choices** | `csv` \| `xlsx` \| `json` \| `parquet` \| `tsv` |
| **Default** | `csv` |

File format of the merged output.

**Example:** Use `xlsx` if the result will be opened in Excel.

---

#### `ADD_SOURCE_TAG`
| | |
|---|---|
| **Type** | True / False |
| **Default** | `True` |

When `True`, a new column is added to every row showing **which ZIP file that
row came from**. Lets you trace the origin of any row after merging.

**Why we use it:** After stacking 12 monthly ZIPs into one file, you can
filter by `_source_file = "jan.zip"` to see only January rows.

**Example result column:**

| order_id | amount | _source_file |
|---|---|---|
| 1001 | 500 | jan.zip |
| 1002 | 300 | feb.zip |

---

#### `SOURCE_TAG_COLUMN`
| | |
|---|---|
| **Type** | Text |
| **Default** | `_source_file` |

The name of the source-tag column added when `ADD_SOURCE_TAG = True`.

**Example:**
```
SOURCE_TAG_COLUMN = "month_source"
```

---

---

## 2. PS-05Z — Join Two ZIP Files (Multi-Key) (`file_join_multi_key_zip`)

**What it does:** Extracts a data file from each of two ZIPs and joins them
using **multiple columns at the same time** (a composite key).

**Typical use case:** You have a `customers.zip` and an `orders.zip`. A single
customer can have the same ID across different regions, so you need to match on
both `customer_id` **and** `region` together to get a unique match.

---

### Parameters

#### `LEFT_INNER_FILE`
| | |
|---|---|
| **Type** | Text |
| **Default** | *(blank)* |

The filename inside the **left (primary) ZIP** to use as the data file.

**Example:**
```
LEFT_INNER_FILE = "customers.csv"
```

Leave blank to auto-pick the first supported file in the left ZIP.

---

#### `RIGHT_INNER_FILE`
| | |
|---|---|
| **Type** | Text |
| **Default** | *(blank)* |

The filename inside the **right ZIP** to use as the data file.

**Example:**
```
RIGHT_INNER_FILE = "orders.csv"
```

---

#### `LEFT_USECOLS`
| | |
|---|---|
| **Type** | List of column names |
| **Default** | `[]` (load all columns) |

Load only these columns from the left file. Reduces memory and speeds up
processing when files are wide.

**Why we use it:** If `customers.csv` has 40 columns but you only need
`customer_id`, `region`, and `name` for this join, list just those three.

**Example:**
```
LEFT_USECOLS = ["customer_id", "region", "name"]
```

---

#### `RIGHT_USECOLS`
| | |
|---|---|
| **Type** | List of column names |
| **Default** | `[]` (load all columns) |

Same as `LEFT_USECOLS` but for the right file.

**Example:**
```
RIGHT_USECOLS = ["customer_id", "region", "order_date", "amount"]
```

---

#### `DEDUP_RIGHT_BY`
| | |
|---|---|
| **Type** | Text (single column name) |
| **Default** | *(blank — skip dedup)* |

Before joining, remove duplicate rows from the right file based on this column.
Only the first (or last) occurrence of each value is kept.

**Why we use it:** If `orders.csv` has multiple rows per customer due to a
data export bug, deduplicate first to avoid row multiplication after the join.

**Example:**
```
DEDUP_RIGHT_BY = "order_id"
```

---

#### `DEDUP_KEEP`
| | |
|---|---|
| **Type** | Text |
| **Choices** | `first` \| `last` |
| **Default** | `first` |

Which duplicate row to keep when `DEDUP_RIGHT_BY` is set.

- `first` — keep the earliest occurrence
- `last` — keep the most recent occurrence

---

#### `JOIN_KEYS`
| | |
|---|---|
| **Type** | List of column names |
| **Default** | `["id", "date"]` |

The columns that **both files share** and that are used together to match rows.
This is the core parameter of a multi-key join.

**Why we use it:** When a single column is not enough to uniquely identify a
match, you combine multiple columns. For example, the same `customer_id = 101`
may exist in both `region = "North"` and `region = "South"` — matching on ID
alone would give wrong results.

**Example:**
```
JOIN_KEYS = ["customer_id", "region"]
```

---

#### `LEFT_KEYS`
| | |
|---|---|
| **Type** | List of column names |
| **Default** | `[]` (use JOIN_KEYS) |

Use this **only** when the join columns have different names in the left file
than in the right file. Overrides `JOIN_KEYS` for the left side only.

**Example:** Left file calls it `cust_id`, right file calls it `customer_id`.
```
LEFT_KEYS  = ["cust_id", "region"]
RIGHT_KEYS = ["customer_id", "region"]
```

---

#### `RIGHT_KEYS`
| | |
|---|---|
| **Type** | List of column names |
| **Default** | `[]` (use JOIN_KEYS) |

Same as `LEFT_KEYS` but for the right file. Must have the same number of
entries as `LEFT_KEYS`.

---

#### `JOIN_TYPE`
| | |
|---|---|
| **Type** | Text |
| **Choices** | `inner` \| `left` \| `right` \| `outer` |
| **Default** | `inner` |

Controls which rows appear in the output:

| Value | Keeps |
|---|---|
| `inner` | Only rows that match in **both** files |
| `left` | All rows from the left file; unmatched right rows are blank |
| `right` | All rows from the right file; unmatched left rows are blank |
| `outer` | All rows from **both** files regardless of matches |

**Example:** Use `left` when you want all customers, even those with no orders.

---

#### `LEFT_SUFFIX` / `RIGHT_SUFFIX`
| | |
|---|---|
| **Type** | Text |
| **Default** | `_left` / `_right` |

When both files have a column with the same name (other than the join key),
these suffixes are added to distinguish them in the output.

**Example:** Both files have a `status` column.
```
LEFT_SUFFIX  = "_cust"
RIGHT_SUFFIX = "_order"
```
Output will have `status_cust` and `status_order`.

---

#### `OUTPUT_DROP_COLUMNS`
| | |
|---|---|
| **Type** | List of column names |
| **Default** | `[]` (keep all) |

Columns to remove from the final joined result before writing.

**Why we use it:** The join may bring in technical or redundant columns
(e.g. internal IDs, timestamps) that you don't need in the output.

**Example:**
```
OUTPUT_DROP_COLUMNS = ["internal_ref", "load_timestamp"]
```

---

#### `INSERT_COLUMN` / `INSERT_AFTER_COLUMN`
| | |
|---|---|
| **Type** | Text |
| **Default** | *(blank — skip reordering)* |

Moves one column to immediately after another column in the output.

**Why we use it:** After a join, important columns like `status` may end up
at the far right. Use this to bring them into a more readable position.

**Example:** Move `status` to appear right after `customer_id`.
```
INSERT_COLUMN       = "status"
INSERT_AFTER_COLUMN = "customer_id"
```

---

#### `OUTPUT_DIR` / `OUTPUT_FILENAME` / `OUTPUT_FORMAT`

Same meaning as in PS-02Z above. See those descriptions.

---

---

## 3. PS-06Z — Denormalize ZIP Files (`file_denormalize_zip`)

**What it does:** Extracts a **header (master)** file from one ZIP and a
**detail** file from another ZIP, then flattens them into one wide file where
each detail row carries all its parent header columns alongside it.

**Typical use case:** `invoices.zip` contains invoice headers
(`invoice_id`, `customer`, `date`). `line_items.zip` contains invoice lines
(`invoice_id`, `product`, `qty`, `price`). You want one flat file with every
line item alongside its invoice header.

---

### Parameters

#### `LEFT_INNER_FILE`
The filename to extract from the **header/master ZIP**.

**Example:**
```
LEFT_INNER_FILE = "invoices.csv"
```

#### `RIGHT_INNER_FILE`
The filename to extract from the **detail ZIP**.

**Example:**
```
RIGHT_INNER_FILE = "line_items.csv"
```

---

#### `LEFT_USECOLS` / `RIGHT_USECOLS`
Load only specific columns from the header or detail file.

**Example:** Only need invoice date and customer from the header:
```
LEFT_USECOLS = ["invoice_id", "customer", "date"]
```

---

#### `DEDUP_RIGHT_BY` / `DEDUP_KEEP`
Remove duplicates from the detail file before joining.

**Example:** If line items have duplicate entries per product, dedup on `line_id`:
```
DEDUP_RIGHT_BY = "line_id"
DEDUP_KEEP     = "first"
```

---

#### `JOIN_KEY`
| | |
|---|---|
| **Type** | Text (single column name) |
| **Default** | `id` |

The column that links a detail row back to its header row. Must exist in
both files with the same name. If the names differ, use `LEFT_KEY`/`RIGHT_KEY`.

**Example:**
```
JOIN_KEY = "invoice_id"
```

---

#### `LEFT_KEY` / `RIGHT_KEY`
| | |
|---|---|
| **Type** | Text |
| **Default** | *(blank — use JOIN_KEY)* |

Override `JOIN_KEY` when the linking column has a different name in each file.

**Example:** Header file has `inv_id`, detail file has `invoice_id`:
```
LEFT_KEY  = "inv_id"
RIGHT_KEY = "invoice_id"
```

---

#### `JOIN_TYPE`
Controls which rows appear. Typically `left` for denormalization — keeps all
header rows even if a header has no detail lines.

---

#### `DETAIL_PREFIX`
| | |
|---|---|
| **Type** | Text |
| **Default** | `detail_` |

A prefix added to **every detail column** in the output (except the join key).
This makes it clear which columns came from the detail file.

**Why we use it:** Both files may have a column called `status` or `date`.
The prefix avoids confusion and name collisions.

**Example:**
```
DETAIL_PREFIX = "line_"
```
Output columns: `invoice_id`, `customer`, `date`, `line_product`, `line_qty`, `line_price`

---

#### `LEFT_SUFFIX` / `RIGHT_SUFFIX`
Suffix added to any remaining overlapping column names that `DETAIL_PREFIX`
didn't resolve. Usually left at defaults `_left` / `_right`.

---

#### `OUTPUT_DROP_COLUMNS`
Columns to remove from the flattened output.

**Example:** Drop the redundant detail-side join key that pandas keeps:
```
OUTPUT_DROP_COLUMNS = ["line_invoice_id"]
```

---

#### `INSERT_COLUMN` / `INSERT_AFTER_COLUMN`
Reposition a column in the output. Useful if `DETAIL_PREFIX` pushed an
important column far to the right.

---

#### `OUTPUT_DIR` / `OUTPUT_FILENAME` / `OUTPUT_FORMAT`
Where to write, what to name it, and in what format. See PS-02Z descriptions.

---

---

## 4. PS-19Z — Column Value Split from ZIP (`file_column_split_zip`)

**What it does:** Extracts a data file from a ZIP, then splits its rows into
**separate output files** based on the value of one chosen column. Each group
of values goes to its own named file.

**Typical use case:** `transactions.zip` contains `transactions.csv` with a
`status` column. You want separate files for `APPROVED` rows, `REJECTED` rows,
and a third file for anything else.

---

### Parameters

#### `INNER_FILE`
| | |
|---|---|
| **Type** | Text |
| **Default** | *(blank)* |

The filename inside the ZIP to load and split.

**Example:**
```
INNER_FILE = "transactions.csv"
```

Leave blank to auto-pick the first supported file in the ZIP.

---

#### `SPLIT_COLUMN`
| | |
|---|---|
| **Type** | Text (column name) |
| **Required?** | Yes |

The column whose values determine which output file each row goes to.

**Example:**
```
SPLIT_COLUMN = "status"
```

---

#### `GROUPS`
| | |
|---|---|
| **Type** | Table / List of groups |
| **Required?** | Yes |

Defines the output groups. Each group has three fields:

| Field | Meaning | Example |
|---|---|---|
| `label` | A friendly name for this group (for your reference) | `approved` |
| `values` | The column values that belong to this group (comma-separated) | `APPROVED, CONFIRMED` |
| `output_filename` | The file to write these rows into | `approved.csv` |

**Why we use it:** You control exactly which values map to which file. A row
is placed in the **first group whose values list it matches** (first-match-wins).

**Example setup:**

| label | values | output_filename |
|---|---|---|
| approved | APPROVED, CONFIRMED | approved.csv |
| rejected | REJECTED, DECLINED | rejected.csv |
| pending | PENDING | pending.csv |

Rows with `status = "APPROVED"` → `approved.csv`
Rows with `status = "REJECTED"` → `rejected.csv`
Rows with `status = "PENDING"` → `pending.csv`

---

#### `CASE_SENSITIVE`
| | |
|---|---|
| **Type** | True / False |
| **Default** | `False` |

Whether the value matching is case-sensitive.

- `False` — `"approved"`, `"APPROVED"`, `"Approved"` all match the same group
- `True` — only an exact case match works

**Why we use it:** Real data is inconsistent. Keeping `False` means `"active"`
and `"ACTIVE"` are treated as the same value, avoiding missed rows.

---

#### `INCLUDE_SPLIT_COLUMN`
| | |
|---|---|
| **Type** | True / False |
| **Default** | `True` |

Whether to keep the `SPLIT_COLUMN` in the output files.

- `True` — the `status` column appears in every output file
- `False` — the `status` column is dropped (since all rows in one file already have the same value, it may be redundant)

---

#### `NULL_HANDLING`
| | |
|---|---|
| **Type** | Text |
| **Choices** | `separate_file` \| `merge_into_remaining` \| `discard` |
| **Default** | `merge_into_remaining` |

What to do with rows where `SPLIT_COLUMN` has a blank / null value.

| Value | Behaviour |
|---|---|
| `separate_file` | Write null rows to the file named in `NULL_FILENAME` |
| `merge_into_remaining` | Treat null rows as unmatched — add them to the remaining file |
| `discard` | Drop null rows silently |

---

#### `NULL_FILENAME`
| | |
|---|---|
| **Type** | Text |
| **Default** | `nulls.csv` |

The output file for null rows. Only used when `NULL_HANDLING = separate_file`.

**Example:**
```
NULL_FILENAME = "unknown_status.csv"
```

---

#### `REMAINING_HANDLING`
| | |
|---|---|
| **Type** | Text |
| **Choices** | `separate_file` \| `discard` |
| **Default** | `separate_file` |

What to do with rows that did not match **any** group.

| Value | Behaviour |
|---|---|
| `separate_file` | Write unmatched rows to the file named in `REMAINING_FILENAME` |
| `discard` | Drop unmatched rows silently |

**Why we use it:** Protects you from silently losing data. If a new value like
`"ON_HOLD"` appears that isn't in any group, it lands in the remaining file
instead of being discarded.

---

#### `REMAINING_FILENAME`
| | |
|---|---|
| **Type** | Text |
| **Default** | `remaining.csv` |

The output file for rows matching no group. Only used when
`REMAINING_HANDLING = separate_file`.

**Example:**
```
REMAINING_FILENAME = "unclassified.csv"
```

---

#### `OUTPUT_DIR`
Where all output files (extracted + split results) are written.

#### `OUTPUT_FORMAT`
Format of the split output files: `csv` \| `xlsx` \| `json` \| `parquet` \| `tsv`.

---

---

## 5. PS-18Z — Join ZIP Files, Filter & Aggregate (`file_join_filter_agg_zip`)

**What it does:** Extracts a data file from each of two ZIPs, joins them,
optionally filters rows with a condition, groups and aggregates the result,
and optionally ranks the groups. All in one step.

**Typical use case:** `customers.zip` and `orders.zip`. Join on `customer_id`,
keep only orders above £100, then count orders and sum amounts per region,
and rank regions by total amount descending.

---

### Parameters

#### `LEFT_INNER_FILE` / `RIGHT_INNER_FILE`
Same meaning as in PS-05Z. Filename to extract from left and right ZIPs.

**Example:**
```
LEFT_INNER_FILE  = "customers.csv"
RIGHT_INNER_FILE = "orders.csv"
```

---

#### `LEFT_USECOLS` / `RIGHT_USECOLS`
Load only these columns from left/right files. Leave `[]` to load all.

---

#### `DEDUP_RIGHT_BY` / `DEDUP_KEEP`
Remove duplicates from the right file before joining. Same as PS-05Z.

---

#### `JOIN_KEYS`
| | |
|---|---|
| **Type** | List of column names |
| **Default** | `["id"]` |

One or more columns used to match rows between the two files.
Unlike PS-05Z, these must have the **same name** in both files.

**Example:**
```
JOIN_KEYS = ["customer_id"]
```

---

#### `JOIN_TYPE`
`inner` \| `left` \| `right` \| `outer`. Same meaning as PS-05Z.

---

#### `LEFT_SUFFIX` / `RIGHT_SUFFIX`
Suffixes for overlapping column names. Same as PS-05Z.

---

#### `WHERE_CONDITION`
| | |
|---|---|
| **Type** | Text (pandas query expression) |
| **Default** | *(blank — no filter)* |

A filter applied **after** the join. Only rows matching this condition are
passed to the aggregation step. Leave blank to keep all joined rows.

**Why we use it:** You may only want to aggregate meaningful data — for example,
only completed orders, or only transactions above a threshold.

**Syntax:** Same as a SQL WHERE clause, but using Python comparison operators.

**Examples:**
```
WHERE_CONDITION = "amount > 100"
WHERE_CONDITION = "status == 'COMPLETED' and region == 'North'"
WHERE_CONDITION = "amount > 0 and order_date >= '2025-01-01'"
```

Leave blank (`""`) to skip filtering entirely.

---

#### `GROUP_BY_COLUMNS`
| | |
|---|---|
| **Type** | List of column names |
| **Default** | `["category"]` |

Columns to group by before applying aggregations.

**Example:** Count and sum orders per region and product category:
```
GROUP_BY_COLUMNS = ["region", "category"]
```

---

#### `AGGREGATIONS`
| | |
|---|---|
| **Type** | Table / List of aggregation rules |

Defines what calculations to perform on each group.
Each row in the table has three fields:

| Field | Meaning | Example |
|---|---|---|
| `column` | The column to aggregate. Use `*` to count rows. | `amount` |
| `function` | The aggregation function | `sum` |
| `output_column` | The name of the result column in output | `total_amount` |

**Available functions:** `count` `sum` `mean` `min` `max` `nunique` `first` `last` `std`

**Example setup:**

| column | function | output_column |
|---|---|---|
| * | count | order_count |
| amount | sum | total_amount |
| amount | mean | avg_order_value |
| customer_id | nunique | unique_customers |

- `*` with `count` → counts how many rows are in each group
- `nunique` → counts distinct values (useful for unique customer counts)

---

#### `RANK_BY_COLUMN`
| | |
|---|---|
| **Type** | Text (column name) |
| **Default** | *(blank — skip ranking)* |

After aggregation, rank the groups by this column. Leave blank to skip ranking.

**Example:** Rank groups by total amount:
```
RANK_BY_COLUMN = "total_amount"
```

---

#### `RANK_ORDER`
| | |
|---|---|
| **Type** | Text |
| **Choices** | `asc` \| `desc` |
| **Default** | `desc` |

- `desc` — rank 1 = highest value (top performers first)
- `asc` — rank 1 = lowest value (smallest first)

---

#### `RANK_COLUMN_NAME`
| | |
|---|---|
| **Type** | Text |
| **Default** | `_rank` |

The name of the rank column added to the output.

**Example:**
```
RANK_COLUMN_NAME = "sales_rank"
```

---

#### `KEEP_TOP_N`
| | |
|---|---|
| **Type** | Integer |
| **Default** | `0` (keep all) |

After ranking, keep only the top N rows. Set to `0` to keep all rows
(the rank column is still added, you just don't filter by it).

**Why we use it:** To get a "top 10 regions by sales" or "top 5 products by
order volume" report directly from the template.

**Example:**
```
KEEP_TOP_N = 10
```

---

#### `OUTPUT_DROP_COLUMNS`
Remove columns from the final result before writing.

**Example:** Drop intermediate columns you don't need in the report:
```
OUTPUT_DROP_COLUMNS = ["internal_id", "load_date"]
```

---

#### `INSERT_COLUMN` / `INSERT_AFTER_COLUMN`
Reposition a column in the final output. Example: move `sales_rank` to
appear right after `region`.

---

#### `OUTPUT_DIR` / `OUTPUT_FILENAME` / `OUTPUT_FORMAT`
Where to write, what to name it, and in what format.

---

---

## Quick Parameter Reference — All Five Templates

| Parameter | PS-02Z Union | PS-05Z Multi-Key | PS-06Z Denorm | PS-19Z Split | PS-18Z Join+Agg |
|---|:---:|:---:|:---:|:---:|:---:|
| `INNER_FILE` | ✓ | — | — | ✓ | — |
| `LEFT_INNER_FILE` | — | ✓ | ✓ | — | ✓ |
| `RIGHT_INNER_FILE` | — | ✓ | ✓ | — | ✓ |
| `LEFT_USECOLS` | — | ✓ | ✓ | — | ✓ |
| `RIGHT_USECOLS` | — | ✓ | ✓ | — | ✓ |
| `DEDUP_RIGHT_BY` | — | ✓ | ✓ | — | ✓ |
| `DEDUP_KEEP` | — | ✓ | ✓ | — | ✓ |
| `JOIN_KEY` | — | — | ✓ | — | — |
| `LEFT_KEY / RIGHT_KEY` | — | — | ✓ | — | — |
| `JOIN_KEYS` | — | ✓ | — | — | ✓ |
| `LEFT_KEYS / RIGHT_KEYS` | — | ✓ | — | — | — |
| `JOIN_TYPE` | — | ✓ | ✓ | — | ✓ |
| `LEFT_SUFFIX / RIGHT_SUFFIX` | — | ✓ | ✓ | — | ✓ |
| `DETAIL_PREFIX` | — | — | ✓ | — | — |
| `WHERE_CONDITION` | — | — | — | — | ✓ |
| `GROUP_BY_COLUMNS` | — | — | — | — | ✓ |
| `AGGREGATIONS` | — | — | — | — | ✓ |
| `RANK_BY_COLUMN` | — | — | — | — | ✓ |
| `RANK_ORDER` | — | — | — | — | ✓ |
| `RANK_COLUMN_NAME` | — | — | — | — | ✓ |
| `KEEP_TOP_N` | — | — | — | — | ✓ |
| `SPLIT_COLUMN` | — | — | — | ✓ | — |
| `GROUPS` | — | — | — | ✓ | — |
| `CASE_SENSITIVE` | — | — | — | ✓ | — |
| `INCLUDE_SPLIT_COLUMN` | — | — | — | ✓ | — |
| `NULL_HANDLING` | — | — | — | ✓ | — |
| `NULL_FILENAME` | — | — | — | ✓ | — |
| `REMAINING_HANDLING` | — | — | — | ✓ | — |
| `REMAINING_FILENAME` | — | — | — | ✓ | — |
| `ADD_SOURCE_TAG` | ✓ | — | — | — | — |
| `SOURCE_TAG_COLUMN` | ✓ | — | — | — | — |
| `OUTPUT_DROP_COLUMNS` | — | ✓ | ✓ | — | ✓ |
| `INSERT_COLUMN` | — | ✓ | ✓ | — | ✓ |
| `INSERT_AFTER_COLUMN` | — | ✓ | ✓ | — | ✓ |
| `OUTPUT_DIR` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `OUTPUT_FILENAME` | ✓ | ✓ | ✓ | — | ✓ |
| `OUTPUT_FORMAT` | ✓ | ✓ | ✓ | ✓ | ✓ |
