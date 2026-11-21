"""
Script:   app.py
Purpose:  Lumora Hotels dashboard in Streamlit + Plotly (5 pages)
            1 Overview                  2 Demand & forecast
            3 Bookings & cancellations  4 Pricing & experiments
            5 Guests & reviews
          This file sets the page style, draws the sidebar (navigation + slicers for
          year, hotel, channel group and guest segment) and runs the chosen page.
          The KPI cards compare the selected year with the year before.
          The pages live in views/, data loading in lumora_data.py, colours in lumora_theme.py.
Input:    ../Data_clean/*.csv, ../output/tables/*.csv
Output:   local web app, run from the Lumora_Hotels/streamlit_app folder with
              streamlit run app.py
          and open http://localhost:8501
"""
import streamlit as st

import lumora_data as D
import lumora_theme as T

st.set_page_config(page_title="Lumora Hotels", page_icon="🏨", layout="wide",
                   initial_sidebar_state="expanded")
T.inject_css()
T.plotly_theme()
D.check_paths()
core = D.load_core()   # loads once, then cached for every page and rerun

# Navigation ----
pages = [
    st.Page("views/overview.py", title="Overview", icon=":material/dashboard:", default=True),
    st.Page("views/demand.py", title="Demand & forecast", icon=":material/calendar_month:"),
    st.Page("views/cancellations.py", title="Bookings & cancellations", icon=":material/event_busy:"),
    st.Page("views/pricing.py", title="Pricing & experiments", icon=":material/sell:"),
    st.Page("views/guests.py", title="Guests & reviews", icon=":material/reviews:"),
]

# own sidebar menu (brand on top, then the pages, then the slicers)
nav = st.navigation(pages, position="hidden")
with st.sidebar:
    st.markdown('<div class="side-brand">LUMORA<span>.</span></div>'
                '<div class="side-sub">Hotels · revenue dashboard</div>'
                '<div class="side-label">Dashboard</div>', unsafe_allow_html=True)
    for i, p in enumerate(pages):
        key = "navactive" if p.title == nav.title else f"navlink{i}"
        with st.container(key=key):
            st.page_link(p, label=p.title, icon=p.icon)

# Slicers ----
# keys are shared by every page, so a selection stays when you switch page
hotels = core["hotels"].sort_values("short_name")
hotel_names = dict(zip(hotels.hotel_id, hotels.short_name))

for k, v in {"f_year": 2025, "f_hotels": [], "f_groups": [], "f_segments": []}.items():
    st.session_state.setdefault(k, v)

with st.sidebar:
    st.markdown('<div class="side-label">Filters</div>', unsafe_allow_html=True)
    st.selectbox("Year", ["All years"] + D.YEARS[::-1], key="f_year",
                 help="KPI cards compare the selected year with the year before.")
    st.multiselect("Hotel", list(hotel_names), format_func=hotel_names.get, key="f_hotels",
                   placeholder="All hotels")
    st.multiselect("Channel group", D.CHANNEL_GROUPS, key="f_groups", placeholder="All channels")
    st.multiselect("Guest segment", D.SEGMENTS, key="f_segments", placeholder="All segments")

    def _reset():
        st.session_state.f_year = 2025
        for k in ["f_hotels", "f_groups", "f_segments"]:
            st.session_state[k] = []

    st.button("Reset filters", on_click=_reset, width="stretch")
    st.caption("Occupancy and RevPAR use the selected hotels' full capacity, so channel "
               "and segment filters show their share of it.")

nav.run()
