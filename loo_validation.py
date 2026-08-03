from __future__ import annotations

import copy
import csv
from collections import defaultdict
from pathlib import Path

import pandas as pd

from SRC.constants import PARTIES
from SRC.evidence import (
    nearest_scenario_distribution,
    normalise_distribution,
    shrink_distribution,
)
from SRC.irv import run_irv_for_seat
from SRC.loaders import (
    division_key,
    load_baseline_results_by_seat,
    load_params,
    load_preference_matrices,
    load_seat_metadata,
    load_seat_preference_evidence,
)
from SRC.preference_engine import get_preference_weights


ROOT = Path(__file__).resolve().parent
REPORT_DIR = ROOT / "reports"
POOL_K_GRID = (0.0, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0)
MATRIX_WEIGHT_GRID = (0.0, 0.1, 0.25, 0.5, 0.75, 1.0)


def _observations() -> dict[str, dict[str, dict[str, float]]]:
    evidence = load_seat_preference_evidence()
    votes: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(float))
    )

    for _, row in evidence.iterrows():
        seat_key = division_key(row.get("Seat"))
        eliminated = str(row.get("Eliminated") or "").strip()
        alive = str(row.get("AliveSet") or "").strip()
        recipient = str(row.get("Recipient") or "").strip()
        value = float(row.get("Votes", 0.0) or 0.0)
        if seat_key and eliminated and alive and recipient and value > 0:
            votes[f"{eliminated}|{alive}"][seat_key][recipient] += value

    observations: dict[str, dict[str, dict[str, float]]] = {}
    for scenario_key, seat_rows in votes.items():
        alive = scenario_key.split("|", 1)[1].split("+")
        observations[scenario_key] = {
            seat_key: normalise_distribution(recipient_votes, alive)
            for seat_key, recipient_votes in seat_rows.items()
        }
    return observations


def _loo_evidence(
    observations: dict[str, dict[str, dict[str, float]]],
    excluded_seat: str,
) -> tuple[dict[str, dict[str, float]], dict[str, dict]]:
    shares = {}
    evidence = {}

    for scenario_key, by_seat in observations.items():
        included = [
            row for seat_key, row in by_seat.items() if seat_key != excluded_seat
        ]
        if not included:
            continue

        eliminated, alive_set = scenario_key.split("|", 1)
        alive = alive_set.split("+")
        means = {
            party: sum(row.get(party, 0.0) for row in included) / len(included)
            for party in alive
        }
        variance = {}
        for party in alive:
            if len(included) <= 1:
                variance[party] = 0.0
            else:
                mean = means[party]
                variance[party] = sum(
                    (row.get(party, 0.0) - mean) ** 2 for row in included
                ) / (len(included) - 1)

        shares[scenario_key] = means
        evidence[scenario_key] = {
            "eliminated": eliminated,
            "alive_set": alive_set,
            "shares": means,
            "equal_seat_mean_shares": means,
            "between_seat_variance": variance,
            "seats": len(included),
            "seat_observations": len(included),
            "source": "leave_one_seat_out",
        }

    return shares, evidence


def _posterior_prediction(
    scenario_key: str,
    loo_evidence: dict[str, dict],
    params: dict,
    pool_k: float,
) -> tuple[dict[str, float], float]:
    eliminated, alive_set = scenario_key.split("|", 1)
    alive = alive_set.split("+")
    scenario = loo_evidence.get(scenario_key)
    prior = params.get("ideology", {}).get(eliminated, {})
    if not scenario:
        nearest, diagnostic = nearest_scenario_distribution(
            eliminated=eliminated,
            requested_alive=alive,
            scenario_evidence=loo_evidence,
            ideology_prior=prior,
            shrinkage_k=pool_k,
        )
        if nearest:
            return nearest, float(diagnostic.get("evidence_weight", 0.0) or 0.0)
        return normalise_distribution(prior, alive), 0.0

    return shrink_distribution(
        empirical=scenario["equal_seat_mean_shares"],
        prior=prior,
        parties=alive,
        seats=scenario["seat_observations"],
        variance=scenario["between_seat_variance"],
        shrinkage_k=pool_k,
    )


def _matrix_prediction(
    scenario_key: str,
    matrix_info: dict,
    params: dict,
) -> dict[str, float]:
    eliminated, alive_set = scenario_key.split("|", 1)
    alive = alive_set.split("+")
    matrix_row = (matrix_info or {}).get("matrix", {}).get(eliminated, {})
    values = {party: float(matrix_row.get(party, 0.0) or 0.0) for party in alive}
    if sum(values.values()) <= 0:
        values = params.get("ideology", {}).get(eliminated, {})
    return normalise_distribution(values, alive)


