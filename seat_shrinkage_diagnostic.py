from __future__ import annotations

import copy
from pathlib import Path

import pandas as pd

from SRC.constants import PARTIES
from SRC.irv import run_irv_all
from SRC.loaders import (
    load_baseline_results_by_seat,
    load_params,
    load_preference_matrices,
    load_seat_metadata,
)
from SRC.preference_engine import get_preference_weights


ROOT = Path(__file__).resolve().parent
REPORT_DIR = ROOT / "reports"
CURRENT_K = 1.0
UNSHRUNK_K = 0.0


def _params_with_seat_k(params: dict, value: float) -> dict:
    adjusted = copy.deepcopy(params)
    adjusted.setdefault("scalars", {})["USE_EVIDENCE_SHRINKAGE"] = 1.0
    adjusted["scalars"]["SEAT_SHRINKAGE_K"] = float(value)
    adjusted["SEAT_SHRINKAGE_K_BY_DIVISION"] = {}
    return adjusted


def _actual_outcomes() -> pd.DataFrame:
    baseline = load_baseline_results_by_seat()
    rows = []
    for _, row in baseline.iterrows():
        shares = {
            party: float(row.get(f"{party}_2CP", 0.0) or 0.0)
            for party in PARTIES
        }
        final = [party for party, share in shares.items() if share > 1e-9]
        if len(final) != 2:
            continue
        ordered = sorted(final, key=lambda party: shares[party], reverse=True)
        rows.append(
            {
                "division_key": row["division_key"],
                "actual_winner": ordered[0],
                "actual_final_two": "+".join(sorted(final)),
            }
        )
    return pd.DataFrame(rows)


def _trace_lookup(trace: pd.DataFrame) -> dict[tuple[str, str, str], dict]:
    out = {}
    for _, row in trace.iterrows():
        key = (
            str(row.get("division_key") or ""),
            str(row.get("eliminated") or ""),
            str(row.get("alive_after") or ""),
        )
        out[key] = row.to_dict()
    return out


def _round_diagnostic(
    seats: pd.DataFrame,
    matrices: dict[str, dict],
    current_params: dict,
    unshrunk_params: dict,
    current_trace: pd.DataFrame,
    unshrunk_trace: pd.DataFrame,
) -> pd.DataFrame:
    current_rounds = _trace_lookup(current_trace)
    unshrunk_rounds = _trace_lookup(unshrunk_trace)
    seat_rows = seats.set_index("division_key").to_dict("index")
    rows = []

    for division_key, matrix_info in matrices.items():
        seat_flows = matrix_info.get("seat_flows", {})
        if not seat_flows or division_key not in seat_rows:
            continue

        seat = seat_rows[division_key]
        matrix = matrix_info.get("matrix", {})
        evidence = matrix_info.get("seat_flow_evidence", {})
        seat_class = str(seat.get("classification", "") or "")

        for scenario, raw_flow in sorted(seat_flows.items()):
            eliminated, alive_key = scenario.split("|", 1)
            alive = alive_key.split("+")
            common = {
                "elim_party": eliminated,
                "alive_parties": alive,
                "aec_row": matrix.get(eliminated, {}),
                "apply_calibration": True,
                "seat_state": matrix_info.get("state", "NAT"),
                "division_key": division_key,
                "seat_flows": seat_flows,
                "seat_flow_evidence": evidence,
                "aec_row_party": eliminated,
                "seat_class": seat_class,
            }
            current_flow, current_diag = get_preference_weights(
                params=current_params, **common
            )
            unshrunk_flow, _ = get_preference_weights(
                params=unshrunk_params, **common
            )

            differences = {
                party: current_flow.get(party, 0.0)
                - unshrunk_flow.get(party, 0.0)
                for party in alive
            }
            largest_party = max(
                alive,
                key=lambda party: abs(differences.get(party, 0.0)),
            )
            flow_tvd_pp = 50.0 * sum(abs(value) for value in differences.values())
            max_recipient_shift_pp = 100.0 * abs(differences[largest_party])

            key = (division_key, eliminated, alive_key)
            current_round = current_rounds.get(key, {})
            unshrunk_round = unshrunk_rounds.get(key, {})
            transfer_share = current_round.get("transfer")
            weighted_effect_pp = (
                flow_tvd_pp * float(transfer_share)
                if transfer_share is not None and not pd.isna(transfer_share)
                else 0.0
            )
            scenario_evidence = evidence.get(scenario, {})

            rows.append(
                {
                    "division": seat.get("division", division_key),
                    "division_key": division_key,
                    "state": matrix_info.get("state", ""),
                    "classification": seat_class,
                    "scenario": scenario,
                    "eliminated": eliminated,
                    "alive_set": alive_key,
                    "historical_votes_at_elimination": scenario_evidence.get(
                        "scenario_total", 0.0
                    ),
                    "position_conflict": bool(
                        scenario_evidence.get("position_conflict", False)
                    ),
                    "current_seat_evidence_weight": current_diag.get(
                        "seat_evidence_weight"
                    ),
                    "flow_total_variation_pp": flow_tvd_pp,
                    "max_recipient_shift_pp": max_recipient_shift_pp,
                    "largest_shift_recipient": largest_party,
                    "largest_shift_direction": (
                        "toward pooled evidence"
                        if differences[largest_party] > 0
                        else "away from local history"
                    ),
                    "largest_shift_signed_pp": 100.0
                    * differences[largest_party],
                    "encountered_current_path": bool(current_round),
                    "encountered_unshrunk_path": bool(unshrunk_round),
                    "current_model_transfer_pct": (
                        100.0 * float(transfer_share)
                        if transfer_share is not None
                        and not pd.isna(transfer_share)
                        else None
                    ),
                    "estimated_current_round_effect_pp": weighted_effect_pp,
                    **{
                        f"local_{party}": float(raw_flow.get(party, 0.0) or 0.0)
                        for party in PARTIES
                    },
                    **{
                        f"current_{party}": float(
                            current_flow.get(party, 0.0) or 0.0
                        )
                        for party in PARTIES
                    },
                }
            )

    return pd.DataFrame(rows)


