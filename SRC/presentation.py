"""Streamlit presentation helpers; consume outputs, never modify model inputs."""
import html
import math
import textwrap
import hashlib
import pandas as pd
import streamlit as st
from SRC.display_params import defaults, PARTIES

FONTS = {'sans':'Arial, Helvetica, sans-serif','serif':'Georgia, Times, serif',
         'mono':'ui-monospace, Menlo, monospace'}
PRESETS = {
    'warm':dict(BACKGROUND='#f2eedf',SURFACE='#ffffff',SIDEBAR_BACKGROUND='#e8e3d5',TEXT='#26251f',MUTED_TEXT='#757166',BORDER='#dcd6c8',ACCENT='#2563eb'),
    'light':dict(BACKGROUND='#f7f8fa',SURFACE='#ffffff',SIDEBAR_BACKGROUND='#eceff3',TEXT='#172033',MUTED_TEXT='#637085',BORDER='#dce2eb',ACCENT='#2563eb'),
    'dark':dict(BACKGROUND='#101318',SURFACE='#1d232d',SIDEBAR_BACKGROUND='#171c24',TEXT='#f0f3f8',MUTED_TEXT='#a5afbe',BORDER='#394252',ACCENT='#74a7ff')}


def effective(settings):
    return settings | PRESETS.get(settings['THEME'],{})


def apply_theme(settings):
    s = effective(settings)
    css = f'''
    :root {{color-scheme: {'dark' if s['THEME']=='dark' else 'light'};}}
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{background:{s['BACKGROUND']};color:{s['TEXT']};}}
    [data-testid="stSidebar"] {{background:{s['SIDEBAR_BACKGROUND']};color:{s['TEXT']};}}
    [data-testid="stMainBlockContainer"] {{max-width:{s['PAGE_MAX_WIDTH_PX']}px;padding-top:{s['TOP_PADDING_REM']}rem;padding-bottom:{s['BOTTOM_PADDING_REM']}rem;}}
    [data-testid="stVerticalBlock"] {{gap:{s['SECTION_GAP_REM']}rem;}}
    [data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"], [data-testid="stCaptionContainer"] {{font-family:{FONTS[s['BODY_FONT']]};color:{s['TEXT']};font-size:{s['BODY_FONT_PX']}px;}}
    [data-testid="stMarkdownContainer"] h1 {{font-family:{FONTS[s['HEADING_FONT']]};font-size:{s['TITLE_FONT_PX']}px;}}
    [data-testid="stMarkdownContainer"] h2, [data-testid="stMarkdownContainer"] h3 {{font-family:{FONTS[s['HEADING_FONT']]};font-size:{s['SECTION_FONT_PX']}px;}}
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{color:{s['MUTED_TEXT']};font-size:{s['CAPTION_FONT_PX']}px;}}
    [data-testid="stMetric"] {{background:{s['SURFACE']};border:1px solid {s['BORDER']};border-radius:{s['CARD_RADIUS_PX']}px;padding:{s['CARD_PADDING_PX']}px;box-shadow:{'0 3px 15px #00000012' if s['CARD_SHADOW'] else 'none'};}}
    [data-testid="stMetricValue"] {{font-size:{s['METRIC_FONT_PX']}px;color:{s['TEXT']};}}
    [data-testid="stMetricLabel"] {{color:{s['MUTED_TEXT']};}}
    [data-testid="stMetricDelta"][data-color="normal"] {{color:{s['POSITIVE']};}}
    [data-testid="stMetricDelta"][data-color="inverse"] {{color:{s['NEGATIVE']};}}
    .stButton button, .stDownloadButton button, .stLinkButton a {{border-radius:{s['CARD_RADIUS_PX']}px;background:{s['SURFACE']};color:{s['TEXT']};border-color:{s['BORDER']};}}
    .stButton button[kind="primary"] {{background:{s['ACCENT']};color:white;}}
    [data-baseweb="input"], [data-baseweb="select"] > div {{background:{s['SURFACE']};color:{s['TEXT']};}}
    [data-testid="stNumberInputContainer"], [data-testid="stNumberInputContainer"] [data-baseweb="base-input"], [data-testid="stNumberInputField"], [data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"] {{background:{s['SURFACE']} !important;color:{s['TEXT']} !important;}}
    [data-testid="stNumberInputContainer"] {{border:1px solid {s['BORDER']};}}
    input {{color:{s['TEXT']} !important;-webkit-text-fill-color:{s['TEXT']} !important;}}
    '''
    st.html('<style>'+css+'</style>')


