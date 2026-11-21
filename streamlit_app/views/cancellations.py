"""
Script:   views/cancellations.py
Purpose:  Page 3, bookings and cancellations. Booking volume, cancellation and no-show
          rates by year, lead time, rate plan and channel, and the 2025 test of the
          cancellation model: how many cancellations the riskiest bookings hold,
          ROC curve, calibration and the strongest features.
Input:    bookings (lumora_data), output/tables/cancel_*.csv (from notebook 03)
Output:   Streamlit page
"""
import numpy as np
import plotly.graph_objects as go
import streamlit as st

import lumora_data as D
import lumora_theme as T

f = D.get_filters()
core = D.load_core()
tabs = D.load_tables()
b, cap = D.filtered_core(f)
period = "2021-2025" if f["year"] == "All years" else str(f["year"])

T.page_header("Bookings <b>& cancellations</b>",
              f"Who cancels, when, and how well the model sees it coming · {period} · by arrival date",
              chips=[f"{len(b):,} bookings"])
if b.empty:
    st.info("No bookings match these filters.")
    st.stop()

# KPI cards ----
k = D.kpis(b, cap)
py = D.prev_years(f)
kp = D.kpis(*D.filtered_core(f, years=py)) if py else {}
note = f"vs {py[0]}" if py else "all years"
lost = b.loc[b.is_cancelled == 1, "adr_eur"].mul(b.loc[b.is_cancelled == 1, "nights"]).sum()


def kpi(label, value, key, kind="pct", hib=True):
    delta, good = T.change(k[key], kp.get(key), kind, hib)
    return dict(label=label, value=value, delta=delta, good=good, note=note)


T.kpi_strip([
    kpi("Bookings", f"{k['bookings']:,}", "bookings"),
    kpi("Cancellation rate", f"{k['cancel_rate']:.1%}", "cancel_rate", "pp", False),
    kpi("No-show rate", f"{k['no_show_rate']:.1%}", "no_show_rate", "pp", False),
    kpi("Avg lead time", f"{k['lead']:.0f} days", "lead"),
    dict(label="Cancelled room value", value=T.eur(lost), delta=None, note="ADR × nights of cancelled bookings"),
])

# Trend and lead time ----
c1, c2 = st.columns([1.4, 1], gap="medium")
with c1, T.card("trend"):
    T.card_title("Cancellation and no-show rate by month", "Year slicer not applied, so the COVID year 2021 stays visible")
    ball = D.apply_filters(core["bookings"], f, years=D.YEARS)
    m = ball.groupby("month").agg(cx=("is_cancelled", "mean"), ns=("no_show", "mean"))
    fig = go.Figure()
    fig.add_scatter(x=m.index, y=m.cx, name="Cancelled", mode="lines", line=dict(color=T.ORANGE, width=2.4),
                    fill="tozeroy", fillcolor="rgba(238,138,76,0.12)", hovertemplate="%{y:.1%}")
    fig.add_scatter(x=m.index, y=m.ns, name="No-show", mode="lines", line=dict(color=T.INK_2, width=2),
                    hovertemplate="%{y:.1%}")
    fig.update_yaxes(tickformat=".0%", rangemode="tozero")
    fig.update_xaxes(hoverformat="%b %Y")
    fig.update_layout(hovermode="x unified")
    T.chart(fig, 320)

with c2, T.card("lead"):
    T.card_title("Cancellation rate by lead time", "Days between booking and arrival")
    lb = b.groupby("lead_bucket", observed=False).agg(rate=("is_cancelled", "mean"), n=("booking_id", "size"))
    fig = go.Figure(go.Bar(x=lb.index.astype(str), y=lb.rate, marker_color=T.ORANGE, customdata=lb.n,
                           text=[f"{v:.0%}" for v in lb.rate], textposition="outside", cliponaxis=False,
                           textfont=dict(color=T.TEXT_MUTED, size=11),
                           hovertemplate="%{x}: %{y:.1%} of %{customdata:,} bookings<extra></extra>"))
    fig.update_yaxes(tickformat=".0%", rangemode="tozero")
    T.chart(fig, 320)

# Rate plan and channel ----
c1, c2 = st.columns(2, gap="medium")


def rate_bar(df, col, title, sub, key):
    with T.card(key):
        T.card_title(title, sub)
        g = df.groupby(col).agg(rate=("is_cancelled", "mean"), n=("booking_id", "size")).sort_values("rate")
        fig = go.Figure(go.Bar(y=g.index, x=g.rate, orientation="h", customdata=g.n,
                               marker_color=[T.INK_2 if v == g.rate.max() else T.ORANGE for v in g.rate],
                               text=[f"{v:.1%}" for v in g.rate], textposition="outside", cliponaxis=False,
                               textfont=dict(color=T.TEXT_MUTED, size=11),
                               hovertemplate="%{y}: %{x:.1%} of %{customdata:,} bookings<extra></extra>"))
        fig.update_xaxes(tickformat=".0%", showgrid=True, gridcolor=T.GRID)
        fig.update_yaxes(showgrid=False)
        fig.update_layout(margin=dict(r=50))
        T.chart(fig, 280)


