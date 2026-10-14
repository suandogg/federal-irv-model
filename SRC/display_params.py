"""Validated, presentation-only controls. Never imported by calculation modules."""
import csv
import math
import re
from pathlib import Path

PARTIES = ('ALP','LNP','GRN','ON','IND','OTH')
SPECS = []


def spec(section,key,default,kind,allowed,description):
    SPECS.append(dict(Section=section,Parameter=key,Default=default,Type=kind,
                      Allowed=allowed,Explanation=description))


spec('Theme','THEME','custom','choice','custom|warm|light|dark','Preset colours; custom uses the colour rows below. Does not change party colours.')
for key,default,description in [
    ('BACKGROUND','#f2eedf','Main page background'),('SURFACE','#ffffff','Cards, chart and input background'),
    ('SIDEBAR_BACKGROUND','#e8e3d5','Sidebar background'),('TEXT','#26251f','Main text colour'),
    ('MUTED_TEXT','#757166','Captions and secondary text'),('BORDER','#dcd6c8','Card edges and chart grid'),
    ('ACCENT','#2563eb','Buttons and active controls'),('POSITIVE','#138553','Positive display changes'),
    ('NEGATIVE','#cc3344','Negative display changes')]:
    spec('Theme',key,default,'colour','#RRGGBB',description)
spec('Typography','BODY_FONT','sans','choice','sans|serif|mono','System font family; no external downloads')
spec('Typography','HEADING_FONT','serif','choice','sans|serif|mono','Page and section heading font')
spec('Typography','BODY_FONT_PX',16,'number','12:24','Body text size; Streamlit canvas tables have their own font')
spec('Typography','TITLE_FONT_PX',40,'number','24:64','Main page title size')
spec('Typography','SECTION_FONT_PX',27,'number','18:40','Section heading size')
spec('Typography','CAPTION_FONT_PX',14,'number','11:20','Caption size; warnings remain visible')
spec('Typography','METRIC_FONT_PX',32,'number','20:52','Dashboard headline value size')
spec('Layout','PAGE_MAX_WIDTH_PX',1450,'number','800:2200','Maximum content width; automatically shrinks on smaller screens')
spec('Layout','TOP_PADDING_REM',2,'number','0:8','Space above main content')
spec('Layout','BOTTOM_PADDING_REM',3,'number','0:10','Space below main content')
spec('Layout','SECTION_GAP_REM',1.2,'number','0.3:3','Vertical spacing between content blocks')
spec('Layout','CARD_RADIUS_PX',12,'number','0:32','Corners of metric cards, charts and buttons')
spec('Layout','CARD_PADDING_PX',20,'number','8:40','Padding inside custom charts and metric cards')
spec('Layout','CARD_SHADOW',False,'boolean','TRUE|FALSE','Subtle shadows on metric and chart cards')
spec('Layout','DASHBOARD_CHAMBERS_SIDE_BY_SIDE',True,'boolean','TRUE|FALSE','FALSE stacks House and Senate summaries vertically')
for key,value,description in [
    ('APP_TITLE','Federal election model — testing','Main page title'),
    ('SENATE_TITLE','Federal Senate Model','Senate view heading'),
    ('DASHBOARD_TITLE','Election dashboard','Dashboard heading'),
    ('FORECAST_TITLE','Lower-house forecast · experimental','Forecast heading; provisional warning remains'),
    ('NAV_DASHBOARD','Dashboard','Sidebar navigation label'),
    ('NAV_HOUSE','House','Sidebar navigation label'),
    ('NAV_SENATE','Senate','Sidebar navigation label'),
    ('NAV_FORECAST','Forecast (experimental)','Sidebar navigation label'),
    ('SEAT_CHART_TITLE','House seat totals','Forecast interval chart heading'),
    ('GOVERNMENT_CHART_TITLE','Parliamentary outcomes','Forecast event chart heading')]:
    spec('Labels',key,value,'text','1–120 characters',description)
for party,label,colour in [('ALP','Labor','#df3347'),('LNP','Coalition','#2865ce'),
                           ('GRN','Greens','#22a653'),('ON','One Nation','#ff7900'),
                           ('IND','Independents','#159f9c'),('OTH','Other','#8d7ba5')]:
    spec('Parties',party+'_LABEL',label,'text','1–120 characters','Display name only; internal party code stays '+party)
    spec('Parties',party+'_COLOUR',colour,'colour','#RRGGBB','Party colour in tables, charts and seat summaries')
    spec('Parties',party+'_TEXT_COLOUR','#ffffff','colour','#RRGGBB','Text colour on filled party cells; choose good contrast')
