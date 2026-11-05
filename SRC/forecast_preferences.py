"""Simulation-only perturbations; central preference selection remains unchanged."""
import math

def perturb(weights, origin, basis, seat_class, params, seat_evidence_weight=None, pooled_evidence_seats=0):
    shocks = params.get('_forecast_shocks')
    if not shocks:
        return weights
    full_weight_seat = basis == 'seat_pref_flow_shrunk' and seat_evidence_weight == 1
    if full_weight_seat or basis in {'seat_pref_flow', 'aec_perfect', 'exact_candidate_transfer'}:
        source = 'EXACT'
    elif 'shrunk' in basis or 'posterior' in basis or basis == 'projected_candidate_transfer':
        source = 'POOLED'
    else:
        source = 'GENERIC'
    settings = shocks['settings']
    width = settings[f'PREF_{source}_LOG_SD']
    sparse_width = shocks.get('sparse_pool_width')
    if source == 'POOLED' and sparse_width is not None and 1 <= (pooled_evidence_seats or 0) <= 3:
        width = sparse_width
    origin = 'IND' if origin.startswith('IND:') else origin
    values = {}
    for entity, value in weights.items():
        party = 'IND' if entity.startswith('IND:') else entity
        tilt = width * shocks['origin'][origin][party]
        if party == 'ON':
            tilt += settings['PREF_CLASS_ON_LOG_SD'] * shocks['class_on'].get(seat_class, 0)
        values[entity] = value * math.exp(tilt)
    total = sum(values.values())
    if total <= 0:
        raise ValueError('Preference perturbation has no positive continuing flow')
    return {key:value/total for key,value in values.items()}
