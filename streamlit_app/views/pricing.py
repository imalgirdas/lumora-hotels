"""
Script:   views/pricing.py
Purpose:  Page 4, pricing and experiments. Website / app quotes and conversion,
          our ADR vs the competitor average, conversion by price index, the randomised
          price test and price elasticity, and the four A/B tests with confidence intervals.
Input:    rate_quotes, competitor_rates, bookings (lumora_data)
          output/tables/price_*.csv, conversion_by_price_index.csv, ab_test_results.csv
Output:   Streamlit page
"""
import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import lumora_data as D
import lumora_theme as T

f = D.get_filters()
core = D.load_core()
qd = D.load_quotes()
tabs = D.load_tables()
period = "2021-2025" if f["year"] == "All years" else str(f["year"])

q = D.apply_filters(qd["quotes"], f)
T.page_header("Pricing <b>& experiments</b>",
              f"Website and app price quotes, competitor prices and A/B tests · {period} · by quote date",
              chips=["Year and hotel slicers apply to quotes", "Test results are fixed (from notebook 03)"])
if q.empty:
    st.info("No quotes match these filters.")
    st.stop()

# KPI cards ----
py = D.prev_years(f)
qp = D.apply_filters(qd["quotes"], f, years=py) if py else None
note = f"vs {py[0]}" if py else "all years"


def qk(df):
    return dict(n=len(df), conv=df.converted.mean(), rpq=df.revenue.sum() / len(df), price=df.price_per_night_eur.mean())


k, kp = qk(q), (qk(qp) if qp is not None and len(qp) else {})
b, _ = D.filtered_core(f)
comp = D.apply_filters(qd["competitor"].assign(year=qd["competitor"].stay_date.dt.year), f)
stays = b[b.room_nights > 0]
adr = (stays.adr_eur * stays.room_nights).sum() / stays.room_nights.sum()
comp_avg = comp.comp_avg_rate_eur.mean()


def kpi(label, value, key, kind="pct", hib=True):
    delta, good = T.change(k[key], kp.get(key), kind, hib)
    return dict(label=label, value=value, delta=delta, good=good, note=note)


elast = tabs["price_test_by_variant"]
T.kpi_strip([
    kpi("Price quotes", f"{k['n']:,}", "n"),
    kpi("Quote conversion", f"{k['conv']:.1%}", "conv", "pp"),
    kpi("Revenue per quote", f"€{k['rpq']:,.0f}", "rpq"),
    kpi("Avg quoted price / night", f"€{k['price']:,.0f}", "price"),
    dict(label="Our ADR vs competitors", value=f"{adr / comp_avg - 1:+.0%}", delta=None,
         note=f"€{adr:,.0f} vs €{comp_avg:,.0f} competitor avg"),
])

# ADR vs competitors, conversion by price index ----
c1, c2 = st.columns([1.5, 1], gap="medium")
with c1, T.card("adr"):
    T.card_title("Our ADR vs competitor average rate", "Per night, by month · year slicer not applied")
    ball = D.apply_filters(core["bookings"], f, years=D.YEARS)
    ball = ball[ball.room_nights > 0]
    m = ball.assign(w=ball.adr_eur * ball.room_nights).groupby("month")[["w", "room_nights"]].sum()
    m = m.w / m.room_nights
    call = D.apply_filters(qd["competitor"].assign(year=qd["competitor"].stay_date.dt.year), f, years=D.YEARS)
    cm = call.groupby("month").comp_avg_rate_eur.mean()
    fig = go.Figure()
    fig.add_scatter(x=cm.index, y=cm.values, name="Competitor average", mode="lines",
                    line=dict(color=T.GREY, width=2, dash="dot"), hovertemplate="€%{y:,.0f}")
    fig.add_scatter(x=m.index, y=m.values, name="Lumora ADR", mode="lines",
                    line=dict(color=T.ORANGE, width=2.6), hovertemplate="€%{y:,.0f}")
    fig.update_yaxes(tickprefix="€", rangemode="tozero")
    fig.update_xaxes(hoverformat="%b %Y")
    fig.update_layout(hovermode="x unified")
    T.chart(fig, 320)

