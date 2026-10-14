import runpy
from pathlib import Path

import streamlit as st


ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="Federal Election Model — testing", layout="wide")

from SRC.runtime_inputs import load_sync_status
from SRC.display_params import load_display_params
from SRC.presentation import apply_theme
from SRC.input_refresh import refresh_model_inputs

st.session_state['_current_sync_status'] = load_sync_status()
display, display_warnings = load_display_params()
st.session_state['_display_settings'] = display
apply_theme(display)
for warning in display_warnings: st.sidebar.warning(warning)

labels = {'House':display['NAV_HOUSE'],'Forecast':display['NAV_FORECAST'],
          'Senate':display['NAV_SENATE'],'Dashboard':display['NAV_DASHBOARD']}
view = st.segmented_control('Model view',options=list(labels),format_func=labels.get,
                            default='House',key='model_view') or 'House'
if view in ('Senate','Dashboard'):
    if st.sidebar.button('Refresh Google Sheet inputs'):
        refresh_model_inputs(); st.rerun()
    status=st.session_state['_current_sync_status']
    st.sidebar.caption(status['message'] if status.get('synced') else 'Using committed CSV inputs: '+status['message'])

scripts = {
    "House": "house_app.py",
    "Forecast": "forecast_app.py",
    "Senate": "senate_app.py",
    "Dashboard": "dashboard_app.py",
}
runpy.run_path(str(ROOT / scripts[view]), run_name=f"__{view.lower()}_view__")
