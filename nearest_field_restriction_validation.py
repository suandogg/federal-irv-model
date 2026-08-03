from __future__ import annotations

import copy
from pathlib import Path

import pandas as pd

from incremental_methodology_validation import _actual_results
from loo_validation import _loo_evidence, _metrics, _observations
from SRC.evidence import nearest_scenario_distribution, normalise_distribution
from SRC.irv import run_irv_all
from SRC.loaders import load_params, load_preference_matrices, load_seat_metadata


ROOT = Path(__file__).resolve().parent
REPORT_DIR = ROOT / "reports"
OUTPUT = REPORT_DIR / "nearest_field_restriction_validation.csv"
SHEET_OUTPUT = ROOT / "data" / "raw" / "NEAREST_FIELD_RESTRICTION_VALIDATION.csv"
K_GRID = (0.0, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0)
RESTRICTIONS = (
    ("UNRESTRICTED", None, False),
    ("MAX_DISTANCE_1", 1, False),
    ("REQUIRE_DONOR_SUPERSET", None, True),
    ("SUPERSET_AND_MAX_DISTANCE_1", 1, True),
)


def _ideology_only_metrics() -> dict[str, float]:
    observations = _observations()
    ideology = load_params().get("ideology", {})
    metrics = []
    for scenario, by_seat in observations.items():
        eliminated, alive_text = scenario.split("|", 1)
        predicted = normalise_distribution(
            ideology.get(eliminated, {}), alive_text.split("+")
        )
        for target in by_seat.values():
            metrics.append(_metrics(target, predicted))
    return {
        "HeldOutObservations": len(metrics),
        "NearestMatchedObservations": 0,
        "NearestCoverage": 0.0,
        "MeanMatchedDistance": "",
        "HeldOutMeanMAE": sum(row[0] for row in metrics) / len(metrics),
        "HeldOutMeanBrier": sum(row[1] for row in metrics) / len(metrics),
    }


def _held_out_scenario_metrics(
    shrinkage_k: float,
    max_distance: int | None,
    require_all_requested: bool,
) -> dict[str, float]:
    observations = _observations()
    all_evidence = _loo_evidence(observations, "__NO_SEAT_EXCLUDED__")[1]
    ideology = load_params().get("ideology", {})
    metrics = []
    matches = 0
    distances = []
    for scenario, by_seat in observations.items():
        eliminated, alive_text = scenario.split("|", 1)
        alive = alive_text.split("+")
        donors = {key: value for key, value in all_evidence.items() if key != scenario}
        predicted, diagnostic = nearest_scenario_distribution(
            eliminated=eliminated,
            requested_alive=alive,
            scenario_evidence=donors,
            ideology_prior=ideology.get(eliminated, {}),
            shrinkage_k=shrinkage_k,
            max_distance=max_distance,
            require_all_requested=require_all_requested,
        )
        if predicted is None:
            predicted = normalise_distribution(ideology.get(eliminated, {}), alive)
        else:
            matches += len(by_seat)
            if diagnostic.get("distance") is not None:
                distances.extend([diagnostic["distance"]] * len(by_seat))
        for target in by_seat.values():
            mae, brier = _metrics(target, predicted)
            metrics.append((mae, brier))
    return {
        "HeldOutObservations": len(metrics),
        "NearestMatchedObservations": matches,
        "NearestCoverage": matches / len(metrics),
        "MeanMatchedDistance": (
            sum(distances) / len(distances) if distances else float("nan")
        ),
        "HeldOutMeanMAE": sum(row[0] for row in metrics) / len(metrics),
        "HeldOutMeanBrier": sum(row[1] for row in metrics) / len(metrics),
    }


def _reconstruction_metrics(
    enabled: bool,
    shrinkage_k: float,
    max_distance: int | None,
    require_all_requested: bool,
) -> dict[str, float]:
    params = copy.deepcopy(load_params())
    params["scalars"].update(
        {
            "USE_EVIDENCE_SHRINKAGE": 1,
            "USE_NEAREST_FIELD_MATCHING": 1 if enabled else 0,
            "USE_CLASS_EFFECTS": 0,
            "POOL_SHRINKAGE_K": 2.0,
            "SEAT_SHRINKAGE_K": 0.0,
            "NEAREST_FIELD_SHRINKAGE_K": shrinkage_k,
            "NEAREST_FIELD_MAX_DISTANCE": (
                99 if max_distance is None else max_distance
            ),
            "NEAREST_FIELD_REQUIRE_ALL_REQUESTED": (
                1 if require_all_requested else 0
            ),
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
    nearest_rows = trace[trace["basis"].eq("posterior_nearest_field")]
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
        "NearestRounds": len(nearest_rows),
        "ReconstructionMeanNearestDistance": nearest_rows["nearest_distance"].mean(),
    }


def build_validation() -> pd.DataFrame:
    rows = [
        {
            "Restriction": "DISABLED",
            "NearestShrinkageK": "",
            "MaxDistance": "",
            "RequireAllRequested": False,
            **_ideology_only_metrics(),
            **_reconstruction_metrics(False, 5.0, None, False),
        }
    ]
    for label, max_distance, require_all_requested in RESTRICTIONS:
        for shrinkage_k in K_GRID:
            rows.append(
                {
                    "Restriction": label,
                    "NearestShrinkageK": shrinkage_k,
                    "MaxDistance": "" if max_distance is None else max_distance,
                    "RequireAllRequested": require_all_requested,
                    **_held_out_scenario_metrics(
                        shrinkage_k,
                        max_distance,
                        require_all_requested,
                    ),
                    **_reconstruction_metrics(
                        True,
                        shrinkage_k,
                        max_distance,
                        require_all_requested,
                    ),
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