spec('Parties','PARTY_ORDER','LNP,ALP,ON,GRN,IND,OTH','order','All six codes once, comma separated','Order in custom summary tables and charts; no effect on elimination ties')
spec('Tables','TABLE_ROW_HEIGHT_PX',35,'number','24:64','Row height for app result tables')
spec('Tables','TABLE_MAX_HEIGHT_PX',560,'number','180:1600','Maximum height before tables scroll; small tables stay compact')
spec('Tables','TABLE_SHOW_INDEX',False,'boolean','TRUE|FALSE','Show dataframe index where the table does not explicitly require it')
spec('Tables','PERCENT_DECIMALS',2,'number','0:3','Displayed percentages; raw/downloaded numbers unchanged')
spec('Tables','PROBABILITY_DECIMALS',1,'number','0:3','Forecast win/event percentages')
spec('Tables','COLOUR_PARTY_CELLS',True,'boolean','TRUE|FALSE','Filled party cells in existing styled House tables')
spec('Charts','SEAT_CHART_MODE','intervals','choice','intervals|histogram|both|table','Forecast seat-count presentation; intervals show outer range, middle 50% and median')
spec('Charts','GOVERNMENT_CHART_MODE','both','choice','bars|table|both','Forecast government events are overlapping bars, never a pie')
spec('Charts','SHOW_FORECAST_SEAT_TABLE',True,'boolean','TRUE|FALSE','Also show numerical seat distribution summary')
spec('Charts','SHOW_ZERO_SEAT_PARTIES',True,'boolean','TRUE|FALSE','FALSE hides parties whose upper interval is zero from seat summary charts/tables only')
spec('Charts','CHART_ROW_HEIGHT_PX',56,'number','36:90','Custom horizontal chart row spacing')
spec('Charts','CHART_LABEL_FONT_PX',16,'number','11:23','Custom chart label size')
spec('Charts','CHART_HEIGHT_PX',330,'number','200:800','Histogram height')
spec('Charts','CHART_OUTER_OPACITY',0.22,'number','0.05:0.6','Outer uncertainty band opacity')
spec('Charts','CHART_INNER_OPACITY',0.85,'number','0.3:1','Middle 50% uncertainty band opacity')
spec('Charts','CHART_SHOW_GRID',True,'boolean','TRUE|FALSE','Vertical guides in custom charts')
spec('Charts','CHART_SHOW_VALUES',True,'boolean','TRUE|FALSE','Median labels and probability values in custom charts')
spec('Charts','CHART_SHOW_MAJORITY_LINE',True,'boolean','TRUE|FALSE','Show the roster-derived House majority threshold; presentation cannot change it')
spec('Charts','SEAT_AXIS_MAX',150,'number','1:150','Requested seat-axis maximum; expands automatically if an interval exceeds it')
spec('Dashboard','SHOW_DASHBOARD_FORMATION_TABLE',True,'boolean','TRUE|FALSE','Show deterministic parliamentary arithmetic table')


def defaults():
    return {s['Parameter']:s['Default'] for s in SPECS}


def validate_one(s,value):
    kind = s['Type']
    value = str(value).strip()
    if kind=='boolean':
        if value.lower() not in ('true','false'): raise ValueError('use TRUE or FALSE')
        return value.lower()=='true'
    if kind=='colour':
        if not re.fullmatch(r'#[0-9a-fA-F]{6}',value): raise ValueError('use a six-digit hex colour, e.g. #DF3347')
        return value.lower()
    if kind=='number':
        number = float(value)
        lower,upper = map(float,s['Allowed'].split(':'))
        if not math.isfinite(number) or not lower<=number<=upper: raise ValueError('allowed range '+s['Allowed'])
        if isinstance(s['Default'],int) and not number.is_integer(): raise ValueError('use a whole number')
        return int(number) if isinstance(s['Default'],int) else number
    if kind=='choice' and value not in s['Allowed'].split('|'): raise ValueError('choose '+s['Allowed'])
    if kind=='order':
        codes = [p.strip() for p in value.split(',')]
        if len(codes)!=6 or set(codes)!=set(PARTIES): raise ValueError('include each of ALP,LNP,GRN,ON,IND,OTH once')
        return ','.join(codes)
    if not value or len(value)>120: raise ValueError('use 1–120 characters')
    return value


def load_display_params(path=None):
    settings = defaults()
    warnings = []
    path = Path(path) if path else Path(__file__).resolve().parents[1]/'data/raw/DISPLAY PARAMS.csv'
    if not path.exists(): return settings,['DISPLAY PARAMS is missing; using presentation defaults.']
    specs = {s['Parameter']:s for s in SPECS}
    try:
        with path.open(newline='',encoding='utf-8-sig') as handle:
            rows = list(csv.DictReader(handle))
        seen = set()
        for row in rows:
            key = row.get('Parameter','').strip()
            if key.startswith('COLOUR_'): key = key.removeprefix('COLOUR_')+'_COLOUR'
            if key not in specs:
                warnings.append('Unknown display setting: '+key)
                continue
            if key in seen:
                settings[key] = specs[key]['Default']
                warnings.append(key+': duplicate rows; using default.')
                continue
            seen.add(key)
            try: settings[key] = validate_one(specs[key],row.get('Value',''))
            except (ValueError,TypeError) as exc: warnings.append(key+': '+str(exc)+'; using default.')
        missing = set(specs)-seen
        if missing: warnings.append(f'{len(missing)} missing display settings use defaults.')
        nav = [settings[k] for k in ('NAV_DASHBOARD','NAV_HOUSE','NAV_SENATE','NAV_FORECAST')]
        if len(set(nav))!=4:
            for key in ('NAV_DASHBOARD','NAV_HOUSE','NAV_SENATE','NAV_FORECAST'): settings[key]=specs[key]['Default']
            warnings.append('Navigation labels must be unique; using defaults.')
    except (OSError,csv.Error) as exc:
        warnings.append('Display settings could not be read: '+str(exc))
    return settings,warnings


def parameter_rows():
    columns = ['Section','Parameter','Value','Default','Type','Allowed values','Explanation']
    return [columns]+[[s['Section'],s['Parameter'],s['Default'],s['Default'],s['Type'],s['Allowed'],s['Explanation']] for s in SPECS]
