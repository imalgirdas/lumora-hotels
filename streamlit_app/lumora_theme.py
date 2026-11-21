"""
Script:   lumora_theme.py
Purpose:  Look and feel of the Streamlit dashboard: colours (cream / peach / orange
          with a dark navy accent), the page CSS, the Plotly template and small
          HTML helpers for the KPI cards and section titles.
              import lumora_theme as T
              T.inject_css()
Input:    none
Output:   used by app.py and every page in views/
"""
import os
import re
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio

# Colours ----
BG = "#F6F3EF"           # page background (warm light grey)
CARD = "#FFFFFF"         # cards and charts
PEACH = "#FAEEDB"        # soft highlight, active nav, light fills
ORANGE = "#EE8A4C"       # main series and accents
ORANGE_DARK = "#C9672C"  # text on peach, hover
ORANGE_LIGHT = "#F7C6A3" # comparison / previous period
INK = "#1E1E2C"          # dark highlight card, second series
INK_2 = "#2B2D42"
BLUE = "#4F86C6"
TEAL = "#2E9E8F"
SAND = "#D9B13B"
GREY = "#9AA0AE"         # neutral / "other"
GRID = "#EFEAE4"
LINE = "#E7E1DA"
TEXT = "#1E1E2C"
TEXT_MUTED = "#7A7F8C"
RED = "#E5484D"          # only for bad news (negative deltas)
GREEN = "#2BA471"        # only for good news (positive deltas)

# fixed order, colour follows the entity (checked with the palette validator)
CATEGORICAL = [ORANGE, INK_2, BLUE, TEAL, SAND, GREY, ORANGE_LIGHT, "#6C6F86"]
YEAR_COLORS = {2021: "#F9DCC5", 2022: "#F5C19B", 2023: "#F1A673", 2024: "#EE8A4C", 2025: INK_2}
CHANNEL_GROUP_COLORS = {"Direct": ORANGE, "OTA": INK_2, "Corporate": BLUE, "Wholesale": GREY}
SEGMENT_COLORS = {"Leisure": ORANGE, "Business": INK_2, "Family": BLUE, "Group": TEAL}
SEQ_ORANGE = [[0, "#FFF8F1"], [0.35, "#F9D6B9"], [0.7, "#EE8A4C"], [1, "#8A3D12"]]

SOURCE = "Lumora Hotels is a fictional company. All data is simulated (2021-2025)."
GRAPH_CONFIG = {"displayModeBar": False}


# Plotly template ----
def plotly_theme():
    """Register and switch on the 'lumora' Plotly template."""
    t = go.layout.Template()
    t.layout = go.Layout(
        font=dict(family="Inter, Segoe UI, Arial, sans-serif", size=12, color=TEXT),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=CATEGORICAL,
        margin=dict(l=10, r=10, t=10, b=10),
        hovermode="closest",
        hoverlabel=dict(bgcolor=INK, bordercolor=INK, font=dict(color="#FFFFFF", size=12)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    font=dict(color=TEXT_MUTED, size=11), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(automargin=True, showgrid=False, linecolor=LINE, tickcolor=LINE, ticks="", zeroline=False,
                   tickfont=dict(color=TEXT_MUTED), title=dict(font=dict(color=TEXT_MUTED, size=11))),
        yaxis=dict(automargin=True, gridcolor=GRID, zeroline=False, linecolor="rgba(0,0,0,0)", ticks="",
                   tickfont=dict(color=TEXT_MUTED), title=dict(font=dict(color=TEXT_MUTED, size=11))),
        bargap=0.28,
    )
    t.data.bar = [go.Bar(marker=dict(line=dict(width=0), cornerradius=4))]
    t.data.scatter = [go.Scatter(line=dict(width=2.2))]
    pio.templates["lumora"] = t
    pio.templates.default = "lumora"


# CSS ----
CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stApp {{ font-family: 'Inter', 'Segoe UI', sans-serif; }}
.stApp {{ background: {BG}; }}
.block-container {{ padding-top: 1.6rem; padding-bottom: 2rem; max-width: 1500px; }}
header[data-testid="stHeader"] {{ background: transparent; }}

/* sidebar */
section[data-testid="stSidebar"] {{ background: {CARD}; border-right: 1px solid {LINE}; }}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] {{ border-radius: 10px; }}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] {{ background: {PEACH}; }}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] span {{ color: {ORANGE_DARK}; font-weight: 600; }}
[class*="st-key-navlink"] a, .st-key-navactive a {{ border-radius: 10px; padding: 6px 10px; }}
[class*="st-key-navlink"] a:hover {{ background: {BG}; }}
.st-key-navactive a {{ background: {PEACH}; }}
.st-key-navactive a p, .st-key-navactive a span {{ color: {ORANGE_DARK} !important; font-weight: 600; }}
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap: 0.35rem; }}
.side-brand {{ font-size: 22px; font-weight: 700; letter-spacing: .5px; color: {INK}; margin: 0 0 2px 0; }}
.side-brand span {{ color: {ORANGE}; }}
.side-sub {{ font-size: 11px; color: {TEXT_MUTED}; text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 6px; }}
.side-label {{ font-size: 11px; color: {TEXT_MUTED}; text-transform: uppercase; letter-spacing: 1.2px; margin: 18px 0 8px 2px; font-weight: 600; }}

