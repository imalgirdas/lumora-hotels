"""
Script:   views/overview.py
Purpose:  Page 1, business overview. KPI cards (room revenue, RevPAR, occupancy, ADR,
          cancellation rate, review score) vs the year before, monthly revenue and
          occupancy, RevPAR by hotel, channel mix by year and revenue by guest segment.
Input:    lumora_data (bookings, capacity, reviews) and the sidebar filters
Output:   Streamlit page
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import lumora_data as D
import lumora_theme as T

f = D.get_filters()
core = D.load_core()
b, cap = D.filtered_core(f)
k = D.kpis(b, cap)
rv = D.apply_filters(D.load_reviews()["reviews"], f)
period = "2021-2025" if f["year"] == "All years" else str(f["year"])

T.page_header("Business <b>overview</b>",
              f"Revenue, occupancy and channel mix · {period} · by arrival date",
              chips=[f"{k['bookings']:,} bookings", f"{len(set(b.hotel_id))} hotels"])

if k["bookings"] == 0:
    st.info("No bookings match these filters.")
    st.stop()

# KPI cards ----
py = D.prev_years(f)
if py:
    bp, cp = D.filtered_core(f, years=py)
    kp = D.kpis(bp, cp)
    rvp = D.apply_filters(D.load_reviews()["reviews"], f, years=py)
    score_prev = rvp.overall_score.mean() if len(rvp) else None
    note = f"vs {py[0]}"
else:
    kp, score_prev, note = {}, None, "all years"
score = rv.overall_score.mean() if len(rv) else float("nan")


def d(key, kind="pct", hib=True):
    return T.change(k[key], kp.get(key), kind, hib)


items = []
for label, key, value, kind, hib in [
    ("Room revenue", "revenue", T.eur(k["revenue"]), "pct", True),
    ("RevPAR", "revpar", f"€{k['revpar']:,.1f}", "pct", True),
    ("Occupancy", "occupancy", f"{k['occupancy']:.1%}", "pp", True),
    ("ADR", "adr", f"€{k['adr']:,.1f}", "pct", True),
    ("Cancellation rate", "cancel_rate", f"{k['cancel_rate']:.1%}", "pp", False),
]:
    delta, good = d(key, kind, hib)
    items.append(dict(label=label, value=value, delta=delta, good=good, note=note))
sd, sg = T.change(score, score_prev, "abs", True)
items.append(dict(label="Avg review score", value=f"{score:.2f}", delta=sd, good=sg, note=note))
T.kpi_strip(items)

# Monthly revenue + occupancy, status card ----
left, right = st.columns([2.2, 1], gap="medium")
with left, T.card("monthly"):
    cap_all = D.apply_filters(core["capacity"], f, years=D.YEARS)
    b_all = D.apply_filters(core["bookings"], f, years=D.YEARS)
    m = b_all.groupby("month").agg(revenue=("room_revenue_eur", "sum"), rn=("room_nights", "sum"))
    m = m.join(cap_all.groupby("month").room_nights_available.sum()).reset_index()
    m["occ"] = m.rn / m.room_nights_available
    if py:
        T.card_title("Room revenue and occupancy by month", f"{f['year']} compared with {py[0]}")
        cur = m[m.month.dt.year == f["year"]].assign(x=lambda x: x.month.dt.strftime("%b"))
        prv = m[m.month.dt.year == py[0]].assign(x=lambda x: x.month.dt.strftime("%b"))
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.62, 0.38], vertical_spacing=0.08)
        fig.add_bar(x=prv.x, y=prv.revenue, name=str(py[0]), marker_color=T.ORANGE_LIGHT,
                    hovertemplate="%{x} " + str(py[0]) + ": €%{y:,.0f}<extra></extra>", row=1, col=1)
        fig.add_bar(x=cur.x, y=cur.revenue, name=str(f["year"]), marker_color=T.ORANGE,
                    hovertemplate="%{x} " + str(f["year"]) + ": €%{y:,.0f}<extra></extra>", row=1, col=1)
        fig.add_scatter(x=prv.x, y=prv.occ, name=f"Occupancy {py[0]}", mode="lines", showlegend=False,
                        line=dict(color=T.GREY, dash="dot"), hovertemplate="%{x}: %{y:.1%}<extra></extra>", row=2, col=1)
        fig.add_scatter(x=cur.x, y=cur.occ, name=f"Occupancy {f['year']}", mode="lines+markers", showlegend=False,
                        line=dict(color=T.INK_2), marker=dict(size=7, line=dict(color="white", width=2)),
                        hovertemplate="%{x}: %{y:.1%}<extra></extra>", row=2, col=1)
        fig.update_layout(barmode="group", bargap=0.35, bargroupgap=0.08)
    else:
        T.card_title("Room revenue and occupancy by month", "All years by arrival month")
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.62, 0.38], vertical_spacing=0.08)
        fig.add_bar(x=m.month, y=m.revenue, name="Room revenue", marker_color=T.ORANGE, showlegend=False,
                    hovertemplate="%{x|%b %Y}: €%{y:,.0f}<extra></extra>", row=1, col=1)
        fig.add_scatter(x=m.month, y=m.occ, name="Occupancy", mode="lines", line=dict(color=T.INK_2),
                        showlegend=False, hovertemplate="%{x|%b %Y}: %{y:.1%}<extra></extra>", row=2, col=1)
    fig.update_yaxes(tickprefix="€", tickformat="~s", title_text="Room revenue", row=1, col=1)
    fig.update_yaxes(tickformat=".0%", title_text="Occupancy", rangemode="tozero", row=2, col=1)
    T.chart(fig, 380)

with right:
    stays = b[b.stayed == 1]
    T.dark_card("Status summary", "Room-nights sold", f"{k['room_nights']:,.0f}",
                [("Extras", T.eur(k["extras"])), ("OTA & agency commission", T.eur(b.commission.sum()))])
    st.write("")
    with T.card("rings"):
        c1, c2 = st.columns(2)
        direct = (b.channel_group == "Direct").mean()
        rec = rv.would_recommend.mean() if len(rv) else 0
        with c1:
            T.chart(T.ring(direct, "Direct", T.ORANGE), 110)
            st.markdown('<div class="card-sub" style="text-align:center">Direct bookings</div>', unsafe_allow_html=True)
        with c2:
            T.chart(T.ring(rec, "Recommend", T.INK_2), 110)
            st.markdown('<div class="card-sub" style="text-align:center">Would recommend</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="card-sub" style="text-align:center; padding-bottom:10px">Extras per stay: <b>€{k["extras_per_stay"]:,.0f}</b>'
                    f' · Avg lead time: <b>{k["lead"]:.0f} days</b></div>', unsafe_allow_html=True)

# Hotels, channels, segments ----
c1, c2, c3 = st.columns([1.15, 1, 1], gap="medium")
with c1, T.card("revpar"):
    T.card_title("RevPAR by hotel", "Room revenue per available room-night")
    h = b.groupby("short_name").room_revenue_eur.sum().to_frame("rev").join(
        cap.merge(core["hotels"][["hotel_id", "short_name"]]).groupby("short_name").room_nights_available.sum())
    h["revpar"] = h.rev / h.room_nights_available
    h = h.dropna().sort_values("revpar")
    fig = go.Figure(go.Bar(x=h.revpar, y=h.index, orientation="h", marker_color=T.ORANGE,
                           text=[f"€{v:,.0f}" for v in h.revpar], textposition="outside",
                           textfont=dict(color=T.TEXT_MUTED, size=11), cliponaxis=False,
                           hovertemplate="%{y}: €%{x:,.1f}<extra></extra>"))
    fig.update_xaxes(showticklabels=False, showgrid=False)
    fig.update_yaxes(showgrid=False)
    fig.update_layout(bargap=0.3, margin=dict(r=40))
    T.chart(fig, 420)

with c2, T.card("channels"):
    T.card_title("Channel mix by year", "Share of bookings · year slicer not applied")
    cm = D.apply_filters(core["bookings"], f, years=D.YEARS)
    cm = cm.groupby(["year", "channel_group"]).size().unstack(fill_value=0)
    cm = cm.div(cm.sum(axis=1), axis=0)
    fig = go.Figure()
    for g in D.CHANNEL_GROUPS:
        if g in cm:
            fig.add_bar(x=cm.index.astype(str), y=cm[g], name=g, marker=dict(color=T.CHANNEL_GROUP_COLORS[g], cornerradius=0),
                        text=[f"{v:.0%}" if v >= 0.08 else "" for v in cm[g]], textposition="inside",
                        insidetextanchor="middle", textfont=dict(color="white" if g in ("OTA", "Direct") else T.INK, size=11),
                        hovertemplate="%{x} " + g + ": %{y:.1%}<extra></extra>")
    fig.update_layout(barmode="stack", bargap=0.35)
    fig.update_traces(marker_line=dict(color="white", width=2))
    fig.update_yaxes(tickformat=".0%")
    fig.update_xaxes(type="category")
    T.chart(fig, 420)

with c3, T.card("segments"):
    T.card_title("Revenue by guest segment", "Room revenue and extras (restaurant, spa, parking ...)")
    s = b.groupby("market_segment")[["room_revenue_eur", "extras"]].sum().reindex(D.SEGMENTS).dropna()
    fig = go.Figure()
    fig.add_bar(x=s.index, y=s.room_revenue_eur, name="Room revenue", marker_color=T.ORANGE,
                hovertemplate="%{x}: €%{y:,.0f}<extra></extra>")
    fig.add_bar(x=s.index, y=s.extras, name="Extras", marker_color=T.INK_2,
                hovertemplate="%{x} extras: €%{y:,.0f}<extra></extra>")
    fig.update_yaxes(tickprefix="€", tickformat="~s")
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08)
    T.chart(fig, 420)

T.footer()
