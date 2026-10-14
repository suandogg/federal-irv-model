"""One cached sync shared by navigation and all model views."""
import os
import streamlit as st
from . import live_sheet_sync

@st.cache_data(show_spinner='Refreshing Google Sheet inputs...')
def load_sync_status():
    if os.environ.get('FEDERAL_IRV_APP_MODE','').lower()=='legacy':
        return {'ok':True,'synced':0,'skipped':[],'errors':[],'message':'Frozen legacy inputs; live sync disabled'}
    try: secrets=st.secrets.to_dict()
    except Exception: secrets={}
    return live_sheet_sync.sync_inputs_from_google_sheet(secrets)
