from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from SRC.evidence import (
    nearest_scenario_distribution,
    normalise_distribution,
    shrink_distribution,
)
from SRC.loaders import load_params, load_seat_metadata
from loo_validation import _loo_evidence, _metrics, _observations


ROOT = Path(__file__).resolve().parent
REPORT_DIR = ROOT / "reports"
GROUP_K_GRID = (1.0, 2.0, 5.0, 10.0)
NATIONAL_POOL_K = 1.0


def _seat_profiles() -> dict[str, dict[str, str]]:
    seats = load_seat_metadata()
    return {
        row["division_key"]: {
            "state": str(row.get("state") or "").strip().upper(),
            "classification": str(row.get("classification") or "").strip(),
        }
        for _, row in seats.iterrows()
    }


def _group_evidence(
    observations: dict[str, dict[str, dict[str, float]]],
    excluded_seat: str,
    profiles: dict[str, dict[str, str]],
    field: str,
    group_value: str,
) -> dict[str, dict]:
    grouped_observations = {}
    for scenario_key, by_seat in observations.items():
        included = {
            seat_key: shares
            for seat_key, shares in by_seat.items()
            if seat_key != excluded_seat
            and profiles.get(seat_key, {}).get(field) == group_value
        }
        if included:
            grouped_observations[scenario_key] = included

    _, evidence = _loo_evidence(grouped_observations, excluded_seat)
    return evidence


def _national_prediction(
    scenario_key: str,
    national_evidence: dict[str, dict],
    params: dict,
) -> dict[str, float]:
    eliminated, alive_text = scenario_key.split("|", 1)
    alive = alive_text.split("+")
    scenario = national_evidence.get(scenario_key)
    ideology = params.get("ideology", {}).get(eliminated, {})

    if scenario:
        return shrink_distribution(
            empirical=scenario["equal_seat_mean_shares"],
            prior=ideology,
            parties=alive,
            seats=scenario["seat_observations"],
            variance=scenario["between_seat_variance"],
            shrinkage_k=NATIONAL_POOL_K,
        )[0]

    nearest, _ = nearest_scenario_distribution(
        eliminated=eliminated,
        requested_alive=alive,
        scenario_evidence=national_evidence,
        ideology_prior=ideology,
        shrinkage_k=NATIONAL_POOL_K,
    )
    return nearest or normalise_distribution(ideology, alive)


def _group_prediction(
    scenario_key: str,
    group_evidence: dict[str, dict],
    national_prediction: dict[str, float],
    group_k: float,
) -> dict[str, float]:
    eliminated, alive_text = scenario_key.split("|", 1)
    alive = alive_text.split("+")
    scenario = group_evidence.get(scenario_key)

    if scenario:
        return shrink_distribution(
            empirical=scenario["equal_seat_mean_shares"],
            prior=national_prediction,
            parties=alive,
            seats=scenario["seat_observations"],
            variance=scenario["between_seat_variance"],
            shrinkage_k=group_k,
        )[0]

    nearest, _ = nearest_scenario_distribution(
        eliminated=eliminated,
        requested_alive=alive,
        scenario_evidence=group_evidence,
        ideology_prior=national_prediction,
        shrinkage_k=group_k,
    )
    return nearest or national_prediction


def build_validation() -> tuple[pd.DataFrame, pd.DataFrame]:
    observations = _observations()
    profiles = _seat_profiles()
    params = load_params()
    rows = []

    national_cache = {
        seat_key: _loo_evidence(observations, seat_key)[1]
        for by_seat in observations.values()
        for seat_key in by_seat
    }
    state_cache = {}
    class_cache = {}

    for scenario_key, by_seat in observations.items():
        for seat_key, actual in by_seat.items():
            profile = profiles.get(seat_key, {})
            state = profile.get("state", "")
            seat_class = profile.get("classification", "")
            national_evidence = national_cache[seat_key]
            national = _national_prediction(scenario_key, national_evidence, params)

            mae, brier = _metrics(actual, national)
            rows.append(
                {
                    "method": "national",
                    "state_k": "",
                    "class_k": "",
                    "seat": seat_key,
                    "scenario": scenario_key,
                    "mae": mae,
                    "brier": brier,
                }
            )

            state_key = (seat_key, state)
            if state_key not in state_cache:
                state_cache[state_key] = _group_evidence(
                    observations,
                    seat_key,
                    profiles,
                    "state",
                    state,
                )
            class_key = (seat_key, seat_class)
            if class_key not in class_cache:
                class_cache[class_key] = _group_evidence(
                    observations,
                    seat_key,
                    profiles,
                    "classification",
                    seat_class,
                )

            state_predictions = {}
            class_predictions = {}
            for group_k in GROUP_K_GRID:
                state_prediction = _group_prediction(
                    scenario_key,
                    state_cache[state_key],
                    national,
                    group_k,
                )
                class_prediction = _group_prediction(
                    scenario_key,
                    class_cache[class_key],
                    national,
                    group_k,
                )
                state_predictions[group_k] = state_prediction
                class_predictions[group_k] = class_prediction

                for method, prediction in (
                    ("state", state_prediction),
                    ("class", class_prediction),
                ):
                    mae, brier = _metrics(actual, prediction)
                    rows.append(
                        {
                            "method": method,
                            "state_k": group_k if method == "state" else "",
                            "class_k": group_k if method == "class" else "",
                            "seat": seat_key,
                            "scenario": scenario_key,
                            "mae": mae,
                            "brier": brier,
                        }
                    )

            for state_k, state_prediction in state_predictions.items():
                for class_k, class_prediction in class_predictions.items():
                    alive = list(actual)
                    combined = normalise_distribution(
                        {
                            party: (
                                state_prediction.get(party, 0.0)
                                + class_prediction.get(party, 0.0)
                            )
                            / 2.0
                            for party in alive
                        },
                        alive,
                    )
                    mae, brier = _metrics(actual, combined)
                    rows.append(
                        {
                            "method": "state_class",
                            "state_k": state_k,
                            "class_k": class_k,
                            "seat": seat_key,
                            "scenario": scenario_key,
                            "mae": mae,
                            "brier": brier,
                        }
                    )

    detail = pd.DataFrame(rows)
    summary = (
        detail.groupby(
            ["method", "state_k", "class_k"],
            dropna=False,
            as_index=False,
        )
        .agg(
            observations=("scenario", "size"),
            mean_mae=("mae", "mean"),
            mean_brier=("brier", "mean"),
        )
        .sort_values(["mean_brier", "mean_mae"])
    )
    return detail, summary


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(frame.columns)
        writer.writerows(frame.itertuples(index=False, name=None))


def write_reports() -> pd.DataFrame:
    REPORT_DIR.mkdir(exist_ok=True)
    detail, summary = build_validation()
    _write_csv(REPORT_DIR / "geography_validation_detail.csv", detail)
    _write_csv(REPORT_DIR / "geography_validation_summary.csv", summary)
    return summary


if __name__ == "__main__":
    print(write_reports().head(20).to_string(index=False))
