"""Simulation-only perturbations; central preference selection remains unchanged."""
import math

def perturb(weights, origin, basis, seat_class, params):
    shocks = params.get('_forecast_shocks')
    if not shocks:
        return weights
    if basis in {'seat_pref_flow', 'aec_perfect', 'exact_candidate_transfer'}:
        source = 'EXACT'
    elif 'shrunk' in basis or 'posterior' in basis or basis == 'projected_candidate_transfer':
        source = 'POOLED'
    else:
        source = 'GENERIC'
    settings = shocks['settings']
    origin = 'IND' if origin.startswith('IND:') else origin
    values = {}
    for entity, value in weights.items():
        party = 'IND' if entity.startswith('IND:') else entity
        tilt = settings[f'PREF_{source}_LOG_SD'] * shocks['origin'][origin][party]
        if party == 'ON':
            tilt += settings['PREF_CLASS_ON_LOG_SD'] * shocks['class_on'].get(seat_class, 0)
        values[entity] = value * math.exp(tilt)
    total = sum(values.values())
    if total <= 0:
        raise ValueError('Preference perturbation has no positive continuing flow')
    return {key:value/total for key,value in values.items()}