def table(data,*args,settings=None,probabilities=False,**kwargs):
    s = settings or st.session_state.get('_display_settings',defaults())
    frame = data if isinstance(data,pd.DataFrame) else getattr(data,'data',None)
    if frame is not None and 'Party' in frame.columns:
        order=s['PARTY_ORDER'].split(',')
        ranks={value:i for i,p in enumerate(order) for value in (p,s[p+'_LABEL'])}
        frame=frame.iloc[sorted(range(len(frame)),key=lambda i:ranks.get(frame.iloc[i]['Party'],99))].copy()
        if isinstance(data,pd.DataFrame): data=frame
        else:
            data=data._copy(deepcopy=True)
            data.data=frame
    if frame is not None:
        swing_columns=[c for c in frame if ('Swing' in str(c) or 'Change' in str(c)) and pd.api.types.is_numeric_dtype(frame[c])]
        if swing_columns:
            data=data.style if isinstance(data,pd.DataFrame) else data
            data=data.map(lambda v: f'color: {s["POSITIVE"] if v>0 else s["NEGATIVE"]}' if pd.notna(v) and v!=0 else '',subset=swing_columns)
    kwargs.setdefault('row_height',s['TABLE_ROW_HEIGHT_PX'])
    kwargs.setdefault('height',min(s['TABLE_MAX_HEIGHT_PX'],(len(frame)+1)*s['TABLE_ROW_HEIGHT_PX']+4) if frame is not None else s['TABLE_MAX_HEIGHT_PX'])
    kwargs['hide_index'] = not s['TABLE_SHOW_INDEX']
    kwargs.setdefault('width','stretch')
    config = dict(kwargs.get('column_config') or {})
    if frame is not None:
        for column in frame.columns:
            if pd.api.types.is_numeric_dtype(frame[column]) and ('%' in str(column) or 'percent' in str(column).lower() or 'error (pp)' in str(column) or 'MCSE' in str(column) or 'margin pp' in str(column)):
                digits = s['PROBABILITY_DECIMALS'] if probabilities or 'win (%)' in str(column) or 'win %' in str(column) or 'probability' in str(column).lower() or 'majority (%)' in str(column).lower() else s['PERCENT_DECIMALS']
                config[column] = st.column_config.NumberColumn(format=f'%.{digits}f')
        kwargs['column_config'] = config
        if 'Party' in frame.columns and s['COLOUR_PARTY_CELLS']:
            # Summary tables contain configured display labels, whereas other
            # tables may retain party codes. Both use the same live palette.
            styles = {}
            for party in PARTIES:
                style = f'background-color: {s[party+"_COLOUR"]}; color: {s[party+"_TEXT_COLOUR"]}'
                styles[party] = style
                styles[s[party+'_LABEL']] = style
            styled = data.style if isinstance(data,pd.DataFrame) else data
            data = styled.map(lambda value: styles.get(value,''),subset=['Party'])
    return st.dataframe(data,*args,**kwargs)


def party_summary(frame,settings):
    result = frame.copy()
    if 'Party' in result:
        order = settings['PARTY_ORDER'].split(',')
        result['_order'] = result.Party.map({p:i for i,p in enumerate(order)}).fillna(99)
        result = result.sort_values('_order').drop(columns='_order')
        result['Party'] = result.Party.map(lambda p:settings.get(p+'_LABEL',p))
    return result


def headline_metric(label,value,delta,settings):
    s = effective(settings)
    extra = ''
    if delta is not None:
        colour = s['POSITIVE'] if delta>=0 else s['NEGATIVE']
        extra = f'<div style="color:{colour};font-size:{s["CAPTION_FONT_PX"]}px">{delta:+.{s["PERCENT_DECIMALS"]}f} pp</div>'
    st.html(f'<div style="background:{s["SURFACE"]};color:{s["TEXT"]};border:1px solid {s["BORDER"]};border-radius:{s["CARD_RADIUS_PX"]}px;padding:{s["CARD_PADDING_PX"]}px;box-shadow:{"0 3px 15px #00000012" if s["CARD_SHADOW"] else "none"}"><div style="color:{s["MUTED_TEXT"]};font-family:{FONTS[s["BODY_FONT"]]};font-size:{s["CAPTION_FONT_PX"]}px">{html.escape(label)}</div><div style="font-family:{FONTS[s["BODY_FONT"]]};font-size:{s["METRIC_FONT_PX"]}px;font-weight:600;overflow-wrap:anywhere">{html.escape(value)}</div>{extra}</div>')


