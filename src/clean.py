"""
Script:   clean.py
Purpose:  Fix the data-quality problems found in the raw files and save
          clean copies to Data_clean/. Every fix is written to cleaning_log.csv.
Run:      python src/clean.py
"""
import numpy as np
import pandas as pd

from config import CLEAN_DIR, TAB_DIR, make_dirs
from load import load_raw

COUNTRY_NAMES = {
    "germany": "DE", "united kingdom": "GB", "usa": "US", "france": "FR", "netherlands": "NL",
    "italy": "IT", "spain": "ES", "poland": "PL", "lithuania": "LT", "latvia": "LV", "estonia": "EE",
}


def remap(s, mapping):
    """Replace ids found in mapping, keep the rest (much faster than Series.replace)."""
    return s.map(mapping).fillna(s)


class Log:
    """Collects one row per cleaning step."""

    def __init__(self):
        self.rows = []

    def add(self, table, step, rows):
        self.rows.append({"table": table, "step": step, "rows_affected": int(rows)})
        print(f"  {table:17s} {step:70s} {int(rows):>8,}")

    def frame(self):
        return pd.DataFrame(self.rows)


def clean_guests(g, log):
    g = g.copy()
    # country: mixed ISO codes, names and lower case
    raw = g.home_country.astype(str).str.strip()
    fixed = raw.str.lower().map(COUNTRY_NAMES).fillna(raw.str.upper())
    log.add("guests", "home_country standardised to ISO-2 upper case", (fixed != g.home_country).sum())
    g["home_country"] = fixed
    # impossible birth years
    bad = g.birth_year.notna() & ~g.birth_year.between(1930, 2007)
    log.add("guests", "impossible birth_year set to missing", bad.sum())
    g.loc[bad, "birth_year"] = np.nan
    log.add("guests", "birth_year missing (left missing)", g.birth_year.isna().sum())
    # duplicate profiles that share an email_hash -> keep the oldest profile
    g = g.sort_values("created_at")
    canon = g.groupby("email_hash").guest_id.transform("first")
    dup_map = dict(zip(g.guest_id[canon != g.guest_id], canon[canon != g.guest_id]))
    log.add("guests", "duplicate profiles merged (same email_hash)", len(dup_map))
    # keep loyalty info from either profile
    agg = g.assign(canon=canon).groupby("canon").agg(
        loyalty_member=("loyalty_member", "max"), loyalty_join_date=("loyalty_join_date", "min"),
        marketing_opt_in=("marketing_opt_in", "max"))
    g = g[canon == g.guest_id].drop(columns=["loyalty_member", "loyalty_join_date", "marketing_opt_in"])
    g = g.merge(agg, left_on="guest_id", right_index=True, how="left")
    return g.sort_values("guest_id").reset_index(drop=True), dup_map


