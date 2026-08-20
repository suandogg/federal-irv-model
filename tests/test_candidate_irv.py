from SRC.constants import PARTIES
from SRC.candidate_irv import load_candidate_irv_evidence, run_candidate_irv_all
from SRC.irv import apply_statewide_primary_adjustment
from SRC.loaders import (
    load_baseline_primary_by_state,
    load_baseline_results_by_seat,
    load_params,
    load_partisan_vote_index,
    load_preference_matrices,
    load_seat_metadata,
)


def _inputs():
    return (
        load_seat_metadata(),
        load_baseline_results_by_seat(),
        load_baseline_primary_by_state(),
        load_params(),
        load_preference_matrices(),
        load_candidate_irv_evidence(),
    )


def test_candidate_engine_reconstructs_multi_independent_baseline_contests():
    seats, baseline, _, params, matrices, evidence = _inputs()
    indexed = baseline.set_index("division_key")
    for idx, row in seats.iterrows():
        if row["division_key"] not in indexed.index:
            continue
        for party in PARTIES:
            seats.at[idx, party] = indexed.at[row["division_key"], f"{party}_primary"] / 100.0

    results, _ = run_candidate_irv_all(seats, matrices, params, evidence)
    winners = results.set_index("division")["winner"].to_dict()

    assert winners["Calare"] == "IND"
    assert winners["Calwell"] == "ALP"
    assert winners["Monash"] == "LNP"
    assert int(results["winner"].eq("IND").sum()) == 11


def test_candidate_engine_removes_merged_monash_independent_in_disputed_scenario():
    seats, baseline, baseline_state, params, matrices, evidence = _inputs()
    targets = {
        "ALP": 34.37,
        "LNP": 25.74,
        "GRN": 11.79,
        "ON": 15.84,
        "IND": 6.13,
        "OTH": 6.12,
    }
    adjusted = apply_statewide_primary_adjustment(
        seats,
        targets,
        load_partisan_vote_index(params),
        params=params,
        baseline_results_by_seat=baseline,
        baseline_primary_by_state=baseline_state,
    )
    results, _ = run_candidate_irv_all(adjusted, matrices, params, evidence)
    monash = results.loc[results["division"].eq("Monash")].iloc[0]

    assert monash["winner"] == "LNP"
    assert int(results["winner"].eq("IND").sum()) == 14