def _card(svg,settings,title):
    s = effective(settings)
    key = 'display_chart_'+hashlib.sha256(title.encode()).hexdigest()[:12]
    st.html(f'<style>.st-key-{key} {{background:{s["SURFACE"]};border:1px solid {s["BORDER"]};border-radius:{s["CARD_RADIUS_PX"]}px;padding:{s["CARD_PADDING_PX"]}px;overflow-x:auto;box-shadow:{"0 3px 15px #00000012" if s["CARD_SHADOW"] else "none"};}}</style>')
    with st.container(key=key):
        st.html(f'<div style="font:600 {s["SECTION_FONT_PX"]}px {FONTS[s["HEADING_FONT"]]};color:{s["TEXT"]}">{html.escape(title)}</div>')
        # Streamlit's HTML sanitizer deliberately removes inline SVG. Its image
        # component safely renders our generated SVG without enabling scripts.
        st.image(svg,width='stretch')


def seat_intervals(frame,settings,house_size):
    s = effective(settings)
    frame = frame.set_index('Party')
    parties = [p for p in s['PARTY_ORDER'].split(',') if p in frame.index and (s['SHOW_ZERO_SEAT_PARTIES'] or frame.loc[p,'Upper seats']>0)]
    if not parties: return
    maximum = max(s['SEAT_AXIS_MAX'],math.ceil(max(float(frame.loc[p,'Upper seats']) for p in parties)/5)*5)
    row_height = s['CHART_ROW_HEIGHT_PX']
    top,height,left,right = 48,48+len(parties)*row_height+40,230,970
    x = lambda v:left+float(v)/maximum*(right-left)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Seat count intervals, middle 50 percent and median" viewBox="0 0 1000 {height}" style="width:100%;min-width:650px;font-family:{FONTS[s["BODY_FONT"]]};font-size:{s["CHART_LABEL_FONT_PX"]}px;fill:{s["TEXT"]}">']
    for tick in range(0,maximum+1,5):
        if s['CHART_SHOW_GRID']: parts.append(f'<line x1="{x(tick)}" x2="{x(tick)}" y1="{top-15}" y2="{height-35}" stroke="{s["BORDER"]}"/>')
        parts.append(f'<text x="{x(tick)}" y="{height-10}" text-anchor="middle" fill="{s["MUTED_TEXT"]}">{tick}</text>')
    if s['CHART_SHOW_MAJORITY_LINE']:
        parts.append(f'<line x1="{x(house_size//2+1)}" x2="{x(house_size//2+1)}" y1="25" y2="{height-35}" stroke="{s["TEXT"]}" stroke-dasharray="3 4"/><text x="{x(house_size//2+1)}" y="17" text-anchor="middle">{house_size//2+1} for majority</text>')
    for i,p in enumerate(parties):
        row = frame.loc[p]; y = top+i*row_height+row_height/2
        colour = s[p+'_COLOUR']
        parts.append(f'<text x="{left-18}" y="{y+5}" text-anchor="end" fill="{colour}">{html.escape(s[p+"_LABEL"])}</text>')
        for lower,upper,width,opacity in [('Lower seats','Upper seats',25,s['CHART_OUTER_OPACITY']),('25th percentile','75th percentile',12,s['CHART_INNER_OPACITY'])]:
            parts.append(f'<line x1="{x(row[lower])}" x2="{x(row[upper])}" y1="{y}" y2="{y}" stroke="{colour}" stroke-width="{width}" stroke-linecap="round" opacity="{opacity}"/>')
        parts.append(f'<line x1="{x(row["Median seats"])}" x2="{x(row["Median seats"])}" y1="{y-16}" y2="{y+16}" stroke="{s["TEXT"]}" stroke-width="2"/>')
        if s['CHART_SHOW_VALUES']: parts.append(f'<text x="{x(row["Median seats"])}" y="{y-21}" text-anchor="middle">{int(row["Median seats"])}</text>')
    _card(''.join(parts)+'</svg>',s,s['SEAT_CHART_TITLE'])