def _review_priority(row: pd.Series) -> tuple[str, str]:
    if bool(row["winner_changed"]):
        return "Critical", "Winner changes when the seat flow is left unshrunk."
    if bool(row["final_two_changed"]):
        return "High", "Final two changes when the seat flow is left unshrunk."
    if (
        row["final_distribution_change_pp"] >= 5.0
        or row["max_estimated_round_effect_pp"] >= 3.0
    ):
        return "High", "Large final-vote or encountered-round effect."
    if (
        bool(row["elimination_order_changed"])
        or row["max_flow_total_variation_pp"] >= 10.0
        or row["final_distribution_change_pp"] >= 2.0
        or row["max_estimated_round_effect_pp"] >= 1.0
    ):
        return "Medium", "Material local-flow or elimination-path difference."
    return "Low", "Shrinkage has limited effect on the reconstructed result."


def build_report() -> tuple[pd.DataFrame, pd.DataFrame]:
    seats = load_seat_metadata()
    matrices = load_preference_matrices()
    params = load_params()
    current_params = _params_with_seat_k(params, CURRENT_K)
    unshrunk_params = _params_with_seat_k(params, UNSHRUNK_K)

    current_results, current_trace = run_irv_all(
        seats, matrices, current_params, apply_calibration=True
    )
    unshrunk_results, unshrunk_trace = run_irv_all(
        seats, matrices, unshrunk_params, apply_calibration=True
    )
    rounds = _round_diagnostic(
        seats,
        matrices,
        current_params,
        unshrunk_params,
        current_trace,
        unshrunk_trace,
    )

    current_cols = [
        "division",
        "division_key",
        "state",
        "classification",
        "winner",
        "runner_up",
        "final_two",
        "winner_pct",
        "elimination_order",
        *[f"{party}_final" for party in PARTIES],
    ]
    unshrunk_cols = [
        "division_key",
        "winner",
        "runner_up",
        "final_two",
        "winner_pct",
        "elimination_order",
        *[f"{party}_final" for party in PARTIES],
    ]
    comparison = current_results[current_cols].rename(
        columns={
            "winner": "current_winner",
            "runner_up": "current_runner_up",
            "final_two": "current_final_two",
            "winner_pct": "current_winner_pct",
            "elimination_order": "current_elimination_order",
            **{
                f"{party}_final": f"current_{party}_final"
                for party in PARTIES
            },
        }
    ).merge(
        unshrunk_results[unshrunk_cols].rename(
            columns={
                "winner": "unshrunk_winner",
                "runner_up": "unshrunk_runner_up",
                "final_two": "unshrunk_final_two",
                "winner_pct": "unshrunk_winner_pct",
                "elimination_order": "unshrunk_elimination_order",
                **{
                    f"{party}_final": f"unshrunk_{party}_final"
                    for party in PARTIES
                },
            }
        ),
        on="division_key",
        how="inner",
    )

    comparison["winner_changed"] = comparison["current_winner"].ne(
        comparison["unshrunk_winner"]
    )
    comparison["final_two_changed"] = comparison["current_final_two"].ne(
        comparison["unshrunk_final_two"]
    )
    comparison["elimination_order_changed"] = comparison[
        "current_elimination_order"
    ].ne(comparison["unshrunk_elimination_order"])
    comparison["winner_pct_change_pp"] = 100.0 * (
        comparison["current_winner_pct"] - comparison["unshrunk_winner_pct"]
    ).abs()
    comparison["final_distribution_change_pp"] = 50.0 * sum(
        (
            comparison[f"current_{party}_final"]
            - comparison[f"unshrunk_{party}_final"]
        ).abs()
        for party in PARTIES
    )

    round_summary = rounds.groupby("division_key", as_index=False).agg(
        seat_flow_scenarios=("scenario", "count"),
        encountered_scenarios=("encountered_current_path", "sum"),
        max_flow_total_variation_pp=("flow_total_variation_pp", "max"),
        max_recipient_shift_pp=("max_recipient_shift_pp", "max"),
        max_estimated_round_effect_pp=("estimated_current_round_effect_pp", "max"),
        position_conflicts=("position_conflict", "sum"),
    )
    distinctive = rounds.loc[
        rounds.groupby("division_key")["flow_total_variation_pp"].idxmax(),
        ["division_key", "scenario"],
    ].rename(columns={"scenario": "most_distinctive_scenario"})
    summary = (
        comparison.merge(round_summary, on="division_key", how="inner")
        .merge(distinctive, on="division_key", how="left")
        .merge(_actual_outcomes(), on="division_key", how="left")
    )
    summary["current_matches_actual_winner"] = summary["current_winner"].eq(
        summary["actual_winner"]
    )
    summary["unshrunk_matches_actual_winner"] = summary["unshrunk_winner"].eq(
        summary["actual_winner"]
    )
    summary["current_matches_actual_final_two"] = summary["current_final_two"].eq(
        summary["actual_final_two"]
    )
    summary["unshrunk_matches_actual_final_two"] = summary[
        "unshrunk_final_two"
    ].eq(summary["actual_final_two"])

    priorities = summary.apply(_review_priority, axis=1)
    summary["review_priority"] = [item[0] for item in priorities]
    summary["priority_reason"] = [item[1] for item in priorities]
    summary["override_review_candidate"] = summary["review_priority"].isin(
        ["Critical", "High"]
    )
    summary["candidate_k_to_test"] = summary["override_review_candidate"].map(
        {True: 0.5, False: None}
    )
    priority_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    summary["_priority_order"] = summary["review_priority"].map(priority_order)
    summary = summary.sort_values(
        [
            "_priority_order",
            "winner_changed",
            "final_two_changed",
            "max_estimated_round_effect_pp",
            "max_flow_total_variation_pp",
        ],
        ascending=[True, False, False, False, False],
    ).drop(columns=["_priority_order"])

    preferred = [
        "division",
        "division_key",
        "state",
        "classification",
        "review_priority",
        "priority_reason",
        "override_review_candidate",
        "candidate_k_to_test",
        "winner_changed",
        "final_two_changed",
        "elimination_order_changed",
        "current_winner",
        "unshrunk_winner",
        "actual_winner",
        "current_final_two",
        "unshrunk_final_two",
        "actual_final_two",
        "current_matches_actual_winner",
        "unshrunk_matches_actual_winner",
        "current_matches_actual_final_two",
        "unshrunk_matches_actual_final_two",
        "winner_pct_change_pp",
        "final_distribution_change_pp",
        "seat_flow_scenarios",
        "encountered_scenarios",
        "max_flow_total_variation_pp",
        "max_recipient_shift_pp",
        "max_estimated_round_effect_pp",
        "most_distinctive_scenario",
        "position_conflicts",
        "current_elimination_order",
        "unshrunk_elimination_order",
    ]
    return summary[preferred], rounds.sort_values(
        ["flow_total_variation_pp", "estimated_current_round_effect_pp"],
        ascending=False,
    )


