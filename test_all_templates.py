"""
Test all 18 preprocessing templates against test_data files.
"""
import os, sys, tempfile, inspect
from pathlib import Path
from preprocessing_library import generate_preprocessor

BASE  = r'C:/Users/91917/Desktop/Python_Scripts/test_data'
OUT   = r'C:/Users/91917/Desktop/Python_Scripts/test_output'
TMPL  = r'C:/Users/91917/Desktop/Python_Scripts/preprocessing_library/templates'

CUS  = str(Path(BASE) / 'demo_01_customers_clean.csv')
INV  = str(Path(BASE) / 'demo_01_invoices_clean.csv')
INV2 = str(Path(BASE) / 'demo_02_invoices_batch.csv')

os.makedirs(OUT, exist_ok=True)

TESTS = [
    # ── PS-01 ─────────────────────────────────────────────────────────────
    ('file_detect_load', {
        'OUTPUT_DIR': OUT,
        'OUTPUT_FILENAME_PREFIX': 'ps01',
        'OUTPUT_FORMAT': 'csv',
        'ENCODING_PRIMARY': 'utf-8',
        'ENCODING_FALLBACK_1': 'cp1252',
        'ENCODING_FALLBACK_2': 'latin-1',
    }, [INV]),

    # ── PS-02 ─────────────────────────────────────────────────────────────
    ('file_union', {
        'OUTPUT_DIR': OUT,
        'OUTPUT_FILENAME': 'ps02_out.csv',
        'OUTPUT_FORMAT': 'csv',
        'ADD_SOURCE_TAG': True,
        'SOURCE_TAG_COLUMN': '_source_file',
    }, [INV, INV2]),

    # ── PS-03 ─────────────────────────────────────────────────────────────
    ('file_join_two', {
        'JOIN_KEY': 'account_number',
        'JOIN_TYPE': 'inner',
        'LEFT_SUFFIX': '_cus',
        'RIGHT_SUFFIX': '_inv',
        'LEFT_FILENAME': 'demo_01_customers_clean.csv',
        'RIGHT_FILENAME': 'demo_01_invoices_clean.csv',
        'OUTPUT_DIR': OUT,
        'OUTPUT_FILENAME': 'ps03_out.csv',
        'OUTPUT_FORMAT': 'csv',
    }, [CUS, INV]),

    # ── PS-04 ─────────────────────────────────────────────────────────────
    ('file_join_multi', {
        'JOIN_STEPS': [
            {'file_index': 1, 'join_key': 'account_number', 'join_type': 'inner'},
            {'file_index': 2, 'join_key': 'account_number', 'join_type': 'left'},
        ],
        'OUTPUT_DIR': OUT,
        'OUTPUT_FILENAME': 'ps04_out.csv',
        'OUTPUT_FORMAT': 'csv',
    }, [CUS, INV, INV2]),

    # ── PS-05 ─────────────────────────────────────────────────────────────
    ('file_join_multi_key', {
        'JOIN_KEYS': ['account_number'],
        'JOIN_TYPE': 'inner',
        'LEFT_SUFFIX': '_l',
        'RIGHT_SUFFIX': '_r',
        'LEFT_FILENAME': 'demo_01_customers_clean.csv',
        'RIGHT_FILENAME': 'demo_01_invoices_clean.csv',
        'OUTPUT_DIR': OUT,
        'OUTPUT_FILENAME': 'ps05_out.csv',
        'OUTPUT_FORMAT': 'csv',
    }, [CUS, INV]),

    # ── PS-06 ─────────────────────────────────────────────────────────────
    ('file_denormalize', {
        'JOIN_KEY': 'account_number',
        'JOIN_TYPE': 'left',
        'DETAIL_PREFIX': 'inv_',
        'HEADER_FILENAME': 'demo_01_customers_clean.csv',
        'DETAIL_FILENAME': 'demo_01_invoices_clean.csv',
        'OUTPUT_DIR': OUT,
        'OUTPUT_FILENAME': 'ps06_out.csv',
        'OUTPUT_FORMAT': 'csv',
    }, [CUS, INV]),

    # ── PS-07 ─────────────────────────────────────────────────────────────
    ('file_split_by_value', {
        'SPLIT_COLUMN': 'invoice_type',
        'OUTPUT_DIR': OUT,
        'OUTPUT_FORMAT': 'csv',
        'FILENAME_TEMPLATE': 'ps07_{value}.csv',
        'INCLUDE_SPLIT_COLUMN': True,
    }, [INV]),

    # ── PS-08 ─────────────────────────────────────────────────────────────
    ('file_filter_to_files', {
        'FILTER_RULES': [
            {'condition': 'invoice_amount > 1000', 'output_filename': 'ps08_large.csv'},
            {'condition': 'invoice_amount <= 1000', 'output_filename': 'ps08_small.csv'},
        ],
        'OUTPUT_DIR': OUT,
        'OUTPUT_FORMAT': 'csv',
        'UNMATCHED_FILENAME': 'ps08_unmatched.csv',
    }, [INV]),

    # ── PS-09 ─────────────────────────────────────────────────────────────
    ('file_split_columns', {
        'COMMON_KEY_COLUMNS': ['account_number'],
        'COLUMN_GROUPS': [
            {'columns': ['invoice_number', 'invoice_date', 'invoice_amount'], 'output_filename': 'ps09_invoices.csv'},
            {'columns': ['paid_date', 'paid_amount', 'payment_terms'], 'output_filename': 'ps09_payments.csv'},
        ],
        'OUTPUT_DIR': OUT,
        'OUTPUT_FORMAT': 'csv',
    }, [INV]),

    # ── PS-10 ─────────────────────────────────────────────────────────────
    ('file_deduplicate', {
        'KEY_COLUMNS': ['account_number'],
        'KEEP': 'first',
        'OUTPUT_DIR': OUT,
        'OUTPUT_FILENAME': 'ps10_out.csv',
        'DUPLICATES_REPORT_FILENAME': 'ps10_dupes.csv',
        'OUTPUT_FORMAT': 'csv',
    }, [INV]),

    # ── PS-11 ─────────────────────────────────────────────────────────────
    ('file_rename_columns', {
        'COLUMN_MAPPING': {'invoice_number': 'inv_no', 'invoice_amount': 'amount'},
        'DROP_UNMAPPED': False,
        'OUTPUT_DIR': OUT,
        'OUTPUT_FILENAME': 'ps11_out.csv',
        'OUTPUT_FORMAT': 'csv',
    }, [INV]),

    # ── PS-12 ─────────────────────────────────────────────────────────────
    ('file_handle_nulls', {
        'NULL_RULES': [
            {'column': 'paid_date',   'strategy': 'fill', 'fill_value': 'N/A'},
            {'column': 'paid_amount', 'strategy': 'fill', 'fill_value': '0'},
        ],
        'NULL_VALUES': ['', 'NULL', 'N/A', 'null', 'none', 'None'],
        'OUTPUT_DIR': OUT,
        'OUTPUT_FILENAME': 'ps12_out.csv',
        'NULL_REPORT_FILENAME': 'ps12_null_report.csv',
        'OUTPUT_FORMAT': 'csv',
    }, [INV]),

    # ── PS-13 ─────────────────────────────────────────────────────────────
    ('file_cast_types', {
        'TYPE_RULES': [
            {'column': 'invoice_amount', 'target_type': 'float'},
            {'column': 'paid_amount',    'target_type': 'float'},
        ],
        'STRIP_CURRENCY': True,
        'TRIM_STRINGS': True,
        'ON_ERROR': 'null',
        'OUTPUT_DIR': OUT,
        'OUTPUT_FILENAME': 'ps13_out.csv',
        'CAST_ERROR_REPORT_FILENAME': 'ps13_cast_errors.csv',
        'OUTPUT_FORMAT': 'csv',
    }, [INV]),

    # ── PS-14 ─────────────────────────────────────────────────────────────
    ('file_aggregate', {
        'GROUP_BY_COLUMNS': ['account_number'],
        'AGGREGATIONS': [
            {'column': 'invoice_amount', 'function': 'sum', 'output_column': 'total_amount'},
            {'column': 'invoice_number', 'function': 'count', 'output_column': 'inv_count'},
        ],
        'OUTPUT_DIR': OUT,
        'OUTPUT_FILENAME': 'ps14_out.csv',
        'OUTPUT_FORMAT': 'csv',
    }, [INV]),

    # ── PS-15 ─────────────────────────────────────────────────────────────
    ('file_delta_load', {
        'KEY_COLUMNS': ['invoice_number'],
        'DELTA_MODE': 'full_delta',
        'COMPARE_COLUMNS': ['invoice_amount', 'paid_amount'],
        'DELTA_STATUS_COLUMN': 'delta_status',
        'NEW_FILENAME': 'demo_01_invoices_clean.csv',
        'OLD_FILENAME': 'demo_02_invoices_batch.csv',
        'OUTPUT_DIR': OUT,
        'OUTPUT_FILENAME': 'ps15_out.csv',
        'OUTPUT_FORMAT': 'csv',
    }, [INV, INV2]),

    # ── PS-16 ─────────────────────────────────────────────────────────────
    ('file_rank_filter', {
        'PARTITION_BY': [],
        'RANK_BY_COLUMN': 'invoice_amount',
        'RANK_ORDER': 'desc',
        'RANK_METHOD': 'rank',
        'RANK_COLUMN_NAME': '_rank',
        'KEEP_TOP_N': 5,
        'DISCARD_FILENAME': 'ps16_discarded.csv',
        'OUTPUT_DIR': OUT,
        'OUTPUT_FILENAME': 'ps16_out.csv',
        'OUTPUT_FORMAT': 'csv',
    }, [INV]),

    # ── PS-17 ─────────────────────────────────────────────────────────────
    ('file_filter_by_values', {
        'FILTER_COLUMN': 'invoice_type',
        'VALUE_GROUPS': [
            {'values': ['Standard'], 'output_filename': 'ps17_standard.csv'},
            {'values': ['Credit'],   'output_filename': 'ps17_credit.csv'},
        ],
        'CASE_SENSITIVE': False,
        'OTHERS_FILENAME': 'ps17_others.csv',
        'OUTPUT_DIR': OUT,
        'OUTPUT_FORMAT': 'csv',
    }, [INV]),

    # ── PS-18 ─────────────────────────────────────────────────────────────
    ('file_join_filter_agg', {
        'JOIN_KEYS': ['account_number'],
        'JOIN_TYPE': 'inner',
        'LEFT_FILENAME': 'demo_01_customers_clean.csv',
        'RIGHT_FILENAME': 'demo_01_invoices_clean.csv',
        'WHERE_CONDITION': '',
        'GROUP_BY_COLUMNS': ['account_number'],
        'AGGREGATIONS': [
            {'column': 'invoice_amount', 'function': 'sum', 'output_column': 'total_amount'},
            {'column': 'invoice_number', 'function': 'count', 'output_column': 'inv_count'},
        ],
        'RANK_BY_COLUMN': 'total_amount',
        'RANK_ORDER': 'desc',
        'RANK_COLUMN_NAME': '_rank',
        'KEEP_TOP_N': 0,
        'OUTPUT_DIR': OUT,
        'OUTPUT_FILENAME': 'ps18_out.csv',
        'OUTPUT_FORMAT': 'csv',
    }, [CUS, INV]),
]


