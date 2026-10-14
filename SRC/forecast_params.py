"""Strict, sheet-controlled settings. All uncertainty defaults are provisional."""
from pathlib import Path
import math
import pandas as pd
from SRC.loaders import RAW_DIR
from SRC.constants import PARTIES

# Section, parameter, default, units, explanation, lower bound, upper bound.
SPECS = [
    ('Run','SIMULATIONS',200,'draws','Preview count; increase after assumptions are reviewed. Not a calibrated forecast.',1,5000),
    ('Run','SEED',20261014,'integer','Fixed seed makes repeated runs reproducible with the same inputs.',0,4294967295),
    ('Reporting','LOWER_QUANTILE',.05,'fraction','Lower endpoint of the displayed central seat-count interval.',0,.49),
    ('Reporting','UPPER_QUANTILE',.95,'fraction','Upper endpoint of the displayed central seat-count interval.',.51,1),
    ('Local votes','REGION_PRIMARY_SD_PP',.75,'primary pp SD','Shared party shock within each of the states and territories; rebalanced to drawn equal-seat national totals.',0,10),
    ('Local votes','SEAT_PRIMARY_SD_PP',1.5,'primary pp SD','Independent seat/party residual; rebalanced to drawn equal-seat national totals. Includes unmodelled candidate variation.',0,15),
    ('Preferences','PREF_EXACT_LOG_SD',.05,'log-weight SD','Observed exact seat/candidate evidence; provisional transport uncertainty.',0,1),
    ('Preferences','PREF_POOLED_LOG_SD',.1,'log-weight SD','Pooled, projected or shrunk federal evidence; provisional.',0,1),
    ('Preferences','PREF_GENERIC_LOG_SD',.2,'log-weight SD','Matrix, ideology, special assumptions and fallback flows; provisional.',0,1),
    ('Preferences','PREF_CLASS_ON_LOG_SD',.1,'log-weight SD','ON recipient shock shared within a seat classification.',0,1),
]
for party, sd in zip(PARTIES, [2,2,1,3,1,1]):
    SPECS.append(('National votes',f'NATIONAL_SD_{party}_PP',sd,'primary pp SD',
                  'Provisional independent party error before projecting all six shares to a non-negative total of 100; not an empirically fitted polling covariance.',0,15))


def defaults():
    return {spec[1]:spec[2] for spec in SPECS}


def parameter_table(values=None):
    values = defaults() if values is None else values
    return pd.DataFrame([{'Section':s,'Parameter':p,'Value':values[p],'Units':u,'Explanation':e}
                         for s,p,_,u,e,_,_ in SPECS])


def validate(values):
    unknown = set(values)-set(defaults())
    if unknown:
        raise ValueError('Unknown FORECAST PARAMS: '+', '.join(sorted(unknown)))
    result = defaults()
    result.update(values)
    for _, key, _, _, _, low, high in SPECS:
        try:
            value = float(result[key])
        except (TypeError, ValueError) as exc:
            raise ValueError(f'{key} must be numeric') from exc
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f'{key} must be between {low} and {high}')
        if key in ('SIMULATIONS','SEED'):
            if value != int(value):
                raise ValueError(f'{key} must be an integer')
            value = int(value)
        result[key] = value
    return result


def load_forecast_params(path=None):
    path = Path(path) if path else RAW_DIR/'FORECAST PARAMS.csv'
    if not path.exists():
        return defaults(), 'Provisional built-in defaults (FORECAST PARAMS file missing)'
    raw = pd.read_csv(path)
    if not {'Parameter','Value'}.issubset(raw.columns):
        raise ValueError('FORECAST PARAMS needs Parameter and Value columns')
    raw = raw.dropna(subset=['Parameter'])
    raw['Parameter'] = raw.Parameter.astype(str).str.strip()
    raw = raw[raw.Parameter.ne('')]
    if raw.Parameter.duplicated().any():
        raise ValueError('Duplicate FORECAST PARAMS parameter')
    missing = set(defaults())-set(raw.Parameter)
    if missing:
        raise ValueError('Missing FORECAST PARAMS: '+', '.join(sorted(missing)))
    return validate(dict(zip(raw.Parameter,raw.Value))), 'Loaded FORECAST PARAMS (provisional uncertainty settings)'