/* page header */
.page-title {{ font-size: 28px; font-weight: 600; color: {INK}; margin: 0; line-height: 1.2; }}
.page-title b {{ font-weight: 700; }}
.page-sub {{ color: {TEXT_MUTED}; font-size: 14px; margin: 4px 0 10px 0; }}
.chip {{ display: inline-block; background: {PEACH}; color: {ORANGE_DARK}; border-radius: 999px;
         padding: 3px 12px; font-size: 12px; font-weight: 600; margin-right: 6px; }}

/* KPI strip */
.kpi-strip {{ background: {CARD}; border-radius: 16px; box-shadow: 0 2px 14px rgba(30,30,44,.06);
              display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0; padding: 18px 8px; margin-bottom: 18px; }}
.kpi {{ padding: 2px 18px; border-left: 1px solid {LINE}; }}
.kpi:first-child {{ border-left: none; }}
.kpi-label {{ font-size: 12px; color: {TEXT_MUTED}; margin-bottom: 6px; }}
.kpi-value {{ font-size: 26px; font-weight: 700; color: {INK}; line-height: 1.1; }}
.kpi-delta {{ font-size: 12px; font-weight: 600; margin-top: 6px; }}
.kpi-delta .note {{ color: {TEXT_MUTED}; font-weight: 400; }}
.up {{ color: {GREEN}; }} .down {{ color: {RED}; }} .flat {{ color: {TEXT_MUTED}; }}

/* cards: every st.container(border=True) becomes a white rounded card */
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div[data-testid="stVerticalBlock"]),
div[data-testid="stVerticalBlockBorderWrapper"] {{
    background: {CARD}; border: none !important; border-radius: 16px;
    box-shadow: 0 2px 14px rgba(30,30,44,.06); }}
div[data-testid="stLayoutWrapper"] > div[data-testid="stVerticalBlock"][class*="border"],
.st-key-card, [class*="st-key-card"] {{
    background: {CARD}; border: none !important; border-radius: 16px;
    box-shadow: 0 2px 14px rgba(30,30,44,.06); padding: 18px 20px 8px 20px; }}
.card-title {{ font-size: 16px; font-weight: 600; color: {INK}; margin: 0; }}
.card-sub {{ font-size: 12.5px; color: {TEXT_MUTED}; margin: 2px 0 4px 0; line-height: 1.4; }}

/* dark highlight card */
.dark-card {{ background: {INK}; color: #fff; border-radius: 16px; padding: 20px 22px; height: 100%;
              box-shadow: 0 6px 22px rgba(30,30,44,.22); }}
