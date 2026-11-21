"""
Script:   theme.py
Purpose:  Shared colours and chart style for the notebooks (matplotlib / seaborn).
          Same light palette as the Streamlit dashboard (streamlit_app/lumora_theme.py):
          white charts, orange main series, navy second series, peach for comparisons.
              from theme import *
              apply_theme()
"""
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap

# Colours ----
BG = "#FFFFFF"           # figure and chart background
PAGE = "#F6F3EF"         # warm light grey (dashboard page background)
PEACH = "#FAEEDB"        # soft highlight
ORANGE = "#EE8A4C"       # main series, highlights
ORANGE_DARK = "#C9672C"
ORANGE_LIGHT = "#F7C6A3" # comparison / previous period
INK = "#1E1E2C"          # titles
INK_2 = "#2B2D42"        # second series (navy)
BLUE = "#4F86C6"
TEAL = "#2E9E8F"
SAND = "#D9B13B"
GREY = "#9AA0AE"         # neutral / "other" / baselines
GRID = "#EFEAE4"         # grid lines
LINE = "#E7E1DA"         # axes lines
TEXT = "#1E1E2C"
TEXT_MUTED = "#7A7F8C"
RED = "#E5484D"          # only for bad news
GREEN = "#2BA471"        # only for good news

CATEGORICAL = [ORANGE, INK_2, BLUE, TEAL, SAND, GREY, ORANGE_LIGHT, "#6C6F86"]
YEAR_COLORS = {2021: "#F9DCC5", 2022: "#F5C19B", 2023: "#F1A673", 2024: "#EE8A4C", 2025: INK_2}
CHANNEL_GROUP_COLORS = {"Direct": ORANGE, "OTA": INK_2, "Corporate": BLUE, "Wholesale": GREY}

CMAP_ORANGE = LinearSegmentedColormap.from_list("lumora_orange", ["#FFF8F1", "#F9D6B9", ORANGE, "#8A3D12"])
CMAP_DIVERGING = LinearSegmentedColormap.from_list("lumora_div", [INK_2, "#F3F1EE", ORANGE])

# old names from the black and gold theme, kept so older code still runs
BLACK, PANEL, PANEL_2, WHITE = BG, BG, PAGE, BG
GOLD, GOLD_DARK, GOLD_LIGHT, AMBER = ORANGE, INK_2, ORANGE_LIGHT, ORANGE_DARK
GREY_DARK = GREY
CMAP_GOLD = CMAP_ORANGE

SOURCE = "Source: Lumora Hotels (simulated data), 2021-2025"


def _pick_font():
    installed = set(font_manager.get_font_names())
    for name in ["Segoe UI", "Inter", "Helvetica Neue", "Arial", "DejaVu Sans"]:
        if name in installed:
            return name
    return "DejaVu Sans"


def apply_theme():
    """Light matplotlib style for every chart in the project."""
    mpl.rcParams.update({
        "font.family": _pick_font(),
        "font.size": 10,
        "figure.facecolor": BG,
        "axes.facecolor": BG,
        "savefig.facecolor": BG,
        "axes.edgecolor": LINE,
        "axes.labelcolor": TEXT_MUTED,
        "axes.titlecolor": TEXT,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.titlepad": 12,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "axes.axisbelow": True,
        "axes.prop_cycle": mpl.cycler(color=CATEGORICAL),
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": TEXT_MUTED,
        "ytick.color": TEXT_MUTED,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "text.color": TEXT,
        "legend.frameon": False,
        "legend.labelcolor": TEXT_MUTED,
        "patch.linewidth": 0,
        "figure.dpi": 110,
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
    })


def title(ax, text, subtitle=None):
    """Bold title with an optional grey subtitle under it."""
    ax.set_title(text, loc="left", pad=24 if subtitle else 12)
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, color=TEXT_MUTED, fontsize=9, va="bottom")


def source_note(fig, text=SOURCE):
    fig.text(0.01, -0.02, text, color=GREY, fontsize=8, ha="left")


def label_bars(ax, fmt="{:,.0f}", color=TEXT_MUTED, inside=False, fontsize=8):
    """Write the value on top of each vertical bar."""
    for p in ax.patches:
        v = p.get_height()
        ax.annotate(fmt.format(v), (p.get_x() + p.get_width() / 2, p.get_height()),
                    ha="center", va="top" if inside else "bottom", fontsize=fontsize, color=color,
                    xytext=(0, -3 if inside else 2), textcoords="offset points")


def eur_m(x, _=None):
    return f"€{x / 1e6:,.1f}M"


def eur_k(x, _=None):
    return f"€{x / 1e3:,.0f}k"


def pct(x, _=None):
    return f"{x:.0%}"


def fmt_axis(ax, axis="y", kind="pct"):
    f = {"pct": pct, "eur_m": eur_m, "eur_k": eur_k}[kind]
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(mtick.FuncFormatter(f))


def save_fig(fig, name, folder=None):
    from config import FIG_DIR
    folder = folder or FIG_DIR
    folder.mkdir(parents=True, exist_ok=True)
    fig.savefig(folder / f"{name}.png")
    return folder / f"{name}.png"
