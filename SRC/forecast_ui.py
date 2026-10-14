import json
from pathlib import Path
import altair as alt
import pandas as pd
import streamlit as st
from .constants import PARTIES, PARTY_COLOURS
from .forecast_params import load_forecast_params, parameter_table
from .forecast_engine import fingerprint, run_forecast, uncertainty_profile
from .candidate_irv import load_candidate_irv_evidence
from .live_sheet_sync import sync_inputs_from_google_sheet
from .input_refresh import refresh_model_inputs
from .loaders import (load_seat_metadata,load_preference_matrices,load_params,
    load_partisan_vote_index,load_baseline_results_by_seat,load_baseline_primary_by_state)

DEFAULT_TARGETS = dict(zip(PARTIES,[34.56,31.82,12.2,6.4,7.27,7.75]))


def display_settings():
    defaults={'FORECAST_TITLE':'Federal House forecast — testing','PROBABILITY_DECIMALS':'1',
              'SHOW_FORECAST_SEAT_TABLE':'true',**{f'COLOUR_{p}':PARTY_COLOURS[p]['bg'] for p in PARTIES}}
    path=Path(__file__).resolve().parents[1]/'data/raw/DISPLAY PARAMS.csv'
    if path.exists():
        raw=pd.read_csv(path).fillna('')
        for _,row in raw.iterrows():
            key=str(row.get('Parameter','')); value=str(row.get('Value',''))
            valid=(key=='FORECAST_TITLE' and bool(value)) or (key=='PROBABILITY_DECIMALS' and value in ['0','1','2']) or (key=='SHOW_FORECAST_SEAT_TABLE' and value.lower() in ['true','false'])
            if key.startswith('COLOUR_'):
                import re
                valid=bool(re.fullmatch('#[0-9a-fA-F]{6}',value))
            if key in defaults and valid: defaults[key]=value
            else: st.warning(f'Invalid display setting {key}; using default.')
    return defaults


@st.cache_data(show_spinner='Loading federal testing inputs')
def load_inputs():
    try: secrets=st.secrets.to_dict()
    except Exception: secrets={}
    status=sync_inputs_from_google_sheet(secrets)
    seats=load_seat_metadata(); params=load_params()
    return (seats,load_preference_matrices(),params,load_partisan_vote_index(params),
            load_baseline_results_by_seat(),load_baseline_primary_by_state(),load_candidate_irv_evidence(),status)


