"""
Script:   export_figures.py
Purpose:  Save every chart of the Streamlit dashboard as a PNG (light peach / navy
          style, title and subtitle on the image) for the README and reports.
          Replaces the old black and gold figures in output/figures.
          Runs each page headless with Streamlit's AppTest, so the PNGs are exactly
          the charts you see in the app.
Input:    the app (app.py, views/), ../Data_clean, ../output/tables
          optional:  --year 2025   (default: all years)
                     --out  ..\\output\\figures_app   (default)
Output:   ../output/figures_app/<page>_<nr>_<chart>.png  (2x resolution)
Run:      cd Lumora_Hotels\\streamlit_app
          python export_figures.py
          (needs kaleido and Google Chrome; if kaleido cannot find Chrome run  plotly_get_chrome  once)
"""
import argparse
import os
from pathlib import Path

from streamlit.testing.v1 import AppTest

HERE = Path(__file__).resolve().parent
PAGES = {"1_overview": "views/overview.py", "2_demand": "views/demand.py",
         "3_cancellations": "views/cancellations.py", "4_pricing": "views/pricing.py",
         "5_guests": "views/guests.py"}

parser = argparse.ArgumentParser()
parser.add_argument("--year", default="All years")
parser.add_argument("--out", default=str(HERE.parent / "output" / "figures_app"))
args = parser.parse_args()
year = args.year if args.year == "All years" else int(args.year)

out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)
for old in out.glob("*.png"):          # start clean so the numbering stays the same
    old.unlink()
os.environ["LUMORA_EXPORT_DIR"] = str(out)

for page, path in PAGES.items():
    os.environ["LUMORA_EXPORT_PAGE"] = page
    at = AppTest.from_file(str(HERE / "app.py"), default_timeout=600)
    at.session_state["f_year"] = year
    at.switch_page(path)
    at.run()
    if at.exception:
        raise SystemExit(f"{page} failed: {at.exception[0].value}")
    print(f"{page:16s} {len(list(out.glob(page + '_*.png')))} charts")

print(f"Saved {len(list(out.glob('*.png')))} PNGs to {out}")