def clean_bookings(b, room_types, dup_map, log):
    b = b.copy()
    n = len(b)
    b = b.drop_duplicates()
    log.add("bookings", "exact duplicate rows removed", n - len(b))
    if b.booking_id.duplicated().any():
        b = b.drop_duplicates("booking_id")
    # guest ids of merged profiles
    moved = b.guest_id.isin(dup_map)
    b["guest_id"] = remap(b.guest_id, dup_map)
    log.add("bookings", "guest_id remapped to merged profile", moved.sum())
    # segment labels
    seg = b.market_segment.str.strip().str.title()
    log.add("bookings", "market_segment trimmed / title case", (seg != b.market_segment).sum())
    b["market_segment"] = seg
    # swapped dates (nights column is right)
    sw = b.checkout_date < b.checkin_date
    b.loc[sw, ["checkin_date", "checkout_date"]] = b.loc[sw, ["checkout_date", "checkin_date"]].values
    log.add("bookings", "checkin/checkout swapped back", sw.sum())
    b["lead_time_days"] = (b.checkin_date - b.booking_datetime.dt.normalize()).dt.days
    # adults = 0
    a0 = b.adults == 0
    b.loc[a0, "adults"] = 1
    log.add("bookings", "adults = 0 set to 1", a0.sum())
    # ADR in cents
    cents = b.adr_eur > 3000
    b.loc[cents, "adr_eur"] = b.loc[cents, "adr_eur"] / 100
    log.add("bookings", "adr_eur entered in cents divided by 100", cents.sum())
    # ADR = 0 -> median of same room type, rate plan and month
    zero = b.adr_eur <= 0
    b.loc[zero, "adr_eur"] = np.nan
    key = [b.room_type_id, b.rate_plan_id, b.checkin_date.dt.to_period("M")]
    med = b.groupby(key).adr_eur.transform("median")
    med2 = b.groupby([b.room_type_id, b.checkin_date.dt.year]).adr_eur.transform("median")
    b["adr_imputed"] = zero.astype(int)
    b["adr_eur"] = b.adr_eur.fillna(med).fillna(med2).round(2)
    log.add("bookings", "adr_eur = 0 imputed (room type x plan x month median)", zero.sum())
    # helper columns
    b["year"] = b.checkin_date.dt.year
    b["is_cancelled"] = (b.status == "Cancelled").astype(int)
    b["room_nights"] = np.where(b.status == "Cancelled", 0, b.nights)
    # realised room revenue: stays pay all nights, no-shows pay 1 night, cancelled non-refundable pay all
    b["room_revenue_eur"] = np.select(
        [b.status == "Checked-out", b.status == "No-show",
         (b.status == "Cancelled") & (b.deposit_type == "Non Refundable")],
        [b.adr_eur * b.nights, b.adr_eur, b.adr_eur * b.nights], 0.0).round(2)
    return b.sort_values("booking_datetime").reset_index(drop=True)


def clean_fx_convert(df, amount_cols, fx, date_col, log, table):
    df = df.copy()
    m = df[date_col].dt.to_period("M").astype(str)
    rate = pd.Series(list(zip(m, df.currency))).map(
        fx.set_index(["month", "currency"]).units_per_eur.to_dict()).values
    rate = np.where(df.currency.values == "EUR", 1.0, rate.astype(float))
    for c in amount_cols:
        df[c + "_eur"] = (df[c] / rate).round(2)
    log.add(table, "local currency converted to EUR with fx_rates", (df.currency != "EUR").sum())
    return df


def clean_competitor_rates(cr, fx, log):
    cr = clean_fx_convert(cr, ["comp_avg_rate", "comp_min_rate"], fx, "stay_date", log, "competitor_rates")
    cr = cr.sort_values(["hotel_id", "stay_date"])
    # 10x spikes: far above the 15-day rolling median
    med = cr.groupby("hotel_id").comp_avg_rate_eur.transform(lambda s: s.rolling(15, center=True, min_periods=3).median())
    spike = cr.comp_avg_rate_eur > 3 * med
    cr.loc[spike, ["comp_avg_rate_eur", "comp_min_rate_eur"]] = np.nan
    log.add("competitor_rates", "10x spikes set to missing", spike.sum())
    miss = cr.comp_avg_rate_eur.isna().sum()
    for c in ["comp_avg_rate_eur", "comp_min_rate_eur"]:
        cr[c] = cr.groupby("hotel_id")[c].transform(lambda s: s.interpolate(limit_direction="both")).round(2)
    log.add("competitor_rates", "missing rates interpolated per hotel", miss)
    return cr[["hotel_id", "stay_date", "comp_avg_rate_eur", "comp_min_rate_eur", "comp_hotels_sampled"]].reset_index(drop=True)


