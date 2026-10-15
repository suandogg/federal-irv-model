import csv
from pathlib import Path
import pandas as pd
from streamlit.testing.v1 import AppTest
from SRC.display_params import defaults,parameter_rows,load_display_params


def test_display_schema_validation_and_existing_colour_alias(tmp_path):
    rows=parameter_rows()
    for row in rows[1:]:
        if row[1]=='TITLE_FONT_PX':row[2]='nan'
        if row[1]=='PARTY_ORDER':row[2]='ALP,ALP'
    rows.append(['Parties','COLOUR_ALP','#123456','','colour','','Old alias'])
    path=tmp_path/'display.csv'
    with path.open('w',newline='') as f:csv.writer(f).writerows(rows)
    settings,warnings=load_display_params(path)
    assert settings['TITLE_FONT_PX']==defaults()['TITLE_FONT_PX']
    assert settings['PARTY_ORDER']==defaults()['PARTY_ORDER']
    assert settings['ALP_COLOUR']==defaults()['ALP_COLOUR'] # alias duplicates canonical -> safe default
    assert len(warnings)>=3
    assert defaults()['SEAT_AXIS_MAX']==150


def test_presentation_modes_and_roster_majority():
    script='''
import pandas as pd
import streamlit as st
from SRC.display_params import defaults
from SRC.presentation import apply_theme,table,party_summary,seat_intervals,event_bars,seat_histogram
s=defaults();s['ALP_LABEL']='Custom Labor';s['ALP_COLOUR']='#123456';s['TABLE_ROW_HEIGHT_PX']=42
st.session_state['_display_settings']=s
apply_theme(s)
summary=pd.DataFrame({'Party':['ALP','LNP'],'Average':[90.,60.],'Median seats':[90,60],'Lower seats':[80,50],'Upper seats':[100,70],'25th percentile':[85,55],'75th percentile':[95,65]})
table(party_summary(summary,s))
seat_intervals(summary,s,150)
event_bars(pd.DataFrame({'Event':['ALP majority','Hung parliament'],'Probability (%)':[75.,25.]}),s)
seat_histogram(pd.DataFrame({'ALP':[90,91],'LNP':[60,59],'GRN':[0,0],'ON':[0,0],'IND':[0,0],'OTH':[0,0]}),s,150)
'''
    app=AppTest.from_string(script,default_timeout=30).run()
    assert not app.exception
    assert 'Custom Labor' in app.dataframe[0].value.Party.tolist()


def test_display_changes_do_not_mutate_summary():
    from SRC.presentation import party_summary
    frame=pd.DataFrame({'Party':['ALP','LNP'],'Average':[90.,60.]})
    original=frame.copy(deep=True)
    settings=defaults();settings['ALP_LABEL']='Different';settings['PARTY_ORDER']='ALP,LNP,GRN,ON,IND,OTH'
    out=party_summary(frame,settings)
    pd.testing.assert_frame_equal(frame,original)
    assert out.Party.tolist()==['Different',settings['LNP_LABEL']]


def test_complete_schema_loads_without_warnings():
    settings,warnings=load_display_params()
    assert not warnings
    assert settings['COLOUR_PARTY_CELLS'] is True
    assert len(settings)==74


def test_sorted_party_labels_keep_their_colours_and_swing_styles(monkeypatch):
    import SRC.presentation as presentation
    from SRC.constants import PARTIES
    settings=defaults()
    settings['PARTY_ORDER']='LNP,ALP,ON,GRN,IND,OTH'
    frame=pd.DataFrame({'Party':[settings[p+'_LABEL'] for p in PARTIES],
                        'Swing %':[.3,-.3,-.1,-.2,-.4,.6]})
    original=frame.copy(deep=True)
    styled=frame.style.map(lambda v:'font-weight: bold',subset=['Party']).format({'Swing %':'{:.2f}'})
    monkeypatch.setattr(presentation.st,'dataframe',lambda data,*args,**kwargs:data)
    result=presentation.table(styled,settings=settings)
    result._compute()
    for row,party in enumerate(settings['PARTY_ORDER'].split(',')):
        assert result.data.iloc[row]['Party']==settings[party+'_LABEL']
        assert ('background-color',settings[party+'_COLOUR']) in result.ctx[(row,0)]
        value=result.data.iloc[row]['Swing %']
        assert ('color',settings['POSITIVE'] if value>0 else settings['NEGATIVE']) in result.ctx[(row,1)]
    pd.testing.assert_frame_equal(frame,original)
    assert styled.index.equals(original.index)
