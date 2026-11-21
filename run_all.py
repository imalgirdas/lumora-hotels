"""
Script:   run_all.py
Purpose:  Runs the whole Lumora Hotels project in order:
            1 clean the raw data          (src/clean.py)
            2 fit the models              (src/models.py -> output/tables)
            3 export the dashboard charts (streamlit_app/export_figures.py -> output/figures_app)
          With --notebooks it also runs the four notebooks.
Input:    Data/*.csv
Output:   Data_clean/, output/tables/, output/figures_app/
Run:      python run_all.py              (about two minutes)
          python run_all.py --notebooks  (about five minutes)
          then start the dashboard with  streamlit run streamlit_app/app.py
"""
import subprocess
import sys
import time
from pathlib import Path
 
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
 
from clean import clean_all          # noqa: E402
from load import load_clean          # noqa: E402
from models import run_all_models    # noqa: E402
 
APP_DIR = ROOT / "streamlit_app"
 
 
def run_notebooks():
    for nb in sorted((ROOT / "notebooks").glob("0*.ipynb")):
        print(f"Running {nb.name} ...")
        subprocess.run([sys.executable, "-m", "jupyter", "nbconvert", "--to", "notebook", "--execute",
                        "--inplace", "--ExecutePreprocessor.timeout=1200", str(nb)], check=True, cwd=nb.parent)
 
 
def export_figures():
    """Save every chart of the Streamlit app as a PNG (needs kaleido and Chrome)."""
    script = APP_DIR / "export_figures.py"
    if not script.exists():
        print("   streamlit_app/export_figures.py not found, skipped")
        return
    result = subprocess.run([sys.executable, str(script)], cwd=APP_DIR)
    if result.returncode != 0:
        # the charts are a nice extra, so a missing Chrome / kaleido should not stop the run
        print("   Figure export failed (is kaleido installed? try: plotly_get_chrome). The app still works.")
 
 
def main():
    t0 = time.time()
    print("Step 1/3  Cleaning raw data")
    clean_all()
    print(f"\nStep 2/3  Models ({time.time() - t0:.0f}s)")
    clean = load_clean()
    run_all_models(clean)           # writes output/tables, which the Streamlit app reads
    print(f"\nStep 3/3  Dashboard charts ({time.time() - t0:.0f}s)")
    export_figures()
    if "--notebooks" in sys.argv:
        run_notebooks()
    print(f"\nDone in {time.time() - t0:.0f}s. Start the dashboard with:")
    print("    cd streamlit_app")
    print("    streamlit run app.py")
    print("and open http://localhost:8501 in a browser.")
 
 
if __name__ == "__main__":
    main()
 