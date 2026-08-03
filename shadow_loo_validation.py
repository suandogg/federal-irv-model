from __future__ import annotations

import argparse
import math
from collections import defaultdict
from pathlib import Path

import pandas as pd
import numpy as np

from SRC.evidence import normalise_distribution
from SRC.loaders import division_key, load_category_flow_overrides, load_params
from build_shadow_category_flows import (
    DIRECT_METHOD,
    FLOW_OUTPUT,
    PASS_THROUGH_METHOD,
)


ROOT = Path(__file__).resolve().parent
REPORT_DIR = ROOT / "reports"
DETAIL_OUTPUT = REPORT_DIR / "shadow_loo_validation_detail.csv"
SUMMARY_OUTPUT = REPORT_DIR / "shadow_loo_validation_summary.csv"
BREAKDOWN_OUTPUT = REPORT_DIR / "shadow_loo_validation_breakdown.csv"
PAIRWISE_OUTPUT = REPORT_DIR / "shadow_loo_validation_pairwise.csv"
MARKDOWN_OUTPUT = REPORT_DIR / "shadow_loo_validation.md"
SHEET_OUTPUT = ROOT / "data" / "raw" / "CATEGORY_FLOW_VALIDATION.csv"

POOL_K_GRID = (0.0, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0)
LEGACY_MANUAL_FLOW_FILE = (
    ROOT
    / "data"
    / "archive"
    / "manual_pre_candidate_recompile"
    / "SEAT_PREF_FLOWS_LONG_CANONICAL.csv"
)
EVIDENCE_METHODS = (
    "ideology_only",
    "existing_manual_evidence",
    "shadow_direct_unweighted",
    "shadow_direct_coverage",
    "shadow_pass_through",
)


def _alive_key(value: str) -> str:
    parties = {
        party.strip().upper()
        for party in str(value or "").replace(">", "+").replace("|", "+").split("+")
        if party.strip()
    }
    return "+".join(sorted(parties))


def _scenario_key(eliminated: str, alive_value: str) -> str:
    return f"{str(eliminated).strip().upper()}|{_alive_key(alive_value)}"


def _shadow_rows(path: Path = FLOW_OUTPUT) -> pd.DataFrame:
    flows = pd.read_csv(path)
    required = {
        "State",
        "DivisionID",
        "Electorate",
        "EliminatedModelCategory",
        "AliveModelCategoriesAfter",
        "CandidateCount",
        "DefaultEvidenceMultiplier",
        "Method",
        "RecipientModelCategory",
        "Share",
    }
    missing = required - set(flows.columns)
    if missing:
        raise ValueError(f"Shadow category flow file is missing columns: {sorted(missing)}")
    flows = flows.copy()
    flows["seat"] = flows["Electorate"].map(division_key)
    flows["scenario"] = flows.apply(
        lambda row: _scenario_key(
            row["EliminatedModelCategory"], row["AliveModelCategoriesAfter"]
        ),
        axis=1,
    )
    return flows


def _group_flow_rows(
    flows: pd.DataFrame,
    method: str,
    weight_mode: str,
    apply_overrides: bool = False,
) -> dict[str, dict[str, dict]]:
    overrides = load_category_flow_overrides() if apply_overrides else {}
    source = flows[flows["Method"].eq(method)].copy()
    alternate_method = {
        DIRECT_METHOD: PASS_THROUGH_METHOD,
        PASS_THROUGH_METHOD: DIRECT_METHOD,
    }[method]
    alternate = flows[flows["Method"].eq(alternate_method)].copy()
    alternate_lookup = {
        (row["seat"], row["scenario"], row["RecipientModelCategory"]): float(row["Share"])
        for _, row in alternate.iterrows()
    }

    observations: dict[str, dict[str, dict]] = defaultdict(dict)
    group_columns = ["seat", "scenario"]
    for (seat, scenario), group in source.groupby(group_columns, sort=False):
        eliminated, alive = scenario.split("|", 1)
        reference = group.iloc[0]
        override_key = (seat, eliminated, str(reference["AliveModelCategoriesAfter"]).upper())
        override = overrides.get(override_key, {})
        selected_method = str(override.get("method") or method).upper()
        shares = {
            row["RecipientModelCategory"]: float(row["Share"])
            for _, row in group.iterrows()
        }
        if selected_method == alternate_method:
            shares = {
                recipient: alternate_lookup.get((seat, scenario, recipient), 0.0)
                for recipient in alive.split("+")
            }
        shares = normalise_distribution(shares, alive.split("+"))

        if weight_mode == "coverage":
            weight = float(reference["DefaultEvidenceMultiplier"])
        else:
            weight = 1.0
        if override.get("evidence_multiplier") is not None:
            weight = float(override["evidence_multiplier"])
        observations[scenario][seat] = {
            "shares": shares,
            "weight": max(weight, 0.0),
            "candidate_count": int(reference["CandidateCount"]),
        }
    return observations


