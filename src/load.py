"""
Script:   load.py
Purpose:  Read the 17 raw CSVs from Data/ (and the cleaned ones from Data_clean/).
"""
from pathlib import Path

import pandas as pd

from config import RAW_DIR, CLEAN_DIR

DATE_COLS = {
    "calendar": ["date"],
    "hotels": ["opening_date"],
    "local_events": ["start_date", "end_date"],
    "guests": ["created_at", "loyalty_join_date"],
    "bookings": ["booking_datetime", "checkin_date", "checkout_date", "status_datetime"],
    "rate_quotes": ["quote_datetime", "checkin_date"],
    "reviews": ["review_datetime"],
    "stay_charges": ["charge_datetime"],
    "competitor_rates": ["stay_date"],
    "marketing_spend": ["date"],
    "experiments": ["start_date", "end_date"],
    "channels": ["available_from"],
    "rate_plans": ["available_from"],
}
STR_COLS = {
    "rate_quotes": {"experiment_id": "string", "variant": "string", "guest_id": "string", "booking_id": "string"},
    "calendar": {"holiday_name": "string"},
    "guests": {"loyalty_tier": "string"},
}


def _read_folder(folder, extra_dates=None):
    tables = {}
    for path in sorted(Path(folder).glob("*.csv")):
        name = path.stem
        dates = DATE_COLS.get(name, []) + (extra_dates or {}).get(name, [])
        df = pd.read_csv(path, dtype=STR_COLS.get(name), low_memory=False)
        for c in dates:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c], errors="coerce")
        tables[name] = df
    if not tables:
        raise FileNotFoundError(f"No CSV files found in {folder}")
    return tables


def load_raw():
    """All raw tables as a dict of DataFrames."""
    return _read_folder(RAW_DIR)


def load_clean():
    """All cleaned tables (run clean.py first)."""
    return _read_folder(CLEAN_DIR)


if __name__ == "__main__":
    for name, df in load_raw().items():
        print(f"{name:18s} {len(df):>9,} rows x {df.shape[1]:>2} cols")