def render_forecast():
    if st.sidebar.button('Refresh Google Sheet inputs'):
        refresh_model_inputs(); st.rerun()
    seats,matrices,params,pvi,baseline_results,baseline_primary,evidence,status=load_inputs()
    display=display_settings()
    st.title(display['FORECAST_TITLE'])
    st.warning('Experimental conditional scenario probabilities. Uncertainty settings are provisional; this is not a polling-based election forecast. House only.')
    st.caption(status['message'] if status.get('ok') and status.get('synced') else 'Using committed CSV inputs: '+status['message'])
    if status.get('errors') or status.get('skipped'): st.warning('Some live tabs unavailable; see input status below. Available local inputs retained.')
    targets={}
    for col,party in zip(st.columns(len(PARTIES)),PARTIES):
        targets[party]=col.number_input(party,0.,100.,DEFAULT_TARGETS[party],.1,key='primary_'+party)
    if sum(targets.values())<=0: st.error('Enter a positive primary total.'); return
    st.caption(f'Primary total {sum(targets.values()):.2f}% (normalised to 100). {len(seats)} seats; majority {len(seats)//2+1}. LNP includes Liberals and Nationals.')
    calibration=st.checkbox('Apply supported-AEC calibration',True,key='forecast_calibration')
    try: settings,source=load_forecast_params()
    except ValueError as exc: st.error(str(exc)); return
    st.caption(source)
    with st.expander('Settings, methodology and input status'):
        st.dataframe(parameter_table(settings),hide_index=True)
        st.write('Edit column C in FORECAST PARAMS. PARAMS remains the central deterministic model. DISPLAY PARAMS changes presentation only. Refresh inputs after Sheet edits.')
        st.write('National errors are projected to 100%; state/territory and seat errors preserve the production builder’s equal-seat totals and structural zeros. Full production counting includes candidate-level independents. Preference noise follows central source selection. Central model parameters and candidate roster stay fixed.')
        st.write('Preference scales: exact-seat/candidate and perfect AEC evidence; pooled/projected/shrunk evidence; other matrix/ideology/assumed flows. Widths are not calibrated from sample sizes.')
        st.write('Government events overlap and are seat arithmetic. ALP support routes are OR-counted once; independents are not assumed to agree to support. Tied LNP–ON leadership is reported separately.')
        st.json(status); st.json(params)
    inputs=(seats,matrices,params,pvi,baseline_results,baseline_primary,evidence,targets,settings,calibration,status)
    signature=fingerprint(*inputs)
    if st.session_state.get('forecast_signature')!=signature:
        st.session_state.pop('forecast_result',None); st.session_state.pop('forecast_comparison',None)
    if st.button('Run House forecast',type='primary'):
        st.session_state.pop('forecast_result',None)
        st.session_state.pop('forecast_comparison',None)
        bar=st.progress(0.)
        try:
            result=run_forecast(*inputs[:9],calibration,bar.progress,status)
            st.session_state.forecast_result=result; st.session_state.forecast_signature=signature
        except Exception as exc: st.error(f'Forecast failed; no partial results published: {exc}')
        bar.empty()
    result=st.session_state.get('forecast_result')
    if result is None: st.info('Choose central primaries, then run the forecast.'); return
    parliament,seat_tab,details=st.tabs(['Parliament','Seat probabilities','Run details'])
    with parliament:
        st.dataframe(result['summary'].style.format({'Average':'{:.2f}'}),hide_index=True)
        st.caption('Unrounded averages total the House. Medians and interval endpoints are calculated separately and need not add to the House. Lower/upper quantiles follow FORECAST PARAMS.')
        colours=alt.Scale(domain=PARTIES,range=[display[f'COLOUR_{p}'] for p in PARTIES])
        chart=alt.Chart(result['summary']).encode(y=alt.Y('Party:N',sort=PARTIES),color=alt.Color('Party:N',scale=colours,legend=None))
        intervals=chart.mark_rule(strokeWidth=3).encode(x=alt.X('Lower:Q',title='Seats',scale=alt.Scale(domain=[0,len(seats)],nice=False)),x2='Upper:Q')
        middle=chart.mark_rule(strokeWidth=9).encode(x='Q25:Q',x2='Q75:Q')
        dot=chart.mark_point(filled=True,size=80).encode(x='Average:Q',tooltip=list(result['summary'].columns))
        line=alt.Chart(pd.DataFrame({'Majority':[len(seats)//2+1]})).mark_rule(strokeDash=[4,4]).encode(x='Majority:Q')
        st.altair_chart(intervals+middle+dot+line,width='stretch')
        st.caption('Thin line: lower–upper interval. Thick line: middle 50%. Dot: average seats. Dashed line: majority.')
        st.dataframe(result['events'],hide_index=True)
        st.bar_chart(result['events'].set_index('Event')['Probability %'],horizontal=True)
        if st.button('Compare narrower / current / wider uncertainty'):
            try:
                profiles=[uncertainty_profile(settings,m) for m in [.5,1.5]]
                comparison=[]
                for label,profile in zip(['Narrower','Wider'],profiles):
                    bar=st.progress(0.,text=label)
                    alternative=run_forecast(seats,matrices,params,pvi,baseline_results,baseline_primary,evidence,targets,profile,calibration,bar.progress,status)
                    comparison.append(alternative['summary'].assign(Profile=label)); bar.empty()
                comparison.append(result['summary'].assign(Profile='Current'))
                st.session_state.forecast_comparison=pd.concat(comparison,ignore_index=True)
            except Exception as exc: st.error(str(exc))
        if 'forecast_comparison' in st.session_state: st.dataframe(st.session_state.forecast_comparison,hide_index=True)
    with seat_tab:
        table=result['seats']; selected=st.selectbox('Seat',table.division.tolist())
        st.dataframe(table[table.division==selected],hide_index=True)
        if display['SHOW_FORECAST_SEAT_TABLE'].lower()=='true':
            decimals=int(display['PROBABILITY_DECIMALS'])
            st.dataframe(table.style.format({c:f'{{:.{decimals}f}}' for c in table if 'win %' in c or 'MCSE' in c}),hide_index=True)
        st.caption('MCSE measures simulation noise only. Median winning margin is winner share above 50%, not the winner–runner-up gap. Zero wins does not mean impossible.')
    with details:
        st.dataframe(result['primaries'].describe(percentiles=[.05,.25,.5,.75,.95]))
        st.json(result['manifest'])
        for key,label in [('seats','seat_probabilities'),('counts','party_seat_draws'),('primaries','national_primary_draws'),('winners','seat_winner_draws')]:
            st.download_button('Download '+label,result[key].to_csv(index=False),label+'.csv','text/csv')
        st.download_button('Download reproduction manifest',json.dumps(result['manifest'],indent=2,default=str),'forecast_manifest.json','application/json')


if __name__ != 'SRC.forecast_ui': render_forecast()
