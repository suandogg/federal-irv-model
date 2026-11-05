"""Conditional House simulations through the production federal engines."""
import copy
import hashlib
import pickle
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from .constants import PARTIES
from .forecast_params import validate
from .irv import apply_statewide_primary_adjustment, run_irv_all
from .candidate_irv import run_candidate_irv_all


def engine_source_hash():
    root = Path(__file__).resolve().parent
    return hashlib.sha256(b''.join(p.name.encode()+p.read_bytes() for p in sorted(root.glob('*.py')))).hexdigest()


def fingerprint(*inputs):
    return hashlib.sha256(pickle.dumps((engine_source_hash(),inputs),protocol=4)).hexdigest()


def uncertainty_profile(settings, multiplier):
    return validate({k:v*multiplier if '_SD' in k else v for k,v in settings.items()})


def count(seats, matrices, params, evidence, calibration=True):
    if float(params.get('scalars',{}).get('USE_CANDIDATE_LEVEL_IND_IRV',1)) >= .5:
        return run_candidate_irv_all(seats,matrices,params,evidence,calibration)[0]
    return run_irv_all(seats,matrices,params,calibration)[0]


def government_events(counts, house_size):
    majority = house_size//2+1
    joint = (counts.LNP+counts.ON>=majority)&(counts.LNP<majority)&(counts.ON<majority)
    events = {f'{p} majority':counts[p]>=majority for p in PARTIES}
    events.update({
        'ALP + GRN or IND arithmetic (ALP below majority)':(counts.ALP<majority)&((counts.ALP+counts.GRN>=majority)|(counts.ALP+counts.IND>=majority)),
        'LNP + ON arithmetic (LNP-led)':joint&(counts.LNP>counts.ON),
        'LNP + ON arithmetic (ON-led)':joint&(counts.ON>counts.LNP),
        'LNP + ON arithmetic (tied leadership)':joint&(counts.ON==counts.LNP),
        'Hung parliament':counts[PARTIES].max(axis=1)<majority,
        'Any party majority':counts[PARTIES].max(axis=1)>=majority,
        'Neither ALP+GRN nor LNP+ON reaches majority':(counts.ALP+counts.GRN<majority)&(counts.LNP+counts.ON<majority),
    })
    return events


def simplex(values, total=100.0):
    """Euclidean projection onto the non-negative simplex."""
    x = np.asarray(values,dtype=float)
    if not np.isfinite(x).all():
        raise ValueError('Primary shares must be finite')
    order = np.sort(x)[::-1]
    cumulative = np.cumsum(order)-total
    support = np.nonzero(order-cumulative/np.arange(1,len(x)+1)>0)[0]
    threshold = cumulative[support[-1]]/(support[-1]+1)
    return np.maximum(x-threshold,0)


def draw_targets(targets, settings, rng):
    centre = np.array([float(targets[p]) for p in PARTIES])
    if not np.isfinite(centre).all() or (centre<0).any() or centre.sum()<=0:
        raise ValueError('Central primaries must be finite, non-negative and have a positive total')
    centre = centre/centre.sum()*100
    sd = np.array([settings[f'NATIONAL_SD_{p}_PP'] for p in PARTIES])
    draw = simplex(centre+rng.normal(size=len(PARTIES))*sd)
    return dict(zip(PARTIES,draw))