def build_validation_observations(
    path: Path = FLOW_OUTPUT,
) -> tuple[dict[str, dict[str, dict]], dict[str, dict[str, dict]]]:
    flows = _shadow_rows(path)
    direct = _group_flow_rows(flows, DIRECT_METHOD, "unweighted")
    sources = {
        "ideology_only": {},
        "existing_manual_evidence": {},
        "shadow_direct_unweighted": direct,
        "shadow_direct_coverage": _group_flow_rows(
            flows,
            DIRECT_METHOD,
            "coverage",
            apply_overrides=True,
        ),
        "shadow_pass_through": _group_flow_rows(
            flows,
            PASS_THROUGH_METHOD,
            "unweighted",
        ),
    }
    existing_rows = pd.read_csv(LEGACY_MANUAL_FLOW_FILE)
    existing_votes = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    for _, row in existing_rows.iterrows():
        seat = division_key(row.get("Seat"))
        scenario = _scenario_key(row.get("Eliminated"), row.get("AliveSet"))
        recipient = str(row.get("Recipient") or "").strip().upper()
        votes = float(row.get("Votes", 0.0) or 0.0)
        if seat and recipient and votes > 0:
            existing_votes[scenario][seat][recipient] += votes
    existing = {
        scenario: {
            seat: normalise_distribution(votes, scenario.split("|", 1)[1].split("+"))
            for seat, votes in by_seat.items()
        }
        for scenario, by_seat in existing_votes.items()
    }
    sources["existing_manual_evidence"] = {
        scenario: {
            seat: {"shares": shares, "weight": 1.0, "candidate_count": None}
            for seat, shares in by_seat.items()
        }
        for scenario, by_seat in existing.items()
    }
    return direct, sources


def _weighted_variance(values, weights, mean: float) -> float:
    total_weight = sum(weights)
    if total_weight <= 0:
        return 0.0
    squared_weight = sum(weight * weight for weight in weights)
    denominator = total_weight - squared_weight / total_weight
    if denominator <= 1e-12:
        return 0.0
    return sum(
        weight * (value - mean) ** 2
        for value, weight in zip(values, weights)
    ) / denominator


def pool_observations(
    observations: dict[str, dict[str, dict]],
    excluded_seat: str,
) -> dict[str, dict]:
    evidence = {}
    for scenario, by_seat in observations.items():
        included = [row for seat, row in by_seat.items() if seat != excluded_seat and row["weight"] > 0]
        if not included:
            continue
        alive = scenario.split("|", 1)[1].split("+")
        weights = [float(row["weight"]) for row in included]
        total_weight = sum(weights)
        means = {
            party: sum(
                weight * float(row["shares"].get(party, 0.0))
                for row, weight in zip(included, weights)
            ) / total_weight
            for party in alive
        }
        variances = {
            party: _weighted_variance(
                [float(row["shares"].get(party, 0.0)) for row in included],
                weights,
                means[party],
            )
            for party in alive
        }
        evidence[scenario] = {
            "shares": means,
            "variance": variances,
            "seat_observations": len(included),
            "effective_seats": total_weight,
        }
    return evidence


