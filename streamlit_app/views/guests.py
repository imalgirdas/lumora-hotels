"""
Script:   views/guests.py
Purpose:  Page 5, guests and reviews. Review score and recommend rate, the link with
          staff turnover, review sub-scores, what drives the score (regression from
          notebook 03), the most common review phrases, guest value segments,
          extras by category and where guests come from.
Input:    reviews, staffing_monthly, guests, stay_charges (lumora_data)
          output/tables/review_drivers.csv, review_phrases.csv, guest_segment_profiles.csv
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
rd = D.load_reviews()
tabs = D.load_tables()
period = "2021-2025" if f["year"] == "All years" else str(f["year"])

rv = D.apply_filters(rd["reviews"], f)
b, cap = D.filtered_core(f)
T.page_header("Guests <b>& reviews</b>", f"Guest experience, value segments and extra spend · {period}",
              chips=[f"{len(rv):,} reviews", f"{b.guest_id.nunique():,} guests"])
if rv.empty or b.empty:
    st.info("No reviews match these filters.")
    st.stop()

# KPI cards ----
py = D.prev_years(f)
note = f"vs {py[0]}" if py else "all years"


def guest_kpis(rv_, b_):
    stays = b_.stayed.sum()
    per_guest = b_.groupby("guest_id").size()
    return dict(score=rv_.overall_score.mean(), rec=rv_.would_recommend.mean(), n=len(rv_),
                extras=b_.extras.sum() / stays if stays else float("nan"),
                repeat=(per_guest > 1).mean() if len(per_guest) else float("nan"))


k = guest_kpis(rv, b)
kp = guest_kpis(D.apply_filters(rd["reviews"], f, years=py), D.filtered_core(f, years=py)[0]) if py else {}


def kpi(label, value, key, kind="pct", hib=True):
    delta, good = T.change(k[key], kp.get(key), kind, hib)
    return dict(label=label, value=value, delta=delta, good=good, note=note)


T.kpi_strip([
    kpi("Avg review score", f"{k['score']:.2f}", "score", "abs"),
    kpi("Would recommend", f"{k['rec']:.1%}", "rec", "pp"),
    kpi("Reviews", f"{k['n']:,}", "n"),
    kpi("Extras per stay", f"€{k['extras']:,.0f}", "extras"),
    kpi("Guests with 2+ bookings", f"{k['repeat']:.1%}", "repeat", "pp"),
])

# Reviews vs staff turnover, drivers ----
c1, c2 = st.columns([1.5, 1], gap="medium")
with c1, T.card("turnover"):
    T.card_title("Review score and staff turnover by month",
                 "When turnover jumped in 2022, scores fell · year slicer not applied")
    rall = D.apply_filters(rd["reviews"], f, years=D.YEARS)
    rall = rall.assign(m=rall.review_datetime.dt.to_period("M").dt.to_timestamp())
    sm = rall.groupby("m").overall_score.mean()
    st_ = D.apply_filters(rd["staffing"], f, years=D.YEARS).groupby("month").staff_turnover_pct.mean()
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.55, 0.45])
    fig.add_scatter(x=sm.index, y=sm.values, mode="lines", line=dict(color=T.ORANGE, width=2.4), name="Review score",
                    showlegend=False, hovertemplate="%{x|%b %Y}: %{y:.2f}<extra>Score</extra>", row=1, col=1)
    fig.add_bar(x=st_.index, y=st_.values, marker_color=T.INK_2, name="Staff turnover", showlegend=False,
                marker=dict(cornerradius=2), hovertemplate="%{x|%b %Y}: %{y:.1f}%<extra>Turnover</extra>", row=2, col=1)
    fig.update_yaxes(title_text="Review score", row=1, col=1)
    fig.update_yaxes(title_text="Turnover %", ticksuffix="%", row=2, col=1)
    fig.update_layout(bargap=0.15)
    T.chart(fig, 380)

with c2, T.card("drivers"):
    T.card_title("What moves the review score", "Effect on the 1-10 score with 95% CI (regression, notebook 03)")
    dr = tabs["review_drivers"].sort_values("effect")
    fig = go.Figure(go.Bar(y=dr.driver, x=dr.effect, orientation="h",
                           marker_color=[T.ORANGE if e > 0 else T.INK_2 for e in dr.effect],
                           error_x=dict(type="data", symmetric=False, array=dr.ci_high - dr.effect,
                                        arrayminus=dr.effect - dr.ci_low, color=T.TEXT_MUTED, thickness=1.2, width=3),
                           hovertemplate="%{y}: %{x:+.2f} points<extra></extra>"))
    fig.update_xaxes(showgrid=True, gridcolor=T.GRID, title_text="Points of review score")
    fig.update_yaxes(showgrid=False, tickfont=dict(size=11))
    T.chart(fig, 380)

# Sub-scores, phrases, segments ----
c1, c2, c3 = st.columns([0.9, 1.1, 1.1], gap="medium")
with c1, T.card("subs"):
    T.card_title("Review sub-scores", f"Average out of 10 · {period}")
    subs = {"cleanliness": "Cleanliness", "staff": "Staff", "location": "Location", "comfort": "Comfort",
            "value_for_money": "Value for money"}
    sv = rv[list(subs)].mean().rename(subs).sort_values()
    fig = go.Figure(go.Bar(y=sv.index, x=sv.values, orientation="h",
                           marker_color=[T.INK_2 if v == sv.min() else T.ORANGE for v in sv.values],
                           text=[f"{v:.2f}" for v in sv.values], textposition="inside", insidetextanchor="end",
                           textfont=dict(color="white", size=12), hovertemplate="%{y}: %{x:.2f}<extra></extra>"))
    fig.update_xaxes(range=[0, 10], showgrid=True, gridcolor=T.GRID)
    fig.update_yaxes(showgrid=False)
    T.chart(fig, 330)

with c2, T.card("phrases"):
    T.card_title("What guests write", "Most mentioned phrases in review text, with their avg score")
    ph = tabs["review_phrases"]
    pos = ph[ph.tone == "Positive"].nlargest(6, "mentions")
    # generic phrases ("Good hotel", avg ~7.7) are tagged Negative in the table, so only
    # phrases from clearly unhappy reviews (avg score under 7) count as complaints here
    neg = ph[(ph.tone == "Negative") & (ph.avg_score < 7)].nlargest(6, "mentions")
    show = pd.concat([neg.iloc[::-1], pos.iloc[::-1]])
    fig = go.Figure(go.Bar(y=show.phrase, x=show.mentions, orientation="h", customdata=show.avg_score,
                           marker_color=[T.ORANGE if t == "Positive" else T.INK_2 for t in show.tone],
                           hovertemplate="%{y}: %{x:,} mentions · avg score %{customdata:.2f}<extra></extra>"))
    fig.update_xaxes(showgrid=True, gridcolor=T.GRID, tickformat=",")
    fig.update_yaxes(showgrid=False, tickfont=dict(size=11))
    T.chart(fig, 330)
    st.markdown('<div class="card-sub" style="padding-bottom:10px">Orange = positive · navy = negative '
                '(phrases from reviews scoring under 7 on average).</div>', unsafe_allow_html=True)

with c3, T.card("segs"):
    T.card_title("Guest value segments", "Share of guests vs share of total value (k-means, notebook 03)")
    sp = tabs["guest_segment_profiles"].sort_values("share_of_value")
    sp["share_guests"] = sp.guests / sp.guests.sum()
    fig = go.Figure()
    fig.add_bar(y=sp.segment, x=sp.share_guests, orientation="h", name="Guests", marker_color=T.ORANGE_LIGHT,
                hovertemplate="%{y}: %{x:.0%} of guests<extra></extra>")
    fig.add_bar(y=sp.segment, x=sp.share_of_value, orientation="h", name="Value", marker_color=T.ORANGE,
                customdata=sp.value_per_guest,
                hovertemplate="%{y}: %{x:.0%} of value · €%{customdata:,.0f} per guest<extra></extra>")
    fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.05)
    fig.update_xaxes(tickformat=".0%", showgrid=True, gridcolor=T.GRID)
    fig.update_yaxes(showgrid=False)
    T.chart(fig, 350)

# Extras and home countries ----
c1, c2 = st.columns(2, gap="medium")
with c1, T.card("extras"):
    T.card_title("Extras revenue by category", f"Restaurant, spa, parking and other charges · {period}")
    ex = D.apply_filters(core["extras"], f).groupby("category").amount_eur.sum().sort_values()
    fig = go.Figure(go.Bar(y=ex.index, x=ex.values, orientation="h", marker_color=T.ORANGE,
                           text=[T.eur(v) for v in ex.values], textposition="outside", cliponaxis=False,
                           textfont=dict(color=T.TEXT_MUTED, size=11),
                           hovertemplate="%{y}: €%{x:,.0f}<extra></extra>"))
    fig.update_xaxes(showticklabels=False, showgrid=False)
    fig.update_yaxes(showgrid=False)
    fig.update_layout(margin=dict(r=60))
    T.chart(fig, 320)

with c2, T.card("countries"):
    T.card_title("Where guests come from", f"Top 10 home countries, share of guests who booked · {period}")
    g = rd["guests"].set_index("guest_id")
    hc = g.home_country.reindex(b.guest_id.unique()).fillna("Unknown").value_counts(normalize=True).head(10).iloc[::-1]
    fig = go.Figure(go.Bar(y=hc.index, x=hc.values, orientation="h",
                           marker_color=[T.INK_2 if i == len(hc) - 1 else T.ORANGE for i in range(len(hc))],
                           text=[f"{v:.1%}" for v in hc.values], textposition="outside", cliponaxis=False,
                           textfont=dict(color=T.TEXT_MUTED, size=11),
                           hovertemplate="%{y}: %{x:.1%}<extra></extra>"))
    fig.update_xaxes(showticklabels=False, showgrid=False)
    fig.update_yaxes(showgrid=False)
    fig.update_layout(margin=dict(r=50))
    T.chart(fig, 320)

T.footer()