def _loo_national_matrix(
    matrices: dict[str, dict],
    excluded_seat: str,
) -> dict:
    accumulated = {
        eliminated: {party: 0.0 for party in PARTIES}
        for eliminated in PARTIES
    }
    contributing_seats = {eliminated: 0 for eliminated in PARTIES}

    for seat_key, matrix_info in matrices.items():
        if seat_key == excluded_seat:
            continue
        matrix = matrix_info.get("matrix", {})
        for eliminated in PARTIES:
            row = {
                party: float(matrix.get(eliminated, {}).get(party, 0.0) or 0.0)
                for party in PARTIES
                if party != eliminated
            }
            if sum(row.values()) <= 0:
                continue
            row = normalise_distribution(row, list(row))
            for party, value in row.items():
                accumulated[eliminated][party] += value
            contributing_seats[eliminated] += 1

    pooled = {}
    for eliminated in PARTIES:
        count = contributing_seats[eliminated]
        if count <= 0:
            continue
        pooled[eliminated] = {
            party: accumulated[eliminated][party] / count
            for party in PARTIES
        }

    return {
        "state": "NAT",
        "matrix": pooled,
        "seat_flows": {},
        "matrix_source": "national_leave_one_seat_out",
        "matrix_contributing_seats": contributing_seats,
    }


def _hybrid_prediction(
    scenario_key: str,
    matrix_info: dict,
    params: dict,
    loo_shares: dict[str, dict[str, float]],
    loo_evidence: dict[str, dict],
    pool_k: float,
    matrix_weight: float,
) -> dict[str, float]:
    alive = scenario_key.split("|", 1)[1].split("+")
    matrix_prediction = _matrix_prediction(scenario_key, matrix_info, params)
    posterior_prediction, _ = _posterior_prediction(
        scenario_key,
        loo_evidence,
        params,
        pool_k,
    )
    return normalise_distribution(
        {
            party: matrix_weight * matrix_prediction.get(party, 0.0)
            + (1.0 - matrix_weight) * posterior_prediction.get(party, 0.0)
            for party in alive
        },
        alive,
    )


def _metrics(
    actual: dict[str, float],
    predicted: dict[str, float],
) -> tuple[float, float]:
    parties = list(actual)
    errors = [predicted.get(party, 0.0) - actual[party] for party in parties]
    mae = sum(abs(error) for error in errors) / len(errors)
    brier = sum(error**2 for error in errors)
    return mae, brier


def build_flow_validation() -> tuple[pd.DataFrame, pd.DataFrame]:
    observations = _observations()
    matrices = load_preference_matrices()
    params = load_params()
    detail = []
    loo_evidence_cache = {
        seat_key: _loo_evidence(observations, seat_key)
        for by_seat in observations.values()
        for seat_key in by_seat
    }
    loo_matrix_cache = {
        seat_key: _loo_national_matrix(matrices, seat_key)
        for seat_key in loo_evidence_cache
    }

    for pool_k in POOL_K_GRID:
        for scenario_key, by_seat in observations.items():
            for seat_key, actual in by_seat.items():
                loo_shares, loo_evidence = loo_evidence_cache[seat_key]
                matrix_info = loo_matrix_cache[seat_key]
                for matrix_weight in MATRIX_WEIGHT_GRID:
                    if matrix_weight == 0:
                        method = "posterior_only"
                    elif matrix_weight == 1:
                        method = "matrix_only"
                    else:
                        method = "hybrid"
                    predicted = _hybrid_prediction(
                        scenario_key,
                        matrix_info,
                        params,
                        loo_shares,
                        loo_evidence,
                        pool_k,
                        matrix_weight,
                    )
                    mae, brier = _metrics(actual, predicted)
                    detail.append(
                        {
                            "pool_k": pool_k,
                            "matrix_weight": matrix_weight,
                            "method": method,
                            "seat": seat_key,
                            "scenario": scenario_key,
                            "alive_parties": len(actual),
                            "loo_seats": loo_evidence.get(
                                scenario_key, {}
                            ).get("seat_observations", 0),
                            "mae": mae,
                            "brier": brier,
                        }
                    )

    detail_df = pd.DataFrame(detail)
    summary = (
        detail_df.groupby(["pool_k", "matrix_weight", "method"], as_index=False)
        .agg(
            observations=("scenario", "size"),
            mean_mae=("mae", "mean"),
            mean_brier=("brier", "mean"),
        )
        .sort_values(["mean_brier", "mean_mae"])
    )
    return detail_df, summary


def _actual_outcomes() -> dict[str, dict[str, str]]:
    baseline = load_baseline_results_by_seat()
    outcomes = {}
    for _, row in baseline.iterrows():
        final = [
            party
            for party in PARTIES
            if float(row.get(f"{party}_2CP", 0.0) or 0.0) > 0
        ]
        if len(final) != 2:
            continue
        winner = max(final, key=lambda party: float(row.get(f"{party}_2CP", 0.0) or 0.0))
        outcomes[row["division_key"]] = {
            "winner": winner,
            "final_two": "+".join(sorted(final)),
        }
    return outcomes


