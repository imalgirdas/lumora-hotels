"""
Script:   views/demand.py
Purpose:  Page 2, demand and forecast. Occupancy seasonality (hotel x month heatmap),
          occupancy by weekday and on city-event nights, and the 2025 test of the
          demand model: weekly rooms sold vs forecast vs "same day last year",
          and forecast error (WAPE) per hotel.
Input:    output/tables/hotel_daily_forecast.csv, forecast_accuracy_by_hotel.csv
          (from notebook 03)
Output:   Streamlit page
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import lumora_data as D
import lumora_theme as T

f = D.get_filters()
core = D.load_core()
tabs = D.load_tables()
names = core["hotels"].set_index("hotel_id").short_name

allnights = tabs["daily_forecast"].assign(year=lambda x: x.date.dt.year)
daily = D.apply_filters(allnights, f)     # year and hotel slicers (channel / segment do not apply)
period = "2021-2025" if f["year"] == "All years" else str(f["year"])

T.page_header("Demand <b>& forecast</b>",
              f"Rooms sold per night, seasonality and the demand model · {period}",
              chips=["Whole-hotel demand: channel and segment slicers do not apply"])

if daily.empty:
    st.info("No nights match these filters.")
    st.stop()

# KPI cards ----
sold, rooms = daily.rooms_sold.sum(), daily.rooms.sum()
occ = sold / rooms
by_day = daily.groupby("date")[["rooms_sold", "rooms"]].sum()
peak = (by_day.rooms_sold / by_day.rooms).max()
full_nights = (daily.occupancy >= 0.95).mean()
py = D.prev_years(f)
prev = {}
if py:
    dp = D.apply_filters(allnights, f, years=py)
    prev = dict(occ=dp.rooms_sold.sum() / dp.rooms.sum(), sold=dp.rooms_sold.sum(),
                full=(dp.occupancy >= 0.95).mean())
note = f"vs {py[0]}" if py else "all years"

# model accuracy is only measured on 2025 (the test year)
test = D.apply_filters(allnights, f, years=[2025])
wape_m = (test.rooms_sold - test.forecast_rooms).abs().sum() / test.rooms_sold.sum()
wape_n = (test.rooms_sold - test.naive_rooms).abs().sum() / test.rooms_sold.sum()


def kpi(label, value, cur, key, kind="pct"):
    delta, good = T.change(cur, prev.get(key), kind)
    return dict(label=label, value=value, delta=delta, good=good, note=note)


T.kpi_strip([
    kpi("Room-nights sold", f"{sold:,.0f}", sold, "sold"),
    kpi("Occupancy", f"{occ:.1%}", occ, "occ", "pp"),
    dict(label="Busiest night", value=f"{peak:.0%}", delta=None, note="occupancy of the selected hotels"),
    kpi("Nights ≥ 95% full", f"{full_nights:.1%}", full_nights, "full", "pp"),
    dict(label="Forecast error (WAPE)", value=f"{wape_m:.1%}", delta=f"▼ {(wape_m - wape_n) * 100:+.1f} pp",
         good=bool(wape_m < wape_n), note="vs last-year baseline · 2025"),
])

# Seasonality heatmap, weekday and events ----
c1, c2 = st.columns([1.6, 1], gap="medium")
with c1, T.card("heat"):
    T.card_title("Occupancy by hotel and month", f"Share of rooms sold · {period}")
    hm = daily.assign(m=daily.date.dt.month).groupby(["hotel_id", "m"])[["rooms_sold", "rooms"]].sum()
    hm = (hm.rooms_sold / hm.rooms).unstack()
    hm.index = hm.index.map(names)
    hm = hm.loc[hm.mean(axis=1).sort_values().index]
    month_names = pd.date_range("2021-01-01", periods=12, freq="MS").strftime("%b")
    txt = [[f"{v:.0%}" if v == v else "" for v in row] for row in hm.values]
    fig = go.Figure(go.Heatmap(z=hm.values, x=month_names[hm.columns - 1], y=hm.index, colorscale=T.SEQ_ORANGE,
                               zmin=0, zmax=1, xgap=3, ygap=3, text=txt, texttemplate="%{text}",
                               textfont=dict(size=10),
                               colorbar=dict(tickformat=".0%", thickness=10, outlinewidth=0, len=0.8),
                               hovertemplate="%{y} · %{x}: %{z:.1%}<extra></extra>"))
    fig.update_xaxes(side="top")
    fig.update_yaxes(showgrid=False)
    T.chart(fig, 500)

with c2:
    with T.card("dow"):
        T.card_title("Occupancy by weekday", "Every night counted, Friday and Saturday highlighted")
        dw = daily.assign(d=daily.date.dt.dayofweek).groupby("d")[["rooms_sold", "rooms"]].sum()
        dw = dw.rooms_sold / dw.rooms
        labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        fig = go.Figure(go.Bar(x=[labels[i] for i in dw.index], y=dw.values,
                               marker_color=[T.ORANGE if i in (4, 5) else T.ORANGE_LIGHT for i in dw.index],
                               text=[f"{v:.0%}" for v in dw.values], textposition="outside", cliponaxis=False,
                               textfont=dict(color=T.TEXT_MUTED, size=11),
                               hovertemplate="%{x}: %{y:.1%}<extra></extra>"))
        fig.update_yaxes(tickformat=".0%", range=[0, 1])
        T.chart(fig, 200)
    st.write("")
    with T.card("events"):
        T.card_title("City events lift demand", "Occupancy on nights with and without a held event")
        ev = daily.assign(e=np.where(daily.events > 0, "Event in city", "No event"))
        ev = ev.groupby("e")[["rooms_sold", "rooms"]].sum()
        ev = (ev.rooms_sold / ev.rooms).reindex(["No event", "Event in city"]).dropna()
        fig = go.Figure(go.Bar(y=ev.index, x=ev.values, orientation="h",
                               marker_color=[T.ORANGE_LIGHT if i == "No event" else T.ORANGE for i in ev.index],
                               text=[f"{v:.1%}" for v in ev.values], textposition="outside", cliponaxis=False,
                               textfont=dict(color=T.TEXT_MUTED, size=11),
                               hovertemplate="%{y}: %{x:.1%}<extra></extra>"))
        fig.update_xaxes(tickformat=".0%", range=[0, 1], showgrid=True, gridcolor=T.GRID)
        fig.update_yaxes(showgrid=False)
        fig.update_layout(bargap=0.45)
        T.chart(fig, 150)

# 2025 forecast test ----
c1, c2 = st.columns([1.6, 1], gap="medium")
with c1, T.card("forecast"):
    T.card_title("2025 rooms sold per week: actual vs forecast",
                 "Model trained on 2021-2024 · baseline = same weekday last year · hotel slicer applies")
    w = test.set_index("date")[["rooms_sold", "forecast_rooms", "naive_rooms"]].resample("W-MON").sum().iloc[1:-1]
    fig = go.Figure()
    fig.add_scatter(x=w.index, y=w.naive_rooms, name="Same day last year", mode="lines",
                    line=dict(color=T.GREY, dash="dot", width=1.6), hovertemplate="%{y:,.0f}")
    fig.add_scatter(x=w.index, y=w.forecast_rooms, name="Forecast", mode="lines",
                    line=dict(color=T.ORANGE, width=2.4), hovertemplate="%{y:,.0f}")
    fig.add_scatter(x=w.index, y=w.rooms_sold, name="Actual", mode="lines",
                    line=dict(color=T.INK_2, width=2), hovertemplate="%{y:,.0f}")
    fig.update_yaxes(title_text="Rooms sold per week", tickformat=",", rangemode="tozero")
    fig.update_xaxes(hoverformat="week of %d %b")
    fig.update_layout(hovermode="x unified")
    T.chart(fig, 360)

with c2, T.card("wape"):
    T.card_title("Forecast error by hotel (2025)", "WAPE, lower is better · model vs last-year baseline")
    acc = tabs["forecast_accuracy_by_hotel"]
    if f["hotels"]:
        acc = acc[acc.hotel_id.isin(f["hotels"])]
    acc = acc.assign(name=acc.hotel_id.map(names)).sort_values("wape_model", ascending=False)
    fig = go.Figure()
    fig.add_bar(y=acc.name, x=acc.wape_naive, orientation="h", name="Same day last year", marker_color=T.ORANGE_LIGHT,
                hovertemplate="%{y}: %{x:.1%}<extra>Last year</extra>")
    fig.add_bar(y=acc.name, x=acc.wape_model, orientation="h", name="Model", marker_color=T.ORANGE,
                hovertemplate="%{y}: %{x:.1%}<extra>Model</extra>")
    fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.05)
    fig.update_xaxes(tickformat=".0%", showgrid=True, gridcolor=T.GRID)
    fig.update_yaxes(showgrid=False)
    T.chart(fig, 360)

T.footer()