def event_bars(frame,settings):
    s = effective(settings); row_height = s['CHART_ROW_HEIGHT_PX']
    height = len(frame)*row_height+50
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Overlapping parliamentary event probabilities" viewBox="0 0 1100 {height}" style="width:100%;min-width:750px;font-family:{FONTS[s["BODY_FONT"]]};font-size:{s["CHART_LABEL_FONT_PX"]}px;fill:{s["TEXT"]}">']
    for i,row in frame.reset_index(drop=True).iterrows():
        label = str(row['Event']); value = float(row['Probability (%)']); y=i*row_height+25
        if 'Hung parliament' in frame['Event'].values:
            divider_index = list(frame['Event']).index('Hung parliament')
            if i == divider_index:
                parts.append(f'<line x1="5" x2="1090" y1="{y-row_height/2}" y2="{y-row_height/2}" stroke="{s["BORDER"]}" stroke-width="2"/>')
            if i >= divider_index:
                y += 25
        colour = next((s[p+'_COLOUR'] for p in PARTIES if label.startswith(p)),s['MUTED_TEXT'])
        lines = textwrap.wrap(label,width=max(40,int(620/(s['CHART_LABEL_FONT_PX']*.58))))
        for line_index,line in enumerate(lines):
            parts.append(f'<text x="5" y="{y+5+(line_index-(len(lines)-1)/2)*(s["CHART_LABEL_FONT_PX"]+2)}">{html.escape(line)}</text>')
        parts.append(f'<rect x="650" y="{y-9}" width="350" height="18" rx="9" fill="{s["BORDER"]}"/><rect x="650" y="{y-9}" width="{3.5*value}" height="18" rx="9" fill="{colour}"/>')
        if s['CHART_SHOW_VALUES']: parts.append(f'<text x="1020" y="{y+5}">{value:.{s["PROBABILITY_DECIMALS"]}f}%</text>')
    _card(''.join(parts)+'</svg>',s,s['GOVERNMENT_CHART_TITLE'])


def seat_histogram(counts, settings, house_size):
    import altair as alt
    s = effective(settings)
    parties = [p for p in s['PARTY_ORDER'].split(',') if s['SHOW_ZERO_SEAT_PARTIES'] or counts[p].max()>0]
    rows = counts[parties].melt(var_name='Party',value_name='Seats')
    rows['Label'] = rows.Party.map({p:s[p+'_LABEL'] for p in parties})
    labels = [s[p+'_LABEL'] for p in parties]
    chart = alt.Chart(rows).mark_bar(opacity=s['CHART_INNER_OPACITY']).encode(
        x=alt.X('Seats:Q',bin=alt.Bin(step=1),scale=alt.Scale(domain=[0,max(s['SEAT_AXIS_MAX'],int(rows.Seats.max()))],nice=False),axis=alt.Axis(grid=s['CHART_SHOW_GRID'])),
        y=alt.Y('count():Q',title='Simulated elections',axis=alt.Axis(grid=s['CHART_SHOW_GRID'])),
        color=alt.Color('Label:N',scale=alt.Scale(domain=labels,range=[s[p+'_COLOUR'] for p in parties]),legend=alt.Legend(title=None)),
        tooltip=['Label:N','Seats:Q','count():Q']).properties(height=s['CHART_HEIGHT_PX'],title=s['SEAT_CHART_TITLE'])
    if s['CHART_SHOW_MAJORITY_LINE']:
        line=alt.Chart(pd.DataFrame({'Majority':[house_size//2+1]})).mark_rule(strokeDash=[4,4],color=s['TEXT']).encode(x='Majority:Q')
        chart=chart+line
    chart=chart.configure(background=s['SURFACE']).configure_axis(labelColor=s['TEXT'],titleColor=s['TEXT'],labelFontSize=s['CHART_LABEL_FONT_PX'],gridColor=s['BORDER']).configure_legend(labelColor=s['TEXT'],labelFontSize=s['CHART_LABEL_FONT_PX']).configure_title(color=s['TEXT'],fontSize=s['SECTION_FONT_PX'])
    st.altair_chart(chart,width='stretch')