def build_outcome_validation(
    best_pool_k: float,
    best_matrix_weight: float,
) -> pd.DataFrame:
    observations = _observations()
    seats = load_seat_metadata()
    matrices = load_preference_matrices()
    params = load_params()
    actual = _actual_outcomes()
    rows = []
    loo_evidence_cache = {
        seat_key: _loo_evidence(observations, seat_key)
        for seat_key in seats["division_key"]
    }
    loo_matrix_cache = {
        seat_key: _loo_national_matrix(matrices, seat_key)
        for seat_key in seats["division_key"]
    }

    for _, seat in seats.iterrows():
        seat_key = seat["division_key"]
        if seat_key not in actual:
            continue
        loo_shares, loo_evidence = loo_evidence_cache[seat_key]

        configurations = (
            ("matrix_only", 1.0),
            ("posterior_only", 0.0),
            ("hybrid", best_matrix_weight),
        )
        for method, matrix_weight in configurations:
            model_params = copy.deepcopy(params)
            if method == "matrix_only":
                model_params["POSTERIOR_SCENARIOS"] = {}
                model_params["POSTERIOR_SCENARIO_EVIDENCE"] = {}
                matrix_info = copy.deepcopy(loo_matrix_cache[seat_key])
            else:
                model_params["POSTERIOR_SCENARIOS"] = loo_shares
                model_params["POSTERIOR_SCENARIO_EVIDENCE"] = loo_evidence
                model_params["scalars"]["USE_EVIDENCE_SHRINKAGE"] = 1.0
                model_params["scalars"]["POOL_SHRINKAGE_K"] = best_pool_k
                model_params["scalars"]["MATRIX_POSTERIOR_BLEND_WEIGHT"] = matrix_weight
                matrix_info = copy.deepcopy(loo_matrix_cache[seat_key])
                if method == "posterior_only":
                    matrix_info["matrix"] = {}

            matrix_info["seat_flows"] = {}
            result, _ = run_irv_for_seat(
                seat,
                matrix_info,
                model_params,
                apply_calibration=True,
            )
            rows.append(
                {
                    "method": method,
                    "seat": seat_key,
                    "actual_winner": actual[seat_key]["winner"],
                    "predicted_winner": result["winner"],
                    "winner_match": result["winner"] == actual[seat_key]["winner"],
                    "actual_final_two": actual[seat_key]["final_two"],
                    "predicted_final_two": result["final_two"],
                    "final_two_match": result["final_two"] == actual[seat_key]["final_two"],
                }
            )

    detail = pd.DataFrame(rows)
    return (
        detail.groupby("method", as_index=False)
        .agg(
            seats=("seat", "size"),
            winner_matches=("winner_match", "sum"),
            final_two_matches=("final_two_match", "sum"),
        )
        .sort_values("winner_matches", ascending=False)
    )


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(frame.columns)
        writer.writerows(frame.itertuples(index=False, name=None))


def _markdown_table(frame: pd.DataFrame) -> str:
    columns = [str(column) for column in frame.columns]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in frame.itertuples(index=False, name=None):
        values = []
        for value in row:
            if isinstance(value, float):
                value = f"{value:.6g}"
            values.append(str(value).replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def write_reports() -> tuple[pd.DataFrame, pd.DataFrame]:
    REPORT_DIR.mkdir(exist_ok=True)
    detail, summary = build_flow_validation()
    best_overall = summary.iloc[0]
    best_hybrid = summary[summary["method"].eq("hybrid")].iloc[0]
    best_pool_k = float(best_hybrid["pool_k"])
    best_matrix_weight = float(best_hybrid["matrix_weight"])
    outcomes = build_outcome_validation(best_pool_k, best_matrix_weight)

    _write_csv(REPORT_DIR / "loo_flow_validation_detail.csv", detail)
    _write_csv(REPORT_DIR / "loo_flow_validation_summary.csv", summary)
    _write_csv(REPORT_DIR / "loo_outcome_validation_summary.csv", outcomes)

    lines = [
        "# Leave-one-seat-out validation",
        "",
        "Each seat/scenario observation has equal weight. Ballot totals do not act as",
        "independent sample size. The held-out seat is excluded from pooled evidence.",
        "",
        "The held-out seat is excluded from both pooled scenario evidence and the",
        "equal-seat national preference matrix.",
        "",
        f"Best overall method: `{best_overall['method']}` "
        f"(pool K {best_overall['pool_k']:g}, matrix weight "
        f"{best_overall['matrix_weight']:.0%})",
        "",
        f"Best genuine hybrid: pool K {best_pool_k:g}, matrix weight "
        f"{best_matrix_weight:.0%}",
        "",
        "## Flow accuracy",
        "",
        _markdown_table(summary),
        "",
        "## Secondary seat outcomes",
        "",
        _markdown_table(outcomes),
        "",
        "## Limitation",
        "",
        "This tests generalisation across electorates within one election. It cannot",
        "fully validate the persistence of a seat-specific flow into a later election.",
        "State and seat-class pooling are intentionally deferred to the later empirical",
        "effects stage.",
        "",
    ]
    (REPORT_DIR / "loo_validation.md").write_text("\n".join(lines), encoding="utf-8")
    return summary, outcomes


if __name__ == "__main__":
    flow_summary, outcome_summary = write_reports()
    print(flow_summary.head(12).to_string(index=False))
    print(outcome_summary.to_string(index=False))
