"""
Script:   features.py
Purpose:  Feature tables for the models:
            booking_features()  one row per booking  (cancellation model)
            hotel_daily()       one row per hotel per night  (demand forecast)
            quote_features()    one row per booking-engine quote  (pricing)
          Only information known at booking / quote time is used.
"""
import numpy as np
import pandas as pd


def _price_refs(clean):
    rt = clean["room_types"].set_index("room_type_id").price_multiplier
    rp = clean["rate_plans"].set_index("rate_plan_id").price_factor
    comp = clean["competitor_rates"].set_index(["hotel_id", "stay_date"]).comp_avg_rate_eur
    return rt, rp, comp


def _comp_lookup(comp, hotel, date):
    idx = pd.MultiIndex.from_arrays([hotel.values, date.values])
    return comp.reindex(idx).values


def city_event_days(clean):
    """hotel x date table with event count and attendance in the hotel's city."""
    ev = clean["local_events"]
    ev = ev[ev.status == "Held"]
    rows = []
    for _, e in ev.iterrows():
        for d in pd.date_range(e.start_date - pd.Timedelta(days=1), e.end_date):
            rows.append((e.city_id, d, e.expected_attendance))
    ed = pd.DataFrame(rows, columns=["city_id", "date", "attendance"])
    ed = ed.groupby(["city_id", "date"]).agg(events=("attendance", "size"), event_attendance=("attendance", "sum")).reset_index()
    h = clean["hotels"][["hotel_id", "city_id"]]
    return h.merge(ed, on="city_id").drop(columns="city_id")


def booking_features(clean):
    b = clean["bookings"].copy()
    rt, rp, comp = _price_refs(clean)
    hotels = clean["hotels"].set_index("hotel_id")
    cal = clean["calendar"].set_index("date")
    b["comp_rate_eur"] = _comp_lookup(comp, b.hotel_id, b.checkin_date)
    b["price_index"] = b.adr_eur / (b.comp_rate_eur * b.room_type_id.map(rt) * b.rate_plan_id.map(rp))
    b["log_price_index"] = np.log(b.price_index.clip(0.2, 5))
    b["log_lead"] = np.log1p(b.lead_time_days.clip(lower=0))
    b["checkin_month"] = b.checkin_date.dt.month
    b["checkin_dow"] = b.checkin_date.dt.dayofweek
    b["booking_hour"] = b.booking_datetime.dt.hour
    b["weekend_stay"] = (b.checkin_dow >= 4).astype(int)
    b["party_size"] = b.adults + b.children
    b["is_holiday"] = b.checkin_date.map(cal.is_public_holiday).fillna(0).astype(int)
    b["stars"] = b.hotel_id.map(hotels.stars)
    ev = city_event_days(clean).set_index(["hotel_id", "date"]).events
    b["event_on_arrival"] = (pd.Series(_comp_lookup(ev, b.hotel_id, b.checkin_date)).fillna(0).values > 0).astype(int)
    # guest history known at booking time
    b = b.sort_values("booking_datetime")
    b["prev_bookings"] = b.groupby("guest_id").cumcount()
    b["prev_cancels"] = b.groupby("guest_id").is_cancelled.cumsum() - b.is_cancelled
    b["prev_cancel_rate"] = (b.prev_cancels / b.prev_bookings).fillna(0)
    g = clean["guests"].set_index("guest_id")
    join = b.guest_id.map(g.loyalty_join_date)
    b["is_member"] = (join.notna() & (join <= b.booking_datetime)).astype(int)
    b["is_direct"] = b.channel_id.isin(["CH1", "CH2", "CH3"]).astype(int)
    return b.sort_index()


CANCEL_NUM = ["log_lead", "lead_time_days", "nights", "adults", "children", "party_size", "special_requests",
              "adr_eur", "log_price_index", "checkin_month", "checkin_dow", "booking_hour", "weekend_stay",
              "is_holiday", "event_on_arrival", "stars", "prev_bookings", "prev_cancels", "prev_cancel_rate",
              "is_member", "year"]