def clean_reviews(r, b, dup_map, log):
    r = r.copy()
    r["guest_id"] = remap(r.guest_id, dup_map)
    five = (r.source == "TripGlobe") & (r.review_datetime.dt.year <= 2022) & (r.overall_score <= 5)
    r.loc[five, "overall_score"] = r.loc[five, "overall_score"] * 2
    log.add("reviews", "TripGlobe 2021-2022 scores rescaled from 1-5 to 1-10", five.sum())
    co = r.booking_id.map(b.set_index("booking_id").checkout_date)
    early = r.review_datetime < r.booking_id.map(b.set_index("booking_id").checkin_date)
    delay = (r.review_datetime - co)[~early].median()
    r.loc[early, "review_datetime"] = co[early] + delay
    log.add("reviews", "review_datetime before stay replaced by checkout + median delay", early.sum())
    r["year"] = r.review_datetime.dt.year
    return r


def clean_quotes(q, dup_map, log):
    q = q.copy()
    q["guest_id"] = remap(q.guest_id, dup_map)
    grp = q.groupby("session_id").quote_datetime
    size = grp.transform("size")
    span = (grp.transform("max") - grp.transform("min")).dt.total_seconds()
    bot = (size >= 50) & (span / size < 30)
    log.add("rate_quotes", "bot sessions removed (50+ quotes, < 30 s apart)", bot.sum())
    q = q[~bot].copy()
    q["experiment_id"] = q.experiment_id.fillna("")
    q["variant"] = q.variant.fillna("")
    return q.reset_index(drop=True)


def clean_staffing(s, hotels, log):
    months = pd.period_range("2021-01", "2025-12", freq="M").astype(str)
    full = []
    for _, h in hotels.iterrows():
        open_m = max(pd.Period(h.opening_date, "M"), pd.Period("2021-01", "M"))
        ms = [m for m in months if pd.Period(m, "M") >= open_m]
        full.append(pd.DataFrame({"hotel_id": h.hotel_id, "month": ms}))
    full = pd.concat(full)
    out = full.merge(s, on=["hotel_id", "month"], how="left")
    miss = out.staff_fte.isna().sum()
    num = [c for c in s.columns if c not in ("hotel_id", "month")]
    out[num] = out.groupby("hotel_id")[num].transform(lambda x: x.interpolate(limit_direction="both"))
    log.add("staffing_monthly", "missing hotel-months added and interpolated", miss)
    return out


def clean_all(save=True):
    make_dirs()
    raw = load_raw()
    log = Log()
    print("Cleaning ...")
    guests, dup_map = clean_guests(raw["guests"], log)
    bookings = clean_bookings(raw["bookings"], raw["room_types"], dup_map, log)
    fx = raw["fx_rates"]
    charges = clean_fx_convert(raw["stay_charges"], ["amount"], fx, "charge_datetime", log, "stay_charges")
    log.add("stay_charges", "negative Adjustment rows kept (flag is_adjustment)", (charges.category == "Adjustment").sum())
    charges["is_adjustment"] = (charges.category == "Adjustment").astype(int)
    comp = clean_competitor_rates(raw["competitor_rates"], fx, log)
    reviews = clean_reviews(raw["reviews"], bookings, dup_map, log)
    quotes = clean_quotes(raw["rate_quotes"], dup_map, log)
    staffing = clean_staffing(raw["staffing_monthly"], raw["hotels"], log)
    events = raw["local_events"].drop_duplicates("event_id")
    log.add("local_events", "duplicate events removed", len(raw["local_events"]) - len(events))

    clean = dict(raw)
    clean.update({"guests": guests, "bookings": bookings, "stay_charges": charges, "competitor_rates": comp,
                  "reviews": reviews, "rate_quotes": quotes, "staffing_monthly": staffing, "local_events": events})
    if save:
        CLEAN_DIR.mkdir(parents=True, exist_ok=True)
        for name, df in clean.items():
            df.to_csv(CLEAN_DIR / f"{name}.csv", index=False)
        log.frame().to_csv(TAB_DIR / "cleaning_log.csv", index=False)
        print(f"Saved {len(clean)} clean tables to {CLEAN_DIR}")
    return clean, log.frame()


if __name__ == "__main__":
    clean_all()