def run_tests():
    results = []
    for tname, params, inputs in TESTS:
        # Step 1: generate
        with tempfile.TemporaryDirectory() as tmp:
            try:
                gpath = generate_preprocessor(tname, params, f'{tname}_test.py', tmp, TMPL)
                src = Path(gpath).read_text(encoding='utf-8')
            except Exception as exc:
                results.append((tname, 'GEN_FAIL', str(exc)))
                continue

        # Step 2: exec
        ns = {'__name__': '<test>'}
        try:
            exec(compile(src, f'{tname}_test.py', 'exec'), ns)
        except Exception as exc:
            results.append((tname, 'EXEC_FAIL', str(exc)))
            continue

        fn = ns.get('preprocess')
        if fn is None:
            results.append((tname, 'NO_PREPROCESS', 'function not found'))
            continue

        # Step 3: run — detect single-path vs list signature
        sig = inspect.signature(fn)
        first_param = list(sig.parameters.values())[0]
        ann = first_param.annotation
        use_list = not (ann is str or str(ann) == 'str' or first_param.name == 'input_path')

        try:
            if use_list:
                out = fn(inputs)
            else:
                out = fn(inputs[0])

            # collect output info
            import pandas as pd
            out_paths = [out] if isinstance(out, str) else (list(out) if out else [])
            summaries = []
            for p in out_paths:
                if p and Path(p).exists():
                    try:
                        df = pd.read_csv(p)
                        summaries.append(f'{Path(p).name}({len(df)}r x {len(df.columns)}c)')
                    except Exception:
                        summaries.append(Path(p).name)
            results.append((tname, 'PASS', ' | '.join(summaries) if summaries else str(out)))
        except Exception as exc:
            results.append((tname, 'RUN_FAIL', str(exc)))

    return results


if __name__ == '__main__':
    results = run_tests()

    print('\n' + '='*72)
    print(f"{'Template':<35} {'Status':<12} {'Output / Error'}")
    print('='*72)
    pass_count = 0
    for tname, status, msg in results:
        icon = 'PASS' if status == 'PASS' else 'FAIL'
        if status == 'PASS':
            pass_count += 1
        print(f"[{icon}] {tname:<33} {status:<12} {msg[:80]}")
    print('='*72)
    print(f"Result: {pass_count}/{len(results)} passed")
