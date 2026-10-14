"""Invalidate all views together before reloading Google Sheet inputs."""
import streamlit as st


def refresh_model_inputs():
    # House and Forecast have different cached loaders. Clear both so switching
    # views cannot reuse data loaded before the user requested a refresh.
    st.cache_data.clear()
    for key in ('forecast_result', 'forecast_signature', 'forecast_comparison'):
        st.session_state.pop(key, None)
