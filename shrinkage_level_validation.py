from __future__ import annotations

import copy
from pathlib import Path

import pandas as pd

from incremental_methodology_validation import _actual_results
from loo_validation import _loo_evidence, _metrics, _observations
from SRC.evidence import normalise_distribution, shrink_distribution
from SRC.irv import run_irv_all
from SRC.loaders import (
    load_params,
    load_preference_matrices,
    load_seat_metadata,
)


ROOT = Path(__file__).resolve().parent
REPORT_DIR = ROOT / "reports"
OUTPUT = REPORT_DIR / "shrinkage_level_validation.csv"
SHEET_OUTPUT = ROOT / "data" / "raw" / "SHRINKAGE_LEVEL_VALIDATION.csv"
POOL_K_GRID = (0.0, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0)
SEAT_K_GRID = (0.0, 0.25, 0.5, 1.0, 2.0, 5.0)


def _held_out_pool_metrics(pool_k: float) -> dict[str, float]:
    observations = _observations()
    ideology = load_params().get("ideology", {})
    metrics = []
    for scenario_key, by_seat in observations.items():
        eliminated, alive_text = scenario_key.split("|", 1)
        alive = alive_text.split("+")
        prior = ideology.get(eliminated, {})
        for seat_key, actual in by_seat.items():
            evidence = _loo_evidence(observations, seat_key)[1].get(scenario_key)
            # Exclude singleton scenarios here: this test isolates exact pooled
            # shrinkage and deliberately does not invoke nearest-field matching.
            if not evidence:
                continue
            predicted, _ = shrink_distribution(
                empirical=evidence["equal_seat_mean_shares"],
                prior=normalise_distribution(prior, alive),
                parties=alive,
                seats=evidence["seat_observations"],
                variance=evidence["between_seat_variance"],
                shrinkage_k=pool_k,
            )
            mae, brier = _metrics(actual, predicted)
            metrics.append((mae, brier))
    return {
        "HeldOutObservations": len(metrics),
        "HeldOutMeanMAE": sum(row[0] for row in metrics) / len(metrics),
        "HeldOutMeanBrier": sum(row[1] for row in metrics) / len(metrics),
    }


def _reconstruction_metrics(pool_k: float, seat_k: float) -> dict[str, float]:
    params = copy.deepcopy(load_params())
    params["scalars"].update(
        {
            "USE_EVIDENCE_SHRINKAGE": 1,
            "USE_NEAREST_FIELD_MATCHING": 0,
            "USE_CLASS_EFFECTS": 0,
            "POOL_SHRINKAGE_K": pool_k,
            "SEAT_SHRINKAGE_K": seat_k,
        }
    )
    results, trace = run_irv_all(
        load_seat_metadata(),
        load_preference_matrices(),
        params,
        apply_calibration=True,
    )
    detail = _actual_results().merge(
        results[["division_key", "winner", "runner_up", "final_two", "winner_pct"]],
        on="division_key",
    )
    return {
        "WinnerMatches": int(detail["winner"].eq(detail["actual_winner"]).sum()),
        "RunnerUpMatches": int(
            detail["runner_up"].eq(detail["actual_runner_up"]).sum()
        ),
        "FinalTwoMatches": int(
            detail["final_two"].eq(detail["actual_final_two"]).sum()
        ),
        "MeanAbsoluteWinnerErrorPP": (
            detail["winner_pct"] - detail["actual_winner_share"]
        ).abs().mean()
        * 100.0,
        "SeatShrunkRounds": int(trace["basis"].eq("seat_pref_flow_shrunk").sum()),
    }


def build_validation() -> pd.DataFrame:
    rows = []
    held_out = {pool_k: _held_out_pool_metrics(pool_k) for pool_k in POOL_K_GRID}
    for pool_k in POOL_K_GRID:
        rows.append(
            {
                "Test": "POOL_ONLY_SEAT_K_0",
                "PoolShrinkageK": pool_k,
                "SeatShrinkageK": 0.0,
                **held_out[pool_k],
                **_reconstruction_metrics(pool_k, 0.0),
            }
        )
    for fixed_pool_k, label in ((0.0, "SEAT_ONLY_POOL_K_0"), (2.0, "SEAT_WITH_POOL_K_2")):
        for seat_k in SEAT_K_GRID:
            rows.append(
                {
                    "Test": label,
                    "PoolShrinkageK": fixed_pool_k,
                    "SeatShrinkageK": seat_k,
                    "HeldOutObservations": "",
                    "HeldOutMeanMAE": "",
                    "HeldOutMeanBrier": "",
                    **_reconstruction_metrics(fixed_pool_k, seat_k),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    result = build_validation()
    REPORT_DIR.mkdir(exist_ok=True)
    result.to_csv(OUTPUT, index=False)
    result.to_csv(SHEET_OUTPUT, index=False)
    print(result.to_string(index=False))


if __name__ == "__main__":
    main()