def _markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_(no rows)_"
    lines = [
        "| " + " | ".join(str(col) for col in df.columns) + " |",
        "| " + " | ".join(["---"] * len(df.columns)) + " |",
    ]
    for _, row in df.iterrows():
        values = []
        for value in row:
            if isinstance(value, float):
                value = f"{value:.3f}"
            values.append(str(value).replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def write_reports(summary: pd.DataFrame, rounds: pd.DataFrame) -> None:
    REPORT_DIR.mkdir(exist_ok=True)
    summary.to_csv(REPORT_DIR / "seat_shrinkage_impact_summary.csv", index=False)
    rounds.to_csv(REPORT_DIR / "seat_shrinkage_impact_rounds.csv", index=False)

    override_path = ROOT / "data" / "raw" / "SEAT_SHRINKAGE_OVERRIDES.csv"
    existing = pd.DataFrame()
    if override_path.exists():
        existing = pd.read_csv(override_path)
    preserve_cols = ["DivisionKey", "UseOverride", "SeatShrinkageK", "Rationale"]
    if not existing.empty and set(preserve_cols).issubset(existing.columns):
        preserved = existing[preserve_cols].copy()
    else:
        preserved = pd.DataFrame(columns=preserve_cols)
    override_template = summary[
        [
            "division",
            "division_key",
            "state",
            "classification",
            "review_priority",
            "candidate_k_to_test",
        ]
    ].rename(
        columns={
            "division": "Division",
            "division_key": "DivisionKey",
            "state": "State",
            "classification": "Classification",
            "review_priority": "ReviewPriority",
            "candidate_k_to_test": "SuggestedKToTest",
        }
    )
    override_template = override_template.merge(
        preserved, on="DivisionKey", how="left"
    )
    override_template["UseOverride"] = override_template["UseOverride"].fillna(
        False
    )
    override_template.to_csv(override_path, index=False)

    counts = (
        summary["review_priority"]
        .value_counts()
        .reindex(["Critical", "High", "Medium", "Low"], fill_value=0)
        .rename_axis("review_priority")
        .reset_index(name="seats")
    )
    display_cols = [
        "division",
        "state",
        "review_priority",
        "current_winner",
        "unshrunk_winner",
        "current_final_two",
        "unshrunk_final_two",
        "max_flow_total_variation_pp",
        "max_estimated_round_effect_pp",
        "most_distinctive_scenario",
    ]
    lines = [
        "# Seat Shrinkage Impact Diagnostic",
        "",
        "This isolates the effect of `SEAT_SHRINKAGE_K = 1` by comparing it with",
        "`SEAT_SHRINKAGE_K = 0`. All other evidence, class, matrix and nearest-field",
        "settings remain active and unchanged.",
        "",
        "`flow_total_variation_pp` is the percentage-point redistribution mass moved",
        "between recipients by shrinkage. `estimated_current_round_effect_pp` also",
        "weights that difference by the eliminated party's vote in the current path.",
        "",
        "The suggested `candidate_k_to_test = 0.5` is inactive and is only a review",
        "prompt for Critical and High seats; it is not an automatic override.",
        "",
        "## Review counts",
        "",
        _markdown_table(counts),
        "",
        "## Highest-priority seats",
        "",
        _markdown_table(summary[display_cols].head(30)),
        "",
    ]
    (REPORT_DIR / "seat_shrinkage_impact.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main() -> None:
    summary, rounds = build_report()
    write_reports(summary, rounds)
    print(
        summary[
            [
                "division",
                "review_priority",
                "winner_changed",
                "final_two_changed",
                "max_flow_total_variation_pp",
                "max_estimated_round_effect_pp",
            ]
        ]
        .head(20)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