def _evidence_weight(effective_seats: float, variance: dict[str, float], pool_k: float) -> float:
    if effective_seats <= 0:
        return 0.0
    finite = [
        max(float(value), 0.0)
        for value in variance.values()
        if math.isfinite(float(value))
    ]
    dispersion = sum(finite) / len(finite) if finite else 0.0
    dispersion_penalty = min(dispersion / 0.25, 1.0)
    adjusted = effective_seats / (1.0 + dispersion_penalty)
    return adjusted / (adjusted + pool_k) if adjusted + pool_k > 0 else 0.0


def _blend_with_prior(
    empirical: dict[str, float],
    prior: dict[str, float],
    alive: list[str],
    evidence: dict,
    pool_k: float,
) -> tuple[dict[str, float], float]:
    empirical = normalise_distribution(empirical, alive)
    prior = normalise_distribution(prior, alive)
    weight = _evidence_weight(
        float(evidence.get("effective_seats", 0.0)),
        evidence.get("variance", {}),
        pool_k,
    )
    return normalise_distribution(
        {
            party: weight * empirical[party] + (1.0 - weight) * prior[party]
            for party in alive
        },
        alive,
    ), weight


def predict_distribution(
    scenario: str,
    evidence: dict[str, dict],
    ideology: dict[str, dict[str, float]],
    pool_k: float,
) -> tuple[dict[str, float], str, float, int]:
    eliminated, alive_text = scenario.split("|", 1)
    alive = alive_text.split("+")
    prior = ideology.get(eliminated, {})
    exact = evidence.get(scenario)
    if exact:
        prediction, weight = _blend_with_prior(
            exact["shares"], prior, alive, exact, pool_k
        )
        return prediction, "exact", weight, int(exact["seat_observations"])

    candidates = []
    requested = set(alive)
    for donor_key, donor in evidence.items():
        donor_eliminated, donor_alive_text = donor_key.split("|", 1)
        if donor_eliminated != eliminated:
            continue
        donor_alive = set(donor_alive_text.split("+"))
        missing = requested - donor_alive
        extra = donor_alive - requested
        candidates.append(((len(missing) + len(extra), len(missing)), donor_key, donor_alive, donor))
    if not candidates:
        return normalise_distribution(prior, alive), "ideology_fallback", 0.0, 0

    best_score = min(item[0] for item in candidates)
    selected = [item for item in candidates if item[0] == best_score]
    combined = {party: 0.0 for party in alive}
    combined_weight = 0.0
    total_effective = 0.0
    total_seats = 0
    for _, _, donor_alive, donor in selected:
        projected = {
            party: float(donor["shares"].get(party, 0.0))
            for party in alive
            if party in donor_alive
        }
        if sum(projected.values()) <= 0:
            continue
        projected = normalise_distribution(projected, alive)
        donor_weight = max(float(donor["effective_seats"]), 1e-9)
        for party in alive:
            combined[party] += donor_weight * projected[party]
        combined_weight += donor_weight
        total_effective += float(donor["effective_seats"])
        total_seats += int(donor["seat_observations"])
    if combined_weight <= 0:
        return normalise_distribution(prior, alive), "ideology_fallback", 0.0, 0
    empirical = {party: combined[party] / combined_weight for party in alive}
    nearest_evidence = {
        "effective_seats": total_effective,
        "seat_observations": total_seats,
        "variance": {},
    }
    prediction, weight = _blend_with_prior(
        empirical, prior, alive, nearest_evidence, pool_k
    )
    return prediction, "nearest_field", weight, total_seats


def _metrics(actual: dict[str, float], predicted: dict[str, float]) -> dict[str, float]:
    parties = list(actual)
    errors = [float(predicted.get(party, 0.0)) - float(actual[party]) for party in parties]
    return {
        "mae": sum(abs(error) for error in errors) / len(errors),
        "brier": sum(error * error for error in errors),
        "total_variation": sum(abs(error) for error in errors) / 2.0,
    }