def perturb_local_primaries(adjusted, settings, rng, *, concentration_rng=None, structured_rng=None, concentration_width=0):
    if not any((settings['REGION_PRIMARY_SD_PP'], settings['SEAT_PRIMARY_SD_PP'], concentration_width)):
        return adjusted.copy()
    base = adjusted[PARTIES].to_numpy(dtype=float)
    if (base<0).any() or not np.isfinite(base).all():
        raise ValueError('Invalid central seat primaries')
    rows = base.sum(axis=1)
    columns = base.sum(axis=0)
    region_names = sorted(adjusted.state.unique())
    regional = {region:rng.normal(0,settings['REGION_PRIMARY_SD_PP'],len(PARTIES))/100
                for region in region_names}
    if concentration_rng is None:
        shock = np.array([regional[region] for region in adjusted.state])
    else:
        # Replace state shocks with a national concentration shock per party.
        # Standardise each party's geography over its positive-support seats.
        # Keep the main RNG's draw sequence identical across trial modes.
        support = base > 0
        supported_seats = support.sum(axis=0).clip(min=1)
        mean = base.sum(axis=0) / supported_seats
        centred = np.where(support, base - mean, 0)
        spread = np.sqrt((centred ** 2).sum(axis=0) / supported_seats)
        pattern = np.divide(centred, spread, out=np.zeros_like(base), where=spread > 1e-12)
        concentration = concentration_rng.normal(0, settings['REGION_PRIMARY_SD_PP'] / 100, len(PARTIES))
        shock = pattern * concentration
    shock += rng.normal(0,settings['SEAT_PRIMARY_SD_PP']/100,base.shape)
    if structured_rng is not None:
        # Share regional variance across states and seat classes within each state.
        groups = list(zip(adjusted.state, adjusted.classification.fillna('').astype(str)))
        group_sd = settings['REGION_PRIMARY_SD_PP'] / (100 * np.sqrt(2))
        group_shocks = {
            group: structured_rng.normal(0, group_sd, len(PARTIES))
            for group in sorted(set(groups))
        }
        shock = np.array([regional[state] / np.sqrt(2) + group_shocks[group]
                          for state, group in zip(adjusted.state, groups)])
        shock += structured_rng.normal(0, settings['SEAT_PRIMARY_SD_PP'] / 100, base.shape)
        for index, coefficient in enumerate(structured_rng.normal(0, concentration_width, len(PARTIES))):
            active = base[:, index] > 0
            log_strength = np.log(base[active, index])
            if len(log_strength) < 2 or log_strength.std() <= 1e-12:
                continue
            power_delta = np.tanh(coefficient / log_strength.std())
            shock[active, index] += base[active, index] * np.expm1(
                power_delta * (log_strength - log_strength.mean())
            )
    perturbed = np.where(base>0, np.maximum(base+shock,1e-12),0)
    # Raking preserves the current draw's column totals and every seat total.
    # This does not turn the calculator's equal-seat primary convention into
    # a new turnout-weighted model. Structural zero candidates remain zero.
    for _ in range(2000):
        perturbed *= np.divide(columns,perturbed.sum(axis=0),out=np.zeros_like(columns),where=columns>0)
        perturbed *= (rows/perturbed.sum(axis=1))[:,None]
        if np.max(np.abs(perturbed.sum(axis=0)-columns))<1e-9:
            break
    else:
        raise ValueError('Local primary balancing did not converge; no partial forecast published')
    out = adjusted.copy()
    out[PARTIES] = perturbed
    return out



