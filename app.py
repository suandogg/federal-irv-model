import runpy
from pathlib import Path

import streamlit as st


ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="Federal Election Model", layout="wide")

view = st.segmented_control(
    "Model view",
    options=["House", "Senate", "Dashboard"],
    default="House",
    key="model_view",
)

scripts = {
    "House": "house_app.py",
    "Senate": "senate_app.py",
    "Dashboard": "dashboard_app.py",
}
runpy.run_path(str(ROOT / scripts[view]), run_name=f"__{view.lower()}_view__")