def build_shadow_loo_validation(
    path: Path = FLOW_OUTPUT,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    targets, sources = build_validation_observations(path)
    ideology = load_params().get("ideology", {})
    target_seats = sorted({seat for by_seat in targets.values() for seat in by_seat})
    pooled_cache = {
        method: {
            seat: pool_observations(observations, seat)
            for seat in target_seats
        }
        for method, observations in sources.items()
    }

    detail_records = []
    for scenario, by_seat in targets.items():
        eliminated, alive = scenario.split("|", 1)
        for seat, target in by_seat.items():
            actual = target["shares"]
            for method in EVIDENCE_METHODS:
                for pool_k in POOL_K_GRID:
                    predicted, match_type, evidence_weight, loo_seats = predict_distribution(
                        scenario,
                        pooled_cache[method][seat],
                        ideology,
                        pool_k,
                    )
                    metrics = _metrics(actual, predicted)
                    detail_records.append(
                        {
                            "method": method,
                            "pool_k": pool_k,
                            "seat": seat,
                            "scenario": scenario,
                            "eliminated": eliminated,
                            "alive_parties": len(alive.split("+")),
                            "target_candidate_count": target["candidate_count"],
                            "target_combined_category": target["candidate_count"] > 1,
                            "match_type": match_type,
                            "loo_seats": loo_seats,
                            "evidence_weight": evidence_weight,
                            **metrics,
                        }
                    )
    detail = pd.DataFrame(detail_records)
    summary = (
        detail.groupby(["method", "pool_k"], as_index=False)
        .agg(
            observations=("scenario", "size"),
            exact_matches=("match_type", lambda values: int((values == "exact").sum())),
            nearest_matches=("match_type", lambda values: int((values == "nearest_field").sum())),
            ideology_fallbacks=("match_type", lambda values: int((values == "ideology_fallback").sum())),
            mean_mae=("mae", "mean"),
            mean_brier=("brier", "mean"),
            mean_total_variation=("total_variation", "mean"),
        )
        .sort_values(["mean_brier", "mean_total_variation"])
    )

    best_rows = summary.sort_values(["method", "mean_brier"]).groupby("method", as_index=False).first()
    selected = detail.merge(best_rows[["method", "pool_k"]], on=["method", "pool_k"])
    breakdown = (
        selected.groupby(
            ["method", "pool_k", "eliminated", "target_combined_category"],
            as_index=False,
        )
        .agg(
            observations=("scenario", "size"),
            mean_mae=("mae", "mean"),
            mean_brier=("brier", "mean"),
            mean_total_variation=("total_variation", "mean"),
        )
        .sort_values(["method", "eliminated", "target_combined_category"])
    )
    return detail, summary, breakdown


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


def build_pairwise_uncertainty(
    detail: pd.DataFrame,
    summary: pd.DataFrame,
    bootstrap_samples: int = 4000,
    seed: int = 31496,
) -> pd.DataFrame:
    best_k = (
        summary.sort_values(["method", "mean_brier"])
        .groupby("method", as_index=False)
        .first()[["method", "pool_k"]]
    )
    selected = detail.merge(best_k, on=["method", "pool_k"])
    comparisons = [
        ("shadow_direct_unweighted", "existing_manual_evidence"),
        ("shadow_direct_coverage", "existing_manual_evidence"),
        ("shadow_pass_through", "existing_manual_evidence"),
        ("shadow_direct_coverage", "shadow_direct_unweighted"),
    ]
    subsets = {
        "all": lambda frame: frame,
        "combined_categories": lambda frame: frame[frame["target_combined_category"]],
        "oth": lambda frame: frame[frame["eliminated"].eq("OTH")],
        "combined_oth": lambda frame: frame[
            frame["target_combined_category"] & frame["eliminated"].eq("OTH")
        ],
    }
    rng = np.random.default_rng(seed)
    records = []
    index_columns = ["seat", "scenario"]

    for subset_name, selector in subsets.items():
        subset = selector(selected)
        for challenger, reference in comparisons:
            challenger_rows = subset[subset["method"].eq(challenger)][
                index_columns + ["brier", "total_variation"]
            ].rename(
                columns={
                    "brier": "challenger_brier",
                    "total_variation": "challenger_tvd",
                }
            )
            reference_rows = subset[subset["method"].eq(reference)][
                index_columns + ["brier", "total_variation"]
            ].rename(
                columns={
                    "brier": "reference_brier",
                    "total_variation": "reference_tvd",
                }
            )
            pair = challenger_rows.merge(
                reference_rows,
                on=index_columns,
                how="inner",
                validate="one_to_one",
            )
            if pair.empty:
                continue
            pair["brier_diff"] = pair["challenger_brier"] - pair["reference_brier"]
            pair["tvd_diff"] = pair["challenger_tvd"] - pair["reference_tvd"]
            seat_summary = pair.groupby("seat").agg(
                brier_sum=("brier_diff", "sum"),
                tvd_sum=("tvd_diff", "sum"),
                observations=("brier_diff", "size"),
            )
            seats = seat_summary.index.to_numpy()
            samples = rng.choice(seats, size=(bootstrap_samples, len(seats)), replace=True)
            lookup = seat_summary.to_dict("index")
            bootstrap_brier = []
            bootstrap_tvd = []
            for sampled_seats in samples:
                total_n = sum(lookup[seat]["observations"] for seat in sampled_seats)
                bootstrap_brier.append(
                    sum(lookup[seat]["brier_sum"] for seat in sampled_seats) / total_n
                )
                bootstrap_tvd.append(
                    sum(lookup[seat]["tvd_sum"] for seat in sampled_seats) / total_n
                )
            records.append(
                {
                    "subset": subset_name,
                    "challenger": challenger,
                    "reference": reference,
                    "observations": len(pair),
                    "seats": len(seats),
                    "mean_brier_difference": float(pair["brier_diff"].mean()),
                    "brier_ci_low": float(np.quantile(bootstrap_brier, 0.025)),
                    "brier_ci_high": float(np.quantile(bootstrap_brier, 0.975)),
                    "probability_challenger_better_brier": float(
                        np.mean(np.asarray(bootstrap_brier) < 0)
                    ),
                    "mean_tvd_difference": float(pair["tvd_diff"].mean()),
                    "tvd_ci_low": float(np.quantile(bootstrap_tvd, 0.025)),
                    "tvd_ci_high": float(np.quantile(bootstrap_tvd, 0.975)),
                    "probability_challenger_better_tvd": float(
                        np.mean(np.asarray(bootstrap_tvd) < 0)
                    ),
                }
            )
    return pd.DataFrame(records)


def write_outputs(
    detail: pd.DataFrame,
    summary: pd.DataFrame,
    breakdown: pd.DataFrame,
) -> pd.DataFrame:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    detail.to_csv(DETAIL_OUTPUT, index=False)
    summary.to_csv(SUMMARY_OUTPUT, index=False)
    breakdown.to_csv(BREAKDOWN_OUTPUT, index=False)
    pairwise = build_pairwise_uncertainty(detail, summary)
    pairwise.to_csv(PAIRWISE_OUTPUT, index=False)
    best = summary.sort_values(["method", "mean_brier"]).groupby("method", as_index=False).first()
    best = best.sort_values(["mean_brier", "mean_total_variation"])
    best.to_csv(SHEET_OUTPUT, index=False)

    winner = best.iloc[0]
    lines = [
        "# Shadow category-flow leave-one-seat-out validation",
        "",
        "The target is the official last-surviving-candidate category-exit flow.",
        "Every held-out electorate is excluded from the evidence pool for every method.",
        "Each seat/scenario target has equal validation weight.",
        "",
        f"Best method: `{winner['method']}` with pool K {winner['pool_k']:g}.",
        "",
        "## Best setting for each evidence method",
        "",
        _markdown_table(best),
        "",
        "## Paired uncertainty checks",
        "",
        _markdown_table(pairwise[pairwise["subset"].eq("all")]),
        "",
        "## Interpretation",
        "",
        "Coverage weighting changes both the pooled mean and the effective evidence size.",
        "The pass-through method is evaluated as a diagnostic approximation, not as",
        "official observed flow. Existing manual evidence uses its current canonical",
        "alive-set corrections and excludes the held-out seat.",
        "",
    ]
    MARKDOWN_OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    return best


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate shadow category-flow evidence with leave-one-seat-out tests."
    )
    parser.add_argument("--flows", type=Path, default=FLOW_OUTPUT)
    args = parser.parse_args()
    outputs = build_shadow_loo_validation(args.flows)
    best = write_outputs(*outputs)
    print(best.to_string(index=False))


if __name__ == "__main__":
    main()