CANCEL_CAT = ["hotel_id", "channel_id", "rate_plan_id", "market_segment", "deposit_type", "room_type_id"]


def hotel_daily(clean):
    """Rooms sold per hotel per night with calendar, event and price features."""
    b = clean["bookings"]
    b = b[b.status != "Cancelled"]
    rep = b.loc[b.index.repeat(b.nights), ["hotel_id", "checkin_date", "nights"]]
    rep["date"] = rep.checkin_date + pd.to_timedelta(rep.groupby(level=0).cumcount(), unit="D")
    sold = rep.groupby(["hotel_id", "date"]).size().rename("rooms_sold").reset_index()
    hotels = clean["hotels"]
    dates = pd.date_range("2021-01-01", "2025-12-31")
    frames = []
    for _, h in hotels.iterrows():
        d = dates[dates >= h.opening_date]
        frames.append(pd.DataFrame({"hotel_id": h.hotel_id, "date": d, "rooms": h.rooms,
                                    "days_open": (d - h.opening_date).days}))
    hd = pd.concat(frames).merge(sold, on=["hotel_id", "date"], how="left").fillna({"rooms_sold": 0})
    hd["occupancy"] = hd.rooms_sold / hd.rooms
    cal = clean["calendar"].set_index("date")
    hd["year"] = hd.date.dt.year
    hd["month"] = hd.date.dt.month
    hd["dow"] = hd.date.dt.dayofweek
    hd["week"] = hd.date.dt.isocalendar().week.astype(int)
    hd["day_of_year"] = hd.date.dt.dayofyear
    hd["is_holiday"] = hd.date.map(cal.is_public_holiday).astype(int)
    ev = city_event_days(clean)
    hd = hd.merge(ev, on=["hotel_id", "date"], how="left").fillna({"events": 0, "event_attendance": 0})
    comp = clean["competitor_rates"]
    hd = hd.merge(comp[["hotel_id", "stay_date", "comp_avg_rate_eur"]].rename(columns={"stay_date": "date"}),
                  on=["hotel_id", "date"], how="left")
    hd = hd.merge(hotels[["hotel_id", "city_id", "stars"]], on="hotel_id")
    hd = hd.sort_values(["hotel_id", "date"]).reset_index(drop=True)
    # last year's demand (known one year ahead)
    g = hd.groupby("hotel_id")
    hd["occ_lag364"] = g.occupancy.shift(364)
    hd["occ_lag364_ma28"] = g.occupancy.transform(lambda s: s.shift(364).rolling(28, min_periods=7, center=True).mean())
    hd["comp_rate_yoy"] = hd.comp_avg_rate_eur / g.comp_avg_rate_eur.shift(364)
    return hd


DEMAND_NUM = ["rooms", "days_open", "month", "dow", "week", "day_of_year", "is_holiday", "events",
              "event_attendance", "comp_avg_rate_eur", "stars", "occ_lag364", "occ_lag364_ma28", "comp_rate_yoy", "year"]
DEMAND_CAT = ["hotel_id"]


def quote_features(clean):
    q = clean["rate_quotes"].copy()
    rt, rp, comp = _price_refs(clean)
    q["comp_rate_eur"] = _comp_lookup(comp, q.hotel_id, q.checkin_date)
    q["price_index"] = q.price_per_night_eur / (q.comp_rate_eur * q.room_type_id.map(rt) * q.rate_plan_id.map(rp))
    q["log_price_index"] = np.log(q.price_index)
    q["lead_time_days"] = (q.checkin_date - q.quote_datetime.dt.normalize()).dt.days
    q["logged_in"] = q.guest_id.notna().astype(int)
    q["year"] = q.quote_datetime.dt.year
    q["weekend_stay"] = (q.checkin_date.dt.dayofweek >= 4).astype(int)
    q["quote_rank"] = q.groupby("session_id").cumcount()
    return q