with c1:
    rate_bar(b, "rate_plan", "Cancellation rate by rate plan", "Highest rate shown in navy", "plan")
with c2:
    rate_bar(b, "channel_name", "Cancellation rate by booking channel", "Highest rate shown in navy", "channel")

# Model (2025 test year) ----
st.markdown('<div class="page-title" style="font-size:20px;margin-top:18px">Cancellation model '
            '<span style="color:#7A7F8C;font-weight:400;font-size:14px">· trained on 2021-2024, tested on 2025 '
            '· hotel, channel and segment slicers apply</span></div>', unsafe_allow_html=True)
st.write("")

p = tabs["cancel_predictions"].merge(core["channels"][["channel_id", "channel_group"]], on="channel_id", how="left")
p = D.apply_filters(p, f, years=None)
c1, c2, c3 = st.columns([1.1, 1, 1], gap="medium")

with c1:
    if len(p) and p.is_cancelled.sum():
        auc = D.auc_score(p.is_cancelled.values, p.p_cancel.values)
        ps = p.sort_values("p_cancel", ascending=False)
        top = ps.head(int(len(ps) * 0.2))
        caught = top.is_cancelled.sum() / ps.is_cancelled.sum()
        T.dark_card("Model check (2025)", "Cancellations in the riskiest 20% of bookings", f"{caught:.0%}",
                    [("AUC", f"{auc:.2f}"), ("Bookings scored", f"{len(p):,}"), ("Actual rate", f"{p.is_cancelled.mean():.1%}")])
        st.write("")
        with T.card("gain"):
            T.card_title("Cancellations caught vs bookings checked", "Bookings ranked by predicted risk")
            share_b = np.arange(1, len(ps) + 1) / len(ps)
            share_c = ps.is_cancelled.cumsum().values / ps.is_cancelled.sum()
            idx = np.linspace(0, len(ps) - 1, 101).astype(int)
            fig = go.Figure()
            fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", name="Random", line=dict(color=T.GREY, dash="dot", width=1.5),
                            hoverinfo="skip")
            fig.add_scatter(x=share_b[idx], y=share_c[idx], mode="lines", name="Model", line=dict(color=T.ORANGE, width=2.6),
                            hovertemplate="Top %{x:.0%} of bookings → %{y:.0%} of cancellations<extra></extra>")
            fig.update_xaxes(tickformat=".0%", showgrid=True, gridcolor=T.GRID, title_text="Bookings checked")
            fig.update_yaxes(tickformat=".0%", title_text="Cancellations caught")
            T.chart(fig, 250)
    else:
        st.info("No 2025 cancellations in this selection.")

with c2, T.card("roc"):
    T.card_title("ROC curve (all hotels)", "Gradient boosting vs logistic regression baseline")
    roc = tabs["cancel_roc"]
    fig = go.Figure()
    fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color=T.GREY, dash="dot", width=1.5),
                    showlegend=False, hoverinfo="skip")
    for name, col in [("Logistic baseline", T.INK_2), ("Gradient boosting", T.ORANGE)]:
        r = roc[roc.model == name]
        fig.add_scatter(x=r.fpr, y=r.tpr, mode="lines", name=name, line=dict(color=col, width=2.2),
                        hovertemplate="FPR %{x:.0%} · TPR %{y:.0%}<extra>" + name + "</extra>")
    fig.update_xaxes(tickformat=".0%", showgrid=True, gridcolor=T.GRID, title_text="False positive rate")
    fig.update_yaxes(tickformat=".0%", title_text="True positive rate")
    T.chart(fig, 300)
    T.card_title("Calibration", "Predicted vs actual cancel rate, 10 risk bins")
    cal = tabs["cancel_calibration"]
    fig = go.Figure()
    fig.add_scatter(x=[0, 0.5], y=[0, 0.5], mode="lines", line=dict(color=T.GREY, dash="dot", width=1.5),
                    showlegend=False, hoverinfo="skip")
    fig.add_scatter(x=cal.predicted, y=cal.actual, mode="lines+markers", showlegend=False,
                    line=dict(color=T.ORANGE), marker=dict(size=8, line=dict(color="white", width=2)),
                    hovertemplate="Predicted %{x:.1%} · actual %{y:.1%}<extra></extra>")
    fig.update_xaxes(tickformat=".0%", showgrid=True, gridcolor=T.GRID, title_text="Predicted")
    fig.update_yaxes(tickformat=".0%", title_text="Actual")
    T.chart(fig, 220)

with c3, T.card("imp"):
    T.card_title("What drives cancellations", "Permutation importance, top 12 features")
    imp = tabs["cancel_feature_importance"].head(12).iloc[::-1]
    fig = go.Figure(go.Bar(y=imp.feature.map(D.FEATURE_NAMES).fillna(imp.feature), x=imp.importance, orientation="h",
                           marker_color=T.ORANGE, hovertemplate="%{y}: %{x:.3f}<extra></extra>"))
    fig.update_xaxes(showgrid=True, gridcolor=T.GRID, title_text="Drop in AUC when shuffled")
    fig.update_yaxes(showgrid=False)
    T.chart(fig, 560)

T.footer()