.dark-card .t {{ font-size: 16px; font-weight: 600; margin-bottom: 14px; }}
.dark-card .l {{ font-size: 12px; color: #B9BCCB; }}
.dark-card .v {{ font-size: 34px; font-weight: 700; color: {ORANGE}; line-height: 1.15; }}
.dark-card .row {{ display: flex; gap: 26px; margin-top: 14px; }}
.dark-card .row .v2 {{ font-size: 20px; font-weight: 700; color: #fff; }}

/* small insight list */
.insight {{ border-left: 3px solid {ORANGE}; background: {PEACH}; border-radius: 8px; padding: 10px 14px;
            font-size: 13px; color: {INK}; margin: 6px 0; }}
.footer {{ color: {TEXT_MUTED}; font-size: 12px; margin-top: 18px; }}

/* widgets */
div[data-baseweb="select"] > div {{ border-radius: 10px; }}
span[data-baseweb="tag"] {{ background: {PEACH} !important; color: {ORANGE_DARK} !important; }}
span[data-baseweb="tag"] span {{ color: {ORANGE_DARK} !important; }}
</style>
"""


def inject_css():
    import streamlit as st
    st.markdown(CSS, unsafe_allow_html=True)


# HTML helpers ----
def page_header(title, subtitle, chips=()):
    import streamlit as st
    chip_html = "".join(f'<span class="chip">{c}</span>' for c in chips)
    st.markdown(f'<div class="page-title">{title}</div><div class="page-sub">{subtitle}</div>'
                f'<div style="margin-bottom:14px">{chip_html}</div>', unsafe_allow_html=True)


def kpi_strip(items):
    """items: list of dicts with label, value, delta (text or None), good (True/False/None), note."""
    import streamlit as st
    cells = []
    for k in items:
        d = k.get("delta")
        if d is None:
            delta_html = f'<div class="kpi-delta flat">{k.get("note", "")}</div>'
        else:
            cls = {True: "up", False: "down", None: "flat"}[k.get("good")]
            delta_html = f'<div class="kpi-delta {cls}">{d} <span class="note">{k.get("note", "")}</span></div>'
        cells.append(f'<div class="kpi"><div class="kpi-label">{k["label"]}</div>'
                     f'<div class="kpi-value">{k["value"]}</div>{delta_html}</div>')
    st.markdown(f'<div class="kpi-strip">{"".join(cells)}</div>', unsafe_allow_html=True)


def card_title(title, subtitle=None):
    import streamlit as st
    sub = f'<div class="card-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(f'<div class="card-title">{title}</div>{sub}', unsafe_allow_html=True)
    _last_title.update(title=title, sub=subtitle)


def chart(fig, height=330, width=1100):
    import streamlit as st
    fig.update_layout(height=height)
    st.plotly_chart(fig, width="stretch", config=GRAPH_CONFIG, theme=None)
    if os.environ.get("LUMORA_EXPORT_DIR") and _last_title["title"]:
        export_png(fig, height, width)
    _last_title.update(title=None, sub=None)


# PNG export ----
# export_figures.py sets LUMORA_EXPORT_DIR and LUMORA_EXPORT_PAGE, then every chart
# with a card title is also saved as a PNG (title and subtitle drawn on the image)
_last_title = {"title": None, "sub": None}


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:50]


def export_png(fig, height, width=1100):
    folder = Path(os.environ["LUMORA_EXPORT_DIR"])
    folder.mkdir(parents=True, exist_ok=True)
    title, sub = _last_title["title"], _last_title["sub"]
    if sub:   # slicer notes only make sense inside the app
        sub = " · ".join(p for p in sub.split(" · ") if "slicer" not in p) or None
    f = go.Figure(fig)
    top = 84 if sub else 60
    m = f.layout.margin
    f.update_layout(
        title=dict(text=f"<b>{title}</b>" + (f"<br><span style='font-size:13px;color:{TEXT_MUTED}'>{sub}</span>" if sub else ""),
                   x=0.02, xanchor="left", xref="container", y=1, yanchor="top", yref="container",
                   pad=dict(t=20), font=dict(size=18, color=INK)),
        paper_bgcolor=CARD, plot_bgcolor=CARD, width=width, height=height + top + 10,
        margin=dict(l=(m.l or 10) + 20, r=(m.r or 10) + 20, t=(m.t or 10) + top, b=(m.b or 10) + 20),
        legend=dict(y=1.0, yanchor="bottom"),
    )
    page = os.environ.get("LUMORA_EXPORT_PAGE", "chart")
    n = len(list(folder.glob(f"{page}_*.png"))) + 1
    f.write_image(folder / f"{page}_{n:02d}_{_slug(title)}.png", scale=2)


def footer():
    import streamlit as st
    st.markdown(f'<p class="footer">{SOURCE} Built with Python (pandas, Plotly, Streamlit).</p>',
                unsafe_allow_html=True)


# Number formats ----
def eur(x, dec=0):
    if abs(x) >= 1e6:
        return f"€{x / 1e6:,.2f}M"
    if abs(x) >= 1e4:
        return f"€{x / 1e3:,.1f}k"
    return f"€{x:,.{dec}f}"


def change(cur, prev, kind="pct", higher_is_better=True):
    """Delta text and good/bad flag for this period vs the one before."""
    if prev is None or cur is None or prev != prev or cur != cur or (kind == "pct" and prev == 0):
        return None, None
    diff = cur - prev
    if abs(diff) < 1e-12:
        return "● 0.0%", None
    arrow = "▲" if diff > 0 else "▼"
    good = (diff > 0) == higher_is_better
    if kind == "pct":
        return f"{arrow} {diff / abs(prev):+.1%}", good
    if kind == "pp":
        return f"{arrow} {diff * 100:+.1f} pp", good
    return f"{arrow} {diff:+.2f}", good


def card(name):
    """White rounded card (styled by the st-key-card CSS rule)."""
    import streamlit as st
    return st.container(key=f"card_{name}")


def dark_card(title, value_label, value, rows):
    """Navy highlight card: one big number and a row of smaller ones [(label, value), ...]."""
    import streamlit as st
    row_html = "".join(f'<div><div class="l">{l}</div><div class="v2">{v}</div></div>' for l, v in rows)
    st.markdown(f'<div class="dark-card"><div class="t">{title}</div><div class="l">{value_label}</div>'
                f'<div class="v">{value}</div><div class="row">{row_html}</div></div>', unsafe_allow_html=True)


def ring(value, label, color=ORANGE, sub=None):
    """Small donut showing one share (0-1), like the 'Total visitors' ring in the reference."""
    fig = go.Figure(go.Pie(values=[value, 1 - value], hole=0.78, sort=False, direction="clockwise",
                           marker=dict(colors=[color, GRID]), textinfo="none", hoverinfo="skip"))
    fig.update_layout(showlegend=False, margin=dict(l=0, r=0, t=0, b=0), height=110,
                      annotations=[dict(text=f"<b>{value:.0%}</b>", showarrow=False, font=dict(size=17, color=INK))])
    return fig
