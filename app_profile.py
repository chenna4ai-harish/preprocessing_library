"""
app_profile.py
--------------
Data profiling utilities for PrepKit.

Called from gradio_app.py when a file is selected in Tab 1.
profile_file() returns a summary DataFrame with per-column statistics.
"""
from __future__ import annotations

import pandas as pd


def profile_file(
    df: pd.DataFrame | None = None,
    file_path: str | None = None,
    max_rows: int = 500,
) -> pd.DataFrame:
    """
    Compute per-column profile statistics.

    Parameters
    ----------
    df : pd.DataFrame | None
        Pre-loaded DataFrame. Preferred — avoids a second disk read.
    file_path : str | None
        Fallback path if df is None.
    max_rows : int
        Maximum rows to load when reading from disk.

    Returns
    -------
    pd.DataFrame with columns:
        Column, Type, Non-Null, Null %, Unique, Min, Max, Top Value
    """
    if df is None:
        if not file_path:
            return pd.DataFrame({"Message": ["No file selected."]})
        try:
            # Lazy import to avoid circular dependency
            from gradio_app import _sniff_load
            df = _sniff_load(file_path, max_rows=max_rows)
        except Exception as exc:
            return pd.DataFrame({"Message": [f"Could not load file: {exc}"]})

    if df is None or df.empty:
        return pd.DataFrame({"Message": ["File is empty or could not be read."]})

    total = len(df)
    rows = []

    for col in df.columns:
        series = df[col]
        null_count = int(series.isna().sum())
        non_null = total - null_count
        null_pct = f"{null_count / total * 100:.1f}%" if total > 0 else "—"
        unique = int(series.nunique(dropna=True))
        dtype = str(series.dtype)

        # Min / Max
        try:
            if pd.api.types.is_numeric_dtype(series):
                mn = series.min()
                mx = series.max()
                col_min = f"{mn:,.2f}" if isinstance(mn, float) else str(mn)
                col_max = f"{mx:,.2f}" if isinstance(mx, float) else str(mx)
            else:
                sorted_vals = series.dropna().astype(str).sort_values()
                col_min = str(sorted_vals.iloc[0]) if len(sorted_vals) > 0 else "—"
                col_max = str(sorted_vals.iloc[-1]) if len(sorted_vals) > 0 else "—"
                col_min = col_min[:30] + "…" if len(col_min) > 30 else col_min
                col_max = col_max[:30] + "…" if len(col_max) > 30 else col_max
        except Exception:
            col_min = col_max = "—"

        # Top value (most frequent non-null)
        try:
            vc = series.dropna().value_counts()
            top_raw = str(vc.index[0]) if len(vc) > 0 else "—"
            top_val = top_raw[:30] + "…" if len(top_raw) > 30 else top_raw
        except Exception:
            top_val = "—"

        rows.append({
            "Column":    col,
            "Type":      dtype,
            "Non-Null":  non_null,
            "Null %":    null_pct,
            "Unique":    unique,
            "Min":       col_min,
            "Max":       col_max,
            "Top Value": top_val,
        })

    return pd.DataFrame(rows)
