"""
tests/test_all_templates.py
===========================
Comprehensive end-to-end tests for all 18 PrepKit preprocessing templates.

Strategy
--------
- Each test method generates a script via generate_preprocessor(), exec()s it
  in an isolated namespace, then calls preprocess() with real temp-file CSV
  inputs and asserts the output exists and has at least one data row.
- All temp files and output dirs are created with tempfile helpers and cleaned
  up automatically via addCleanup() / tearDown().
- No network access, no external data files, no LLM calls.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Make sure the repo root is on sys.path so that
#   from preprocessing_library.generator import generate_preprocessor
# works whether tests are run from the repo root or the tests/ directory.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from preprocessing_library.generator import generate_preprocessor  # noqa: E402

_TEMPLATES_DIR = str(_REPO_ROOT / "preprocessing_library" / "templates")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_csv(path: str, content: str) -> str:
    """Write *content* to *path* and return *path*."""
    Path(path).write_text(content, encoding="utf-8")
    return path


def _make_csv(tmp_dir: str, filename: str, content: str) -> str:
    return _write_csv(os.path.join(tmp_dir, filename), content)


def _count_data_rows(csv_path: str) -> int:
    """Return the number of data rows (excluding header) in a CSV file."""
    lines = Path(csv_path).read_text(encoding="utf-8").splitlines()
    return max(0, len([l for l in lines if l.strip()]) - 1)


def _run_template(template_name: str, parameters: dict, input_paths, out_dir: str):
    """
    Generate a script for *template_name*, exec it in an isolated namespace,
    call preprocess() with *input_paths*, and return the result.

    *input_paths* can be a str (single file) or a list.
    """
    script_path = generate_preprocessor(
        template_name=template_name,
        parameters=parameters,
        output_script_name=f"_test_{template_name}.py",
        output_dir=out_dir,
        templates_dir=_TEMPLATES_DIR,
    )
    code = Path(script_path).read_text(encoding="utf-8")
    ns: dict = {}
    exec(compile(code, script_path, "exec"), ns)  # noqa: S102
    preprocess = ns["preprocess"]
    if isinstance(input_paths, list):
        return preprocess(input_paths)
    return preprocess(input_paths)


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

class TestAllTemplates(unittest.TestCase):

    def setUp(self) -> None:
        # Master scratch space — unique per test run
        self._tmp_roots: list[str] = []

    def _tmp(self) -> str:
        """Create and register a fresh temp directory."""
        d = tempfile.mkdtemp()
        self._tmp_roots.append(d)
        return d

    def tearDown(self) -> None:
        for d in self._tmp_roots:
            shutil.rmtree(d, ignore_errors=True)

    # ------------------------------------------------------------------
    # PS-01  file_detect_load
    # ------------------------------------------------------------------
    def test_ps01_file_detect_load(self) -> None:
        data_dir = self._tmp()
        out_dir = self._tmp()
        scripts_dir = self._tmp()

        src = _make_csv(data_dir, "sales.csv",
                        "id,product,amount\n1,Widget,100\n2,Gadget,200\n3,Doohick,300\n")

        result = _run_template(
            "file_detect_load",
            {
                "OUTPUT_DIR":             out_dir,
                "OUTPUT_FORMAT":          "csv",
                "OUTPUT_FILENAME_PREFIX": "clean_",
                "ENCODING_PRIMARY":       "utf-8",
                "ENCODING_FALLBACK_1":    "cp1252",
                "ENCODING_FALLBACK_2":    "latin-1",
            },
            src,
            scripts_dir,
        )

        self.assertTrue(Path(result).is_file(), f"Output file not found: {result}")
        self.assertGreater(_count_data_rows(result), 0)

    # ------------------------------------------------------------------
    # PS-02  file_union
    # ------------------------------------------------------------------
    def test_ps02_file_union(self) -> None:
        data_dir = self._tmp()
        out_dir = self._tmp()
        scripts_dir = self._tmp()

        a = _make_csv(data_dir, "jan.csv",
                      "id,amount\n1,100\n2,200\n3,300\n")
        b = _make_csv(data_dir, "feb.csv",
                      "id,amount\n4,400\n5,500\n")

        result = _run_template(
            "file_union",
            {
                "OUTPUT_DIR":        out_dir,
                "OUTPUT_FILENAME":   "union_out.csv",
                "OUTPUT_FORMAT":     "csv",
                "ADD_SOURCE_TAG":    "True",
                "SOURCE_TAG_COLUMN": "_source",
            },
            [a, b],
            scripts_dir,
        )

        self.assertTrue(Path(result).is_file(), f"Output file not found: {result}")
        self.assertGreaterEqual(_count_data_rows(result), 5)

    # ------------------------------------------------------------------
    # PS-03  file_join_two
    # ------------------------------------------------------------------
    def test_ps03_file_join_two(self) -> None:
        data_dir = self._tmp()
        out_dir = self._tmp()
        scripts_dir = self._tmp()

        left = _make_csv(data_dir, "customers.csv",
                         "cust_id,name\n1,Alice\n2,Bob\n3,Carol\n")
        right = _make_csv(data_dir, "orders.csv",
                          "cust_id,order_id,total\n1,101,500\n2,102,300\n2,103,150\n")

        result = _run_template(
            "file_join_two",
            {
                "JOIN_KEY":        "cust_id",
                "LEFT_KEY":        "",
                "RIGHT_KEY":       "",
                "JOIN_TYPE":       "inner",
                "LEFT_SUFFIX":     "_cust",
                "RIGHT_SUFFIX":    "_ord",
                "LEFT_FILENAME":   "customers.csv",
                "RIGHT_FILENAME":  "orders.csv",
                "OUTPUT_DIR":      out_dir,
                "OUTPUT_FILENAME": "joined.csv",
                "OUTPUT_FORMAT":   "csv",
            },
            [left, right],
            scripts_dir,
        )

        self.assertTrue(Path(result).is_file(), f"Output file not found: {result}")
        self.assertGreater(_count_data_rows(result), 0)

    # ------------------------------------------------------------------
    # PS-04  file_join_multi
    # ------------------------------------------------------------------
    def test_ps04_file_join_multi(self) -> None:
        data_dir = self._tmp()
        out_dir = self._tmp()
        scripts_dir = self._tmp()

        base = _make_csv(data_dir, "base.csv",
                         "pid,product\n1,Widget\n2,Gadget\n3,Doohick\n")
        prices = _make_csv(data_dir, "prices.csv",
                           "pid,price\n1,9.99\n2,19.99\n3,4.99\n")
        stock = _make_csv(data_dir, "stock.csv",
                          "pid,qty\n1,50\n2,20\n3,100\n")

        join_steps = json.dumps([
            {"file_index": 1, "join_key": "pid", "join_type": "left"},
            {"file_index": 2, "join_key": "pid", "join_type": "left"},
        ])

        result = _run_template(
            "file_join_multi",
            {
                "JOIN_STEPS":      join_steps,
                "OUTPUT_DIR":      out_dir,
                "OUTPUT_FILENAME": "multi_joined.csv",
                "OUTPUT_FORMAT":   "csv",
            },
            [base, prices, stock],
            scripts_dir,
        )

        self.assertTrue(Path(result).is_file(), f"Output file not found: {result}")
        self.assertGreater(_count_data_rows(result), 0)

    # ------------------------------------------------------------------
    # PS-05  file_join_multi_key
    # ------------------------------------------------------------------
    def test_ps05_file_join_multi_key(self) -> None:
        data_dir = self._tmp()
        out_dir = self._tmp()
        scripts_dir = self._tmp()

        left = _make_csv(data_dir, "left.csv",
                         "region,product,sales\nNorth,Widget,100\nSouth,Gadget,200\nNorth,Gadget,50\n")
        right = _make_csv(data_dir, "right.csv",
                          "region,product,target\nNorth,Widget,90\nSouth,Gadget,180\nNorth,Gadget,60\n")

        result = _run_template(
            "file_join_multi_key",
            {
                "JOIN_KEYS":       '["region", "product"]',
                "JOIN_TYPE":       "inner",
                "LEFT_SUFFIX":     "_l",
                "RIGHT_SUFFIX":    "_r",
                "LEFT_FILENAME":   "left.csv",
                "RIGHT_FILENAME":  "right.csv",
                "OUTPUT_DIR":      out_dir,
                "OUTPUT_FILENAME": "multikey_joined.csv",
                "OUTPUT_FORMAT":   "csv",
            },
            [left, right],
            scripts_dir,
        )

        self.assertTrue(Path(result).is_file(), f"Output file not found: {result}")
        self.assertGreater(_count_data_rows(result), 0)

    # ------------------------------------------------------------------
    # PS-06  file_denormalize
    # ------------------------------------------------------------------
    def test_ps06_file_denormalize(self) -> None:
        data_dir = self._tmp()
        out_dir = self._tmp()
        scripts_dir = self._tmp()

        header = _make_csv(data_dir, "master.csv",
                           "cust_id,name\n1,Alice\n2,Bob\n")
        detail = _make_csv(data_dir, "detail.csv",
                           "cust_id,invoice_no,amount\n1,INV001,500\n1,INV002,300\n2,INV003,800\n")

        result = _run_template(
            "file_denormalize",
            {
                "JOIN_KEY":        "cust_id",
                "JOIN_TYPE":       "left",
                "DETAIL_PREFIX":   "inv_",
                "HEADER_FILENAME": "master.csv",
                "DETAIL_FILENAME": "detail.csv",
                "OUTPUT_DIR":      out_dir,
                "OUTPUT_FILENAME": "denorm_out.csv",
                "OUTPUT_FORMAT":   "csv",
            },
            [header, detail],
            scripts_dir,
        )

        self.assertTrue(Path(result).is_file(), f"Output file not found: {result}")
        self.assertGreater(_count_data_rows(result), 0)

    # ------------------------------------------------------------------
    # PS-07  file_split_by_value
    # ------------------------------------------------------------------
    def test_ps07_file_split_by_value(self) -> None:
        data_dir = self._tmp()
        out_dir = self._tmp()
        scripts_dir = self._tmp()

        src = _make_csv(data_dir, "orders.csv",
                        "id,status,amount\n1,PAID,100\n2,OPEN,200\n3,PAID,300\n4,VOID,50\n5,OPEN,75\n")

        result_dir = _run_template(
            "file_split_by_value",
            {
                "SPLIT_COLUMN":         "status",
                "OUTPUT_DIR":           out_dir,
                "OUTPUT_FORMAT":        "csv",
                "FILENAME_TEMPLATE":    "status_{value}.csv",
                "INCLUDE_SPLIT_COLUMN": "True",
            },
            src,
            scripts_dir,
        )

        # Should have created at least one split file in out_dir
        out_files = list(Path(out_dir).glob("*.csv"))
        self.assertGreater(len(out_files), 0, "No split files found in output dir")
        # Each file must have at least one data row
        for f in out_files:
            self.assertGreater(_count_data_rows(str(f)), 0, f"Empty split file: {f}")

    # ------------------------------------------------------------------
    # PS-08  file_filter_to_files
    # ------------------------------------------------------------------
    def test_ps08_file_filter_to_files(self) -> None:
        data_dir = self._tmp()
        out_dir = self._tmp()
        scripts_dir = self._tmp()

        src = _make_csv(data_dir, "invoices.csv",
                        "id,status,amount\n1,PAID,100\n2,OPEN,200\n3,PAID,300\n4,VOID,50\n")

        filter_rules = json.dumps([
            {"condition": "status == 'PAID'", "output_filename": "paid.csv"},
            {"condition": "status == 'OPEN'", "output_filename": "open.csv"},
        ])

        result_dir = _run_template(
            "file_filter_to_files",
            {
                "FILTER_RULES":       filter_rules,
                "OUTPUT_DIR":         out_dir,
                "OUTPUT_FORMAT":      "csv",
                "UNMATCHED_FILENAME": "others.csv",
            },
            src,
            scripts_dir,
        )

        paid_path = Path(out_dir) / "paid.csv"
        open_path = Path(out_dir) / "open.csv"
        self.assertTrue(paid_path.is_file(), "paid.csv not created")
        self.assertTrue(open_path.is_file(), "open.csv not created")
        self.assertGreater(_count_data_rows(str(paid_path)), 0)
        self.assertGreater(_count_data_rows(str(open_path)), 0)

    # ------------------------------------------------------------------
    # PS-09  file_split_columns
    # ------------------------------------------------------------------
    def test_ps09_file_split_columns(self) -> None:
        data_dir = self._tmp()
        out_dir = self._tmp()
        scripts_dir = self._tmp()

        src = _make_csv(data_dir, "wide.csv",
                        "id,name,city,amount,currency\n"
                        "1,Alice,NYC,500,USD\n"
                        "2,Bob,LA,300,USD\n"
                        "3,Carol,Chicago,800,USD\n")

        column_groups = json.dumps([
            {"columns": ["name", "city"],          "output_filename": "address.csv"},
            {"columns": ["amount", "currency"],    "output_filename": "finance.csv"},
        ])

        result_dir = _run_template(
            "file_split_columns",
            {
                "COMMON_KEY_COLUMNS": '["id"]',
                "COLUMN_GROUPS":      column_groups,
                "OUTPUT_DIR":         out_dir,
                "OUTPUT_FORMAT":      "csv",
            },
            src,
            scripts_dir,
        )

        addr_path = Path(out_dir) / "address.csv"
        fin_path = Path(out_dir) / "finance.csv"
        self.assertTrue(addr_path.is_file(), "address.csv not created")
        self.assertTrue(fin_path.is_file(), "finance.csv not created")
        self.assertGreater(_count_data_rows(str(addr_path)), 0)
        self.assertGreater(_count_data_rows(str(fin_path)), 0)

    # ------------------------------------------------------------------
    # PS-10  file_deduplicate
    # ------------------------------------------------------------------
    def test_ps10_file_deduplicate(self) -> None:
        data_dir = self._tmp()
        out_dir = self._tmp()
        scripts_dir = self._tmp()

        src = _make_csv(data_dir, "dupes.csv",
                        "id,name,amount\n"
                        "1,Alice,100\n"
                        "1,Alice,100\n"
                        "2,Bob,200\n"
                        "3,Carol,300\n"
                        "3,Carol,300\n")

        result = _run_template(
            "file_deduplicate",
            {
                "KEY_COLUMNS":                '["id"]',
                "KEEP":                       "first",
                "OUTPUT_DIR":                 out_dir,
                "OUTPUT_FILENAME":            "deduped.csv",
                "DUPLICATES_REPORT_FILENAME": "dupes_report.csv",
                "OUTPUT_FORMAT":              "csv",
            },
            src,
            scripts_dir,
        )

        self.assertTrue(Path(result).is_file(), f"Output file not found: {result}")
        # 3 unique ids → 3 rows after dedup
        self.assertEqual(_count_data_rows(result), 3)

    # ------------------------------------------------------------------
    # PS-11  file_rename_columns
    # ------------------------------------------------------------------
    def test_ps11_file_rename_columns(self) -> None:
        data_dir = self._tmp()
        out_dir = self._tmp()
        scripts_dir = self._tmp()

        src = _make_csv(data_dir, "input.csv",
                        "cust_no,full_name,inv_amt\n"
                        "1,Alice,500\n2,Bob,300\n3,Carol,800\n")

        column_mapping = json.dumps({
            "cust_no":  "CustomerID",
            "full_name": "CustomerName",
            "inv_amt":  "InvoiceAmount",
        })

        result = _run_template(
            "file_rename_columns",
            {
                "COLUMN_MAPPING":  column_mapping,
                "DROP_UNMAPPED":   "False",
                "OUTPUT_DIR":      out_dir,
                "OUTPUT_FILENAME": "renamed.csv",
                "OUTPUT_FORMAT":   "csv",
            },
            src,
            scripts_dir,
        )

        self.assertTrue(Path(result).is_file(), f"Output file not found: {result}")
        header = Path(result).read_text(encoding="utf-8").splitlines()[0]
        self.assertIn("CustomerID", header)
        self.assertIn("CustomerName", header)
        self.assertIn("InvoiceAmount", header)
        self.assertGreater(_count_data_rows(result), 0)

    # ------------------------------------------------------------------
    # PS-12  file_handle_nulls
    # ------------------------------------------------------------------
    def test_ps12_file_handle_nulls(self) -> None:
        data_dir = self._tmp()
        out_dir = self._tmp()
        scripts_dir = self._tmp()

        src = _make_csv(data_dir, "nulls.csv",
                        "id,name,amount\n"
                        "1,Alice,100\n"
                        "2,,200\n"
                        "3,Carol,\n"
                        "4,Dave,400\n")

        null_rules = json.dumps([
            {"column": "name",   "strategy": "fill", "fill_value": "UNKNOWN"},
            {"column": "amount", "strategy": "fill", "fill_value": "0"},
        ])

        result = _run_template(
            "file_handle_nulls",
            {
                "NULL_RULES":           null_rules,
                "NULL_VALUES":          '["", "NULL", "N/A", "nan"]',
                "OUTPUT_DIR":           out_dir,
                "OUTPUT_FILENAME":      "nulls_handled.csv",
                "NULL_REPORT_FILENAME": "null_report.csv",
                "OUTPUT_FORMAT":        "csv",
            },
            src,
            scripts_dir,
        )

        self.assertTrue(Path(result).is_file(), f"Output file not found: {result}")
        self.assertGreater(_count_data_rows(result), 0)

    # ------------------------------------------------------------------
    # PS-13  file_cast_types
    # ------------------------------------------------------------------
    def test_ps13_file_cast_types(self) -> None:
        data_dir = self._tmp()
        out_dir = self._tmp()
        scripts_dir = self._tmp()

        src = _make_csv(data_dir, "types.csv",
                        "id,amount,active,date\n"
                        "1,100.5,true,2024-01-15\n"
                        "2,200.0,false,2024-02-20\n"
                        "3,300.75,true,2024-03-10\n")

        type_rules = json.dumps([
            {"column": "id",     "target_type": "integer", "format": ""},
            {"column": "amount", "target_type": "float",   "format": ""},
            {"column": "active", "target_type": "boolean", "format": ""},
        ])

        result = _run_template(
            "file_cast_types",
            {
                "TYPE_RULES":                 type_rules,
                "STRIP_CURRENCY":             "False",
                "TRIM_STRINGS":               "True",
                "ON_ERROR":                   "nullify",
                "OUTPUT_DIR":                 out_dir,
                "OUTPUT_FILENAME":            "cast_out.csv",
                "CAST_ERROR_REPORT_FILENAME": "cast_errors.csv",
                "OUTPUT_FORMAT":              "csv",
            },
            src,
            scripts_dir,
        )

        self.assertTrue(Path(result).is_file(), f"Output file not found: {result}")
        self.assertGreater(_count_data_rows(result), 0)

    # ------------------------------------------------------------------
    # PS-14  file_aggregate
    # ------------------------------------------------------------------
    def test_ps14_file_aggregate(self) -> None:
        data_dir = self._tmp()
        out_dir = self._tmp()
        scripts_dir = self._tmp()

        src = _make_csv(data_dir, "sales.csv",
                        "region,product,amount\n"
                        "North,Widget,100\n"
                        "North,Widget,150\n"
                        "South,Gadget,200\n"
                        "South,Gadget,250\n"
                        "North,Gadget,300\n")

        aggregations = json.dumps([
            {"column": "amount", "function": "sum"},
            {"column": "amount", "function": "count"},
        ])

        result = _run_template(
            "file_aggregate",
            {
                "GROUP_BY_COLUMNS": '["region", "product"]',
                "AGGREGATIONS":     aggregations,
                "OUTPUT_DIR":       out_dir,
                "OUTPUT_FILENAME":  "agg_out.csv",
                "OUTPUT_FORMAT":    "csv",
            },
            src,
            scripts_dir,
        )

        self.assertTrue(Path(result).is_file(), f"Output file not found: {result}")
        self.assertGreater(_count_data_rows(result), 0)

    # ------------------------------------------------------------------
    # PS-15  file_delta_load
    # ------------------------------------------------------------------
    def test_ps15_file_delta_load(self) -> None:
        data_dir = self._tmp()
        out_dir = self._tmp()
        scripts_dir = self._tmp()

        # "current" snapshot — id 4 is new, id 2 amount changed, id 3 deleted
        current = _make_csv(data_dir, "current.csv",
                            "id,name,amount\n"
                            "1,Alice,100\n"
                            "2,Bob,999\n"
                            "4,Dave,400\n")
        baseline = _make_csv(data_dir, "baseline.csv",
                             "id,name,amount\n"
                             "1,Alice,100\n"
                             "2,Bob,200\n"
                             "3,Carol,300\n")

        result = _run_template(
            "file_delta_load",
            {
                "KEY_COLUMNS":         '["id"]',
                "DELTA_MODE":          "full_delta",
                "COMPARE_COLUMNS":     "[]",
                "DELTA_STATUS_COLUMN": "delta_status",
                "NEW_FILENAME":        "current.csv",
                "OLD_FILENAME":        "baseline.csv",
                "OUTPUT_DIR":          out_dir,
                "OUTPUT_FILENAME":     "delta_out.csv",
                "OUTPUT_FORMAT":       "csv",
            },
            [current, baseline],
            scripts_dir,
        )

        self.assertTrue(Path(result).is_file(), f"Output file not found: {result}")
        self.assertGreater(_count_data_rows(result), 0)

    # ------------------------------------------------------------------
    # PS-16  file_rank_filter
    # ------------------------------------------------------------------
    def test_ps16_file_rank_filter(self) -> None:
        data_dir = self._tmp()
        out_dir = self._tmp()
        scripts_dir = self._tmp()

        src = _make_csv(data_dir, "scores.csv",
                        "region,salesperson,amount\n"
                        "North,Alice,500\n"
                        "North,Bob,300\n"
                        "North,Carol,700\n"
                        "South,Dave,400\n"
                        "South,Eve,600\n")

        result = _run_template(
            "file_rank_filter",
            {
                "PARTITION_BY":    '["region"]',
                "RANK_BY_COLUMN":  "amount",
                "RANK_ORDER":      "desc",
                "RANK_METHOD":     "row_number",
                "RANK_COLUMN_NAME": "rank",
                "KEEP_TOP_N":      "1",
                "DISCARD_FILENAME": "non_top.csv",
                "OUTPUT_DIR":      out_dir,
                "OUTPUT_FILENAME": "ranked.csv",
                "OUTPUT_FORMAT":   "csv",
            },
            src,
            scripts_dir,
        )

        self.assertTrue(Path(result).is_file(), f"Output file not found: {result}")
        # Top-1 per region (North + South) = 2 rows
        self.assertEqual(_count_data_rows(result), 2)

    # ------------------------------------------------------------------
    # PS-17  file_filter_by_values
    # ------------------------------------------------------------------
    def test_ps17_file_filter_by_values(self) -> None:
        data_dir = self._tmp()
        out_dir = self._tmp()
        scripts_dir = self._tmp()

        src = _make_csv(data_dir, "orders.csv",
                        "id,status,amount\n"
                        "1,PAID,100\n"
                        "2,OPEN,200\n"
                        "3,PAID,300\n"
                        "4,VOID,50\n"
                        "5,PENDING,75\n")

        value_groups = json.dumps([
            {"values": ["PAID"],          "output_filename": "paid.csv"},
            {"values": ["OPEN", "PENDING"], "output_filename": "open_pending.csv"},
        ])

        result_dir = _run_template(
            "file_filter_by_values",
            {
                "FILTER_COLUMN":  "status",
                "VALUE_GROUPS":   value_groups,
                "CASE_SENSITIVE": "True",
                "OTHERS_FILENAME": "others.csv",
                "OUTPUT_DIR":     out_dir,
                "OUTPUT_FORMAT":  "csv",
            },
            src,
            scripts_dir,
        )

        paid_path = Path(out_dir) / "paid.csv"
        open_path = Path(out_dir) / "open_pending.csv"
        self.assertTrue(paid_path.is_file(), "paid.csv not created")
        self.assertTrue(open_path.is_file(), "open_pending.csv not created")
        self.assertGreater(_count_data_rows(str(paid_path)), 0)
        self.assertGreater(_count_data_rows(str(open_path)), 0)

    # ------------------------------------------------------------------
    # PS-18  file_join_filter_agg
    # ------------------------------------------------------------------
    def test_ps18_file_join_filter_agg(self) -> None:
        data_dir = self._tmp()
        out_dir = self._tmp()
        scripts_dir = self._tmp()

        left = _make_csv(data_dir, "orders.csv",
                         "cust_id,order_id,amount\n"
                         "1,101,500\n1,102,300\n2,103,800\n3,104,200\n3,105,150\n")
        right = _make_csv(data_dir, "customers.csv",
                          "cust_id,region\n1,North\n2,South\n3,North\n")

        aggregations = json.dumps([
            {"column": "amount", "function": "sum",   "output_column": "total_amount"},
            {"column": "order_id", "function": "count", "output_column": "order_count"},
        ])

        result = _run_template(
            "file_join_filter_agg",
            {
                "JOIN_KEYS":        '["cust_id"]',
                "JOIN_TYPE":        "inner",
                "LEFT_FILENAME":    "orders.csv",
                "RIGHT_FILENAME":   "customers.csv",
                "WHERE_CONDITION":  "amount > 100",
                "GROUP_BY_COLUMNS": '["cust_id", "region"]',
                "AGGREGATIONS":     aggregations,
                "RANK_BY_COLUMN":   "",
                "RANK_ORDER":       "desc",
                "RANK_COLUMN_NAME": "rank",
                "KEEP_TOP_N":       "0",
                "OUTPUT_DIR":       out_dir,
                "OUTPUT_FILENAME":  "join_filter_agg.csv",
                "OUTPUT_FORMAT":    "csv",
            },
            [left, right],
            scripts_dir,
        )

        self.assertTrue(Path(result).is_file(), f"Output file not found: {result}")
        self.assertGreater(_count_data_rows(result), 0)


if __name__ == "__main__":
    unittest.main()
