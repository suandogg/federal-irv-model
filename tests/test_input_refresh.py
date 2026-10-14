from pathlib import Path
from streamlit.testing.v1 import AppTest
import streamlit as st
import SRC.live_sheet_sync as live_sync
import SRC.forecast_ui as forecast_ui


def test_house_refresh_invalidates_forecast_loader_and_results(monkeypatch):
    st.cache_data.clear()
    calls=[]
    def sync(_secrets):
        calls.append(len(calls)+1)
        return {'ok':True,'synced':27,'errors':[],'skipped':[], 'message':f'Synced revision {calls[-1]}'}
    monkeypatch.setattr(live_sync,'sync_inputs_from_google_sheet',sync)
    monkeypatch.setattr(forecast_ui,'sync_inputs_from_google_sheet',sync)
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=60).run()
    app.segmented_control[0].set_value('Forecast').run()
    assert not app.exception
    first_revision=len(calls)
    app.session_state['forecast_result']={'old':'result'}
    app.session_state['forecast_signature']='old'
    app.session_state['forecast_comparison']='old'
    app.segmented_control[0].set_value('House').run()
    next(b for b in app.button if b.label=='Refresh Google Sheet inputs').click().run()
    assert not app.exception
    assert 'forecast_result' not in app.session_state
    assert 'forecast_comparison' not in app.session_state
    app.segmented_control[0].set_value('Forecast').run()
    assert not app.exception
    # A single shared sync updates both views after a refresh in House.
    assert len(calls)>=first_revision+1
    assert any(f'Synced revision {len(calls)}' in c.value for c in app.caption)
    st.cache_data.clear()


def test_sync_downloads_both_forecast_settings_tabs(monkeypatch,tmp_path):
    import pandas as pd
    from types import SimpleNamespace
    from SRC.forecast_params import parameter_table,load_forecast_params
    table=parameter_table();table.loc[table.Parameter=='SEED','Value']=123
    forecast_values=[table.columns.tolist()]+table.values.tolist()
    display_values=[['Section','Parameter','Value','Explanation'],['Forecast','FORECAST_TITLE','Changed from Sheet','Presentation only']]
    tabs=[('FORECAST PARAMS','FORECAST PARAMS.csv'),('DISPLAY PARAMS','DISPLAY PARAMS.csv')]
    requested=[]
    def batch(ranges):
        requested.extend(ranges)
        return {'valueRanges':[{'values':forecast_values},{'values':display_values}]}
    sheet=SimpleNamespace(worksheets=lambda:[SimpleNamespace(title=t) for t,_ in tabs],values_batch_get=batch)
    monkeypatch.setattr(live_sync,'DATA_DIR',tmp_path)
    monkeypatch.setattr(live_sync,'load_manifest',lambda:tabs)
    monkeypatch.setattr(live_sync,'resolve_sheet_id',lambda _:'testing-workbook')
    monkeypatch.setattr(live_sync,'resolve_credentials',lambda _:object())
    monkeypatch.setattr(live_sync.gspread,'authorize',lambda _:SimpleNamespace(open_by_key=lambda _:sheet))
    status=live_sync.sync_inputs_from_google_sheet()
    assert status['ok'] and status['synced']==2
    assert requested==["'FORECAST PARAMS'","'DISPLAY PARAMS'"]
    assert load_forecast_params(tmp_path/'FORECAST PARAMS.csv')[0]['SEED']==123
    assert pd.read_csv(tmp_path/'DISPLAY PARAMS.csv').Value.iloc[0]=='Changed from Sheet'
