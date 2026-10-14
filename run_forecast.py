"""Reproduce the app's default conditional scenario using the committed snapshot."""
from pathlib import Path
import json,time
from SRC.loaders import (load_seat_metadata,load_params,load_preference_matrices,load_partisan_vote_index,load_baseline_results_by_seat,load_baseline_primary_by_state)
from SRC.candidate_irv import load_candidate_irv_evidence
from SRC.forecast_engine import run_forecast
from SRC.forecast_params import load_forecast_params
from SRC.constants import PARTIES

if __name__=='__main__':
    root=Path(__file__).resolve().parent;out=root/'reports/forecast';out.mkdir(parents=True,exist_ok=True)
    seats=load_seat_metadata();params=load_params();settings,_=load_forecast_params()
    start=time.perf_counter()
    snapshot={'ok':False,'synced':0,'message':'Using committed federal repository inputs; not a fresh live sync'}
    result=run_forecast(seats,load_preference_matrices(),params,load_partisan_vote_index(params),
        load_baseline_results_by_seat(),load_baseline_primary_by_state(),load_candidate_irv_evidence(),
        dict(zip(PARTIES,[34.56,31.82,12.2,6.4,7.27,7.75])),settings,sync_status=snapshot)
    for key in ['summary','events','seats','counts','primaries','winners']:result[key].to_csv(out/f'{key}.csv',index=False)
    (out/'manifest.json').write_text(json.dumps(result['manifest'],indent=2,default=str))
    print(result['summary'].to_string(index=False));print(f'Completed {settings["SIMULATIONS"]} draws in {time.perf_counter()-start:.2f}s')