def run_forecast(seats, matrices, params, pvi, baseline_results, baseline_primary,
                 evidence, targets, settings, calibration=True, progress=None, sync_status=None,
                 *, concentration_trial=False, structured_width=None, sparse_pool_width=None):
    settings = validate(settings)
    for name, width in [('Concentration', structured_width), ('Sparse pool', sparse_pool_width)]:
        if width is not None and (not np.isfinite(width) or not 0 <= width <= 1):
            raise ValueError(f'{name} width must be between 0 and 1')
    if concentration_trial and structured_width is not None:
        raise ValueError('Select only one geographic concentration mode')
    keys = seats.division_key.astype(str).tolist()
    if not keys or len(set(keys)) != len(keys) or seats.state.isna().any():
        raise ValueError('House roster must have unique division keys and known states')
    if set(keys)-set(matrices):
        raise ValueError('Missing preference matrices for House roster')
    rng = np.random.default_rng(settings['SEED'])
    concentration_rng = (
        np.random.default_rng(np.random.SeedSequence([settings['SEED'], 1]))
        if concentration_trial else None
    )
    structured_rng = (
        np.random.default_rng(np.random.SeedSequence([settings['SEED'], 2]))
        if structured_width is not None else None
    )
    winners, margins, two_pp, counts, primaries = [], [], [], [], []
    primary_draws = []
    runners_up = []
    for draw in range(settings['SIMULATIONS']):
        national = draw_targets(targets,settings,rng)
        draw_params = copy.deepcopy(params)
        draw_params['_forecast_shocks'] = {
            'settings':settings,
            'sparse_pool_width':sparse_pool_width,
            'origin':{p:dict(zip(PARTIES,rng.normal(size=len(PARTIES)))) for p in PARTIES},
            'class_on':{c:float(rng.normal()) for c in sorted(set(seats.classification.fillna('').astype(str)))},
        } if sparse_pool_width or any(settings[k] for k in settings if k.startswith('PREF_')) else None
        adjusted = apply_statewide_primary_adjustment(seats,national,pvi,params=draw_params,
                    baseline_results_by_seat=baseline_results,baseline_primary_by_state=baseline_primary)
        adjusted = perturb_local_primaries(
            adjusted, settings, rng, concentration_rng=concentration_rng,
            structured_rng=structured_rng, concentration_width=structured_width or 0,
        )
        values = adjusted[PARTIES].to_numpy()
        if not np.isfinite(values).all() or (values<0).any() or not np.allclose(values.sum(axis=1),1):
            raise ValueError('Invalid simulated primaries')
        primary_draws.append(values * 100)
        result = count(adjusted,matrices,draw_params,evidence,calibration)
        if result.division_key.tolist()!=keys or not result.winner.isin(PARTIES).all():
            raise ValueError('Incomplete House draw; no partial results published')
        winners.append(result.winner.tolist())
        runners_up.append(result.runner_up.tolist())
        margins.append((result.winner_pct.to_numpy()-.5)*100)
        two_pp.append(result.ALP_2PP.to_numpy()*100)
        counts.append([int((result.winner==p).sum()) for p in PARTIES])
        primaries.append([national[p] for p in PARTIES])
        if progress: progress((draw+1)/settings['SIMULATIONS'])
    winners=np.array(winners); counts=pd.DataFrame(counts,columns=PARTIES)
    if not (counts.sum(axis=1)==len(keys)).all(): raise ValueError('Incomplete seat allocation')
    probabilities=seats[['division','division_key','state']].copy()
    for p in PARTIES:
        prob=(winners==p).mean(axis=0)
        probabilities[p+' win %']=prob*100
        probabilities[p+' MCSE pp']=100*np.sqrt(prob*(1-prob)/len(winners))
    finalist_records = []
    for key, seat_winners, seat_runners in zip(keys, winners.T, np.asarray(runners_up).T):
        pairs = pd.DataFrame({'winner': seat_winners, 'runner_up': seat_runners})
        pairs['final_pair'] = [
            '+'.join(sorted(filter(None, (winner, runner))))
            for winner, runner in zip(seat_winners, seat_runners)
        ]
        for pair, draws in pairs.groupby('final_pair', sort=True):
            for party, appearances in draws.winner.value_counts().items():
                finalist_records.append({
                    'division_key': key,
                    'final_pair': pair,
                    'winner': party,
                    'pair_draws': len(draws),
                    'pair_probability_pct': 100 * len(draws) / len(seat_winners),
                    'wins': appearances,
                    'win_given_pair_pct': 100 * appearances / len(draws),
                })
    probabilities['Median winning margin pp']=np.median(margins,axis=0)
    probabilities['Median ALP 2PP %']=np.median(two_pp,axis=0)
    probabilities['ALP–LNP 2PP SD (pp)'] = np.std(two_pp, axis=0)
    primary_sd = np.std(primary_draws, axis=0)
    for index, party in enumerate(PARTIES):
        probabilities[f'{party} primary SD (pp)'] = primary_sd[:, index]
    summary=pd.DataFrame({'Party':PARTIES,'Average':counts.mean().values,
        'Median':counts.quantile(.5,interpolation='nearest').values,
        'Lower':counts.quantile(settings['LOWER_QUANTILE'],interpolation='nearest').values,
        'Q25':counts.quantile(.25,interpolation='nearest').values,
        'Q75':counts.quantile(.75,interpolation='nearest').values,
        'Upper':counts.quantile(settings['UPPER_QUANTILE'],interpolation='nearest').values})
    events=pd.DataFrame([{'Event':label,'Probability %':float(event.mean()*100),
                         'MCSE pp':float(100*np.sqrt(event.mean()*(1-event.mean())/len(counts)))}
                        for label,event in government_events(counts,len(keys)).items()])
    return dict(summary=summary,events=events,seats=probabilities,counts=counts,
        finalist_pairs=pd.DataFrame(finalist_records),
        primaries=pd.DataFrame(primaries,columns=PARTIES),winners=pd.DataFrame(winners,columns=keys),
        manifest={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'source_hash':engine_source_hash(),
                  'fingerprint':fingerprint(seats,matrices,params,pvi,baseline_results,baseline_primary,evidence,targets,settings,calibration,concentration_trial,structured_width,sparse_pool_width),
                  'targets':targets,'settings':settings,'model_params':params,'house_size':len(keys),
                  'majority':len(keys)//2+1,'calibration':calibration,'sync_status':sync_status,
                  'geography_mode': ('bounded concentration and state/class blend' if structured_rng is not None
                                     else 'concentration trial' if concentration_trial else 'state shocks'),
                  'structured_concentration_width': structured_width,
                  'sparse_pool_log_sd': sparse_pool_width,
                  'mean_division_2pp_sd_pp': float(probabilities['ALP–LNP 2PP SD (pp)'].mean()),
                  'method':'Federal production primary builder and full candidate-aware IRV; equal-seat aggregation',
                  'caveats':['Conditional on entered primaries; no polling model','Uncertainty widths provisional; central model parameters fixed',
                             'Structural zeros preserved relative to each production primary draw',
                             'Events overlap; independent support not predicted; LNP groups Liberals and Nationals',
                             'Projection and clipping may shift means; no fitted covariance','Zero simulated wins does not imply impossibility']})
