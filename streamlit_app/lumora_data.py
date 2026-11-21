"""
Script:   lumora_data.py
Purpose:  Load the cleaned Lumora tables once (cached by Streamlit) and build the
          small tables the dashboard pages need, plus the sidebar filter logic.
            load_core()       bookings with hotel / channel / extras columns,
                              capacity per hotel-month, hotels, channels
            load_reviews()    reviews joined to the booking (channel, segment)
            load_quotes()     website / app price quotes (pricing page)
            load_tables()     model outputs from output/tables (notebook 03)
            apply_filters()   year / hotel / channel group / segment slicers
          Revenue, bookings and cancellations are counted by ARRIVAL date, same as
          the HTML dashboard in src/dashboard.py.
Input:    ../Data_clean/*.csv  (from notebook 01 / src/clean.py)
          ../output/tables/*.csv  (from notebook 03 / src/models.py)
          Another folder can be used with the LUMORA_BASE environment variable.
Output:   pandas DataFrames (in memory only)
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

# Paths ----
# the app sits in Lumora_Hotels/streamlit_app, so the data is one folder up
_here = Path(__file__).resolve().parent
BASE = Path(os.environ.get("LUMORA_BASE", _here.parent))
CLEAN_DIR = BASE / "Data_clean"
TAB_DIR = BASE / "output" / "tables"

YEARS = [2021, 2022, 2023, 2024, 2025]
SEGMENTS = ["Leisure", "Business", "Family", "Group"]
CHANNEL_GROUPS = ["Direct", "OTA", "Corporate", "Wholesale"]
LEAD_BUCKETS = ["0-6 days", "7-29", "30-59", "60-119", "120+"]
# readable names for the cancellation model features (same list as src/dashboard.py)
FEATURE_NAMES = {
    "log_lead": "Lead time (log)", "lead_time_days": "Lead time (days)", "rate_plan_id": "Rate plan",
    "channel_id": "Booking channel", "prev_cancel_rate": "Guest's past cancel rate", "prev_cancels": "Guest's past cancels",
    "special_requests": "Special requests", "log_price_index": "Price vs competitors", "deposit_type": "Deposit type",
    "market_segment": "Market segment", "year": "Year", "is_member": "Loyalty member", "prev_bookings": "Guest's past bookings",
    "adr_eur": "Room rate (ADR)", "hotel_id": "Hotel", "room_type_id": "Room type", "nights": "Nights",
    "checkin_month": "Arrival month", "checkin_dow": "Arrival weekday", "booking_hour": "Booking hour",
    "party_size": "Party size", "adults": "Adults", "children": "Children", "weekend_stay": "Weekend stay",
    "is_holiday": "Holiday arrival", "event_on_arrival": "City event on arrival", "stars": "Hotel stars",
}


def check_paths():
    """Stop the app with a clear message if the data folders are missing."""
    missing = [p for p in [CLEAN_DIR / "bookings.csv", TAB_DIR / "ab_test_results.csv"] if not p.exists()]
    if missing:
        st.error("Data not found. Put this folder inside Lumora_Hotels (next to Data_clean and output), "
                 "or set LUMORA_BASE to the Lumora_Hotels folder.\n\nMissing: " + ", ".join(map(str, missing)))
        st.stop()


def _csv(name, folder=CLEAN_DIR, **kw):
    return pd.read_csv(folder / f"{name}.csv", low_memory=False, **kw)


# Core tables ----
@st.cache_data(show_spinner="Loading bookings ...")
def load_core():
    hotels = _csv("hotels", parse_dates=["opening_date"]).merge(
        _csv("cities")[["city_id", "city", "country", "city_type"]], on="city_id")
    hotels["short_name"] = hotels.hotel_name.str.replace("Lumora ", "", regex=False)
    channels = _csv("channels")
    plans = _csv("rate_plans")

    cols = ["booking_id", "guest_id", "hotel_id", "room_type_id", "channel_id", "rate_plan_id", "booking_datetime",
            "checkin_date", "nights", "lead_time_days", "adults", "children", "market_segment", "adr_eur",
            "special_requests", "deposit_type", "status", "year", "is_cancelled", "room_nights", "room_revenue_eur"]
    b = _csv("bookings", usecols=cols, parse_dates=["booking_datetime", "checkin_date"])
    b["month"] = b.checkin_date.dt.to_period("M").dt.to_timestamp()
    b = b.merge(channels[["channel_id", "channel_name", "channel_group", "commission_pct"]], on="channel_id", how="left")
    b = b.merge(hotels[["hotel_id", "short_name", "city"]], on="hotel_id", how="left")
    b["rate_plan"] = b.rate_plan_id.map(plans.set_index("rate_plan_id").rate_plan_name)
    b["stayed"] = (b.status == "Checked-out").astype(int)
    b["no_show"] = (b.status == "No-show").astype(int)
    b["lead_bucket"] = pd.cut(b.lead_time_days, [-1, 6, 29, 59, 119, 10_000], labels=LEAD_BUCKETS)
    # OTA / agency commission is only paid on completed stays
    b["commission"] = np.where(b.stayed == 1, b.room_revenue_eur * b.commission_pct, 0.0)

    # extras (stay_charges) per booking, adjustments included so the totals match
    sc = _csv("stay_charges", usecols=["booking_id", "category", "amount_eur"])
    b["extras"] = b.booking_id.map(sc.groupby("booking_id").amount_eur.sum()).fillna(0.0)
    extras = sc[sc.category != "Adjustment"].merge(
        b[["booking_id", "hotel_id", "year", "channel_group", "market_segment"]], on="booking_id")

    # capacity: available room-nights per hotel and month (only after the hotel opened)
    days = pd.DataFrame({"date": pd.date_range("2021-01-01", "2025-12-31")})
    cap = hotels[["hotel_id", "rooms", "opening_date"]].merge(days, how="cross")
    cap = cap[cap.date >= cap.opening_date]
    cap["month"] = cap.date.dt.to_period("M").dt.to_timestamp()
    cap = cap.groupby(["hotel_id", "month"]).rooms.sum().rename("room_nights_available").reset_index()
    cap["year"] = cap.month.dt.year
    return {"bookings": b, "hotels": hotels, "channels": channels, "plans": plans, "capacity": cap,
            "extras": extras}


@st.cache_data(show_spinner="Loading reviews ...")
def load_reviews():
    cols = ["review_id", "booking_id", "hotel_id", "review_datetime", "overall_score", "cleanliness", "staff",
            "location", "comfort", "value_for_money", "would_recommend", "year"]
    r = _csv("reviews", usecols=cols, parse_dates=["review_datetime"])
    b = load_core()["bookings"][["booking_id", "channel_group", "market_segment", "month"]]
    r = r.merge(b, on="booking_id", how="left")
    staff = _csv("staffing_monthly")
    staff["month"] = pd.to_datetime(staff.month + "-01")
    staff["year"] = staff.month.dt.year
    guests = _csv("guests", usecols=["guest_id", "home_country", "loyalty_member", "loyalty_tier", "birth_year"])
    return {"reviews": r, "staffing": staff, "guests": guests}


@st.cache_data(show_spinner="Loading price quotes ...")
def load_quotes():
    cols = ["quote_id", "quote_datetime", "device", "traffic_source", "hotel_id", "nights",
            "price_per_night_eur", "converted"]
    q = _csv("rate_quotes", usecols=cols, parse_dates=["quote_datetime"])
    q = q[q.quote_datetime >= "2021-01-01"].copy()
    q["year"] = q.quote_datetime.dt.year
    q["month"] = q.quote_datetime.dt.to_period("M").dt.to_timestamp()
    q["revenue"] = q.converted * q.price_per_night_eur * q.nights
    comp = _csv("competitor_rates", parse_dates=["stay_date"])
    comp["month"] = comp.stay_date.dt.to_period("M").dt.to_timestamp()
    mk = _csv("marketing_spend", parse_dates=["date"])
    mk["year"] = mk.date.dt.year
    return {"quotes": q, "competitor": comp, "marketing": mk, "experiments": _csv("experiments")}


@st.cache_data(show_spinner="Loading model results ...")
def load_tables():
    names = ["ab_test_results", "cancel_calibration", "cancel_feature_importance", "cancel_roc",
             "conversion_by_price_index", "forecast_accuracy_by_hotel", "guest_segment_profiles",
             "price_elasticity_by_group", "price_test_by_variant", "review_drivers", "review_phrases"]
    t = {n: _csv(n, folder=TAB_DIR) for n in names}
    t["cancel_predictions"] = _csv("cancel_predictions_2025", folder=TAB_DIR, parse_dates=["checkin_date"])
    t["daily_forecast"] = _csv("hotel_daily_forecast", folder=TAB_DIR, parse_dates=["date"])
    return t


# Filters ----
def get_filters():
    """Current sidebar selections (set in app.py), with safe defaults."""
    s = st.session_state
    return {"year": s.get("f_year", 2025), "hotels": s.get("f_hotels", []),
            "groups": s.get("f_groups", []), "segments": s.get("f_segments", [])}


def years_of(f):
    return YEARS if f["year"] == "All years" else [f["year"]]


def prev_years(f):
    """The comparison period for the KPI deltas (None when all years are shown)."""
    if f["year"] == "All years" or f["year"] == YEARS[0]:
        return None
    return [f["year"] - 1]


def apply_filters(df, f, years=None, year_col="year", hotel_col="hotel_id",
                  group_col="channel_group", seg_col="market_segment"):
    """Filter a table by the sidebar slicers. Columns the table does not have are skipped."""
    m = pd.Series(True, index=df.index)
    years = years_of(f) if years is None else years
    if year_col in df.columns and years is not None:
        m &= df[year_col].isin(years)
    if f["hotels"] and hotel_col in df.columns:
        m &= df[hotel_col].isin(f["hotels"])
    if f["groups"] and group_col in df.columns:
        m &= df[group_col].isin(f["groups"])
    if f["segments"] and seg_col in df.columns:
        m &= df[seg_col].isin(f["segments"])
    return df[m]


# KPI maths ----
def kpis(b, cap):
    """Headline numbers for a filtered booking table and its capacity."""
    if len(b) == 0:
        return dict(bookings=0, revenue=0.0, room_nights=0, occupancy=np.nan, adr=np.nan, revpar=np.nan,
                    cancel_rate=np.nan, no_show_rate=np.nan, extras=0.0, lead=np.nan, extras_per_stay=np.nan)
    avail = cap.room_nights_available.sum()
    rn = b.room_nights.sum()
    rev = b.room_revenue_eur.sum()
    stays = b.stayed.sum()
    return dict(
        bookings=len(b), revenue=rev, room_nights=rn,
        occupancy=rn / avail if avail else np.nan,
        adr=(b.adr_eur * b.room_nights).sum() / rn if rn else np.nan,
        revpar=rev / avail if avail else np.nan,
        cancel_rate=b.is_cancelled.mean(), no_show_rate=b.no_show.mean(),
        extras=b.extras.sum(), lead=b.lead_time_days.mean(),
        extras_per_stay=b.extras.sum() / stays if stays else np.nan,
    )


def filtered_core(f, years=None):
    """Bookings and capacity for the current filters (capacity ignores channel / segment)."""
    core = load_core()
    b = apply_filters(core["bookings"], f, years=years)
    cap = apply_filters(core["capacity"], f, years=years)
    return b, cap


def auc_score(y, p):
    """ROC AUC from ranks (Mann-Whitney), so scikit-learn is not needed."""
    y = np.asarray(y)
    n1, n0 = y.sum(), len(y) - y.sum()
    if n1 == 0 or n0 == 0:
        return np.nan
    r = pd.Series(p).rank().values
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