with c2, T.card("pidx"):
    T.card_title("Conversion by price index", "Our quoted price ÷ competitor price for the same room type and plan")
    cp = tabs["conversion_by_price_index"]
    fig = go.Figure(go.Bar(x=cp.price_bin, y=cp.conversion, customdata=cp.quotes,
                           marker_color=[T.ORANGE if "<" in s or s.startswith("0.") else T.ORANGE_LIGHT for s in cp.price_bin],
                           text=[f"{v:.0%}" for v in cp.conversion], textposition="outside", cliponaxis=False,
                           textfont=dict(color=T.TEXT_MUTED, size=10),
                           hovertemplate="Index %{x}: %{y:.1%} of %{customdata:,} quotes<extra></extra>"))
    fig.update_yaxes(tickformat=".0%", rangemode="tozero")
    fig.update_xaxes(title_text="Price index (darker = cheaper than competitors)", tickangle=-40, tickfont=dict(size=10))
    T.chart(fig, 320)

# Price test and elasticity ----
c1, c2, c3 = st.columns([1.2, 0.9, 1.1], gap="medium")
with c1, T.card("ptest"):
    T.card_title("Price test, summer 2024", "Randomised −8% / current / +8% prices per website session")
    v = elast.assign(label=elast.variant.map({"price_minus_8": "−8%", "control": "Current", "price_plus_8": "+8%"}))
    v = v.set_index("label").loc[["−8%", "Current", "+8%"]]
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Conversion", "Revenue per quote"), horizontal_spacing=0.14)
    colors = [T.ORANGE, T.INK_2, T.ORANGE_LIGHT]
    fig.add_bar(x=v.index, y=v.conversion, marker_color=colors, text=[f"{x:.1%}" for x in v.conversion],
                textposition="outside", cliponaxis=False, textfont=dict(color=T.TEXT_MUTED, size=11),
                showlegend=False, hovertemplate="%{x}: %{y:.1%}<extra></extra>", row=1, col=1)
    fig.add_bar(x=v.index, y=v.revenue_per_quote, marker_color=colors, text=[f"€{x:,.0f}" for x in v.revenue_per_quote],
                textposition="outside", cliponaxis=False, textfont=dict(color=T.TEXT_MUTED, size=11),
                showlegend=False, hovertemplate="%{x}: €%{y:,.1f}<extra></extra>", row=1, col=2)
    fig.update_yaxes(tickformat=".0%", row=1, col=1)
    fig.update_yaxes(tickprefix="€", row=1, col=2)
    fig.update_xaxes(type="category")
    fig.update_annotations(font=dict(size=12, color=T.TEXT_MUTED))
    fig.update_layout(margin=dict(t=30))
    T.chart(fig, 300)

with c2:
    pm = tabs["price_elasticity_by_group"]
    # arc elasticity between the -8% and +8% arms of the test
    t = elast.set_index("variant")
    e = np.log(t.conversion["price_plus_8"] / t.conversion["price_minus_8"]) / \
        np.log(t.avg_price["price_plus_8"] / t.avg_price["price_minus_8"])
    T.dark_card("Price sensitivity", "1% higher price cuts bookings by", f"{-e:.1f}%",
                [("Weekend", f"{pm.set_index('group').elasticity['Weekend stay']:.1f}"),
                 ("Weekday", f"{pm.set_index('group').elasticity['Weekday stay']:.1f}")])
    st.write("")
    lift = t.revenue_per_quote["price_minus_8"] / t.revenue_per_quote["control"] - 1
    st.markdown(f'<div class="insight">The −8% price earned <b>{lift:+.0%} revenue per quote</b> vs the current '
                'price. Weekend and long-lead guests are the most price sensitive.</div>', unsafe_allow_html=True)

with c3, T.card("elast"):
    T.card_title("Price elasticity by group", "% change in bookings for a 1% price rise")
    pm = pm.iloc[::-1]
    fig = go.Figure(go.Bar(y=pm.group, x=pm.elasticity, orientation="h", customdata=pm.quotes,
                           marker_color=[T.INK_2 if e < -1.5 else T.ORANGE for e in pm.elasticity],
                           text=[f"{e:.2f}" for e in pm.elasticity], textposition="outside", cliponaxis=False,
                           textfont=dict(color=T.TEXT_MUTED, size=11),
                           hovertemplate="%{y}: %{x:.2f} (%{customdata:,} quotes)<extra></extra>"))
    fig.update_xaxes(showgrid=True, gridcolor=T.GRID, range=[-2.5, 0])
    fig.update_yaxes(showgrid=False)
    fig.update_layout(margin=dict(l=10, r=10))
    T.chart(fig, 300)

# A/B tests and funnel by device / source ----
c1, c2 = st.columns([1.3, 1], gap="medium")
with c1, T.card("ab"):
    T.card_title("Website A/B tests", "Conversion change vs control in percentage points, with 95% confidence interval")
    ab = tabs["ab_test_results"].copy()
    ab["label"] = ab.experiment_name.str.replace("Price test (-8% / +8%)", "Price test", regex=False) + " · " + ab.variant
    ab = ab.iloc[::-1]
    col = [T.GREEN if s and d > 0 else (T.RED if s else T.GREY) for s, d in zip(ab.significant, ab.diff_pp)]
    fig = go.Figure()
    fig.add_scatter(x=ab.diff_pp, y=ab.label, mode="markers", marker=dict(size=12, color=col, line=dict(color="white", width=2)),
                    error_x=dict(type="data", symmetric=False, array=ab.ci_high_pp - ab.diff_pp,
                                 arrayminus=ab.diff_pp - ab.ci_low_pp, color=T.TEXT_MUTED, thickness=1.6, width=6),
                    customdata=ab[["ci_low_pp", "ci_high_pp", "p_value"]].values, showlegend=False,
                    hovertemplate="%{y}<br>%{x:+.1f} pp (95% CI %{customdata[0]:+.1f} to %{customdata[1]:+.1f})"
                                  "<br>p = %{customdata[2]:.3g}<extra></extra>")
    fig.add_vline(x=0, line=dict(color=T.TEXT_MUTED, width=1, dash="dot"))
    fig.update_xaxes(ticksuffix=" pp", showgrid=True, gridcolor=T.GRID, zeroline=False)
    fig.update_yaxes(showgrid=False)
    T.chart(fig, 300)
    st.markdown('<div class="card-sub" style="padding-bottom:10px">Green = significant win · red = significant loss · '
                'grey = no effect (the "only X rooms left" message).</div>', unsafe_allow_html=True)

with c2, T.card("device"):
    T.card_title("Conversion by device and traffic source", f"Share of quotes that became a booking · {period}")
    dv = q.groupby("device").converted.mean().rename({"desktop": "Desktop", "mobile_web": "Mobile web", "app": "App"})
    src = q.groupby("traffic_source").converted.mean().sort_values()
    src.index = src.index.str.replace("_", " ").str.capitalize()
    fig = make_subplots(rows=1, cols=2, column_widths=[0.38, 0.62], horizontal_spacing=0.2,
                        subplot_titles=("Device", "Traffic source"))
    fig.add_bar(y=dv.index, x=dv.values, orientation="h", marker_color=T.INK_2, showlegend=False,
                hovertemplate="%{y}: %{x:.1%}<extra></extra>", row=1, col=1)
    fig.add_bar(y=src.index, x=src.values, orientation="h", marker_color=T.ORANGE, showlegend=False,
                hovertemplate="%{y}: %{x:.1%}<extra></extra>", row=1, col=2)
    fig.update_xaxes(tickformat=".0%", showgrid=True, gridcolor=T.GRID, nticks=4)
    fig.update_yaxes(showgrid=False)
    fig.update_annotations(font=dict(size=12, color=T.TEXT_MUTED))
    fig.update_layout(margin=dict(t=30))
    T.chart(fig, 330)

T.footer()
