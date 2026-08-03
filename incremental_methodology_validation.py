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


ROOT = Path(__file__).resolve().parent
REPORT_DIR = ROOT / "reports"
SUMMARY_OUTPUT = REPORT_DIR / "incremental_methodology_summary.csv"
DETAIL_OUTPUT = REPORT_DIR / "incremental_methodology_seat_detail.csv"
SHEET_OUTPUT = ROOT / "data" / "raw" / "INCREMENTAL_METHOD_VALIDATION.csv"

CONFIGURATIONS = (
    (
        "1_pass_through_original_fallback",
        {
            "USE_EVIDENCE_SHRINKAGE": 0,
            "USE_NEAREST_FIELD_MATCHING": 0,
            "USE_CLASS_EFFECTS": 0,
        },
    ),
    (
        "2_add_evidence_shrinkage",
        {
            "USE_EVIDENCE_SHRINKAGE": 1,
            "USE_NEAREST_FIELD_MATCHING": 0,
            "USE_CLASS_EFFECTS": 0,
        },
    ),
    (
        "3_add_nearest_field",
        {
            "USE_EVIDENCE_SHRINKAGE": 1,
            "USE_NEAREST_FIELD_MATCHING": 1,
            "USE_CLASS_EFFECTS": 0,
        },
    ),
    (
        "4_add_seat_class",
        {
            "USE_EVIDENCE_SHRINKAGE": 1,
            "USE_NEAREST_FIELD_MATCHING": 1,
            "USE_CLASS_EFFECTS": 1,
        },
    ),
)


def _actual_results() -> pd.DataFrame:
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
                "actual_runner_up": ordered[1],
                "actual_final_two": "+".join(sorted(final)),
                "actual_winner_share": shares[ordered[0]] / 100.0,
            }
        )
    return pd.DataFrame(rows)


def build_incremental_validation() -> tuple[pd.DataFrame, pd.DataFrame]:
    seats = load_seat_metadata()
    matrices = load_preference_matrices()
    base_params = load_params()
    actual = _actual_results()
    detail_frames = []
    summary_rows = []

    for stage, scalar_overrides in CONFIGURATIONS:
        params = copy.deepcopy(base_params)
        params["scalars"].update(scalar_overrides)
        results, trace = run_irv_all(
            seats,
            matrices,
            params,
            apply_calibration=True,
        )
        detail = actual.merge(
            results[
                [
                    "division",
                    "division_key",
                    "winner",
                    "runner_up",
                    "final_two",
                    "winner_pct",
                    "elimination_order",
                ]
            ],
            on="division_key",
            how="inner",
        )
        detail.insert(0, "stage", stage)
        detail["winner_match"] = detail["winner"].eq(detail["actual_winner"])
        detail["runner_up_match"] = detail["runner_up"].eq(
            detail["actual_runner_up"]
        )
        detail["final_two_match"] = detail["final_two"].eq(
            detail["actual_final_two"]
        )
        detail["absolute_winner_error_pp"] = (
            detail["winner_pct"] - detail["actual_winner_share"]
        ).abs() * 100.0
        detail_frames.append(detail)

        basis_counts = trace["basis"].value_counts()
        summary_rows.append(
            {
                "stage": stage,
                **scalar_overrides,
                "seats": len(detail),
                "winner_matches": int(detail["winner_match"].sum()),
                "runner_up_matches": int(detail["runner_up_match"].sum()),
                "final_two_matches": int(detail["final_two_match"].sum()),
                "mean_absolute_winner_error_pp": detail[
                    "absolute_winner_error_pp"
                ].mean(),
                "nearest_field_rounds": int(
                    basis_counts.get("posterior_nearest_field", 0)
                ),
                "seat_shrunk_rounds": int(
                    basis_counts.get("seat_pref_flow_shrunk", 0)
                ),
                "pooled_shrunk_rounds": int(
                    sum(
                        count
                        for basis, count in basis_counts.items()
                        if "shrunk" in basis and basis != "seat_pref_flow_shrunk"
                    )
                ),
                "class_weighted_rounds": int(trace["class_evidence_weight"].notna().sum()),
            }
        )

    detail = pd.concat(detail_frames, ignore_index=True)
    summary = pd.DataFrame(summary_rows)
    return detail, summary


def main() -> None:
    detail, summary = build_incremental_validation()
    REPORT_DIR.mkdir(exist_ok=True)
    detail.to_csv(DETAIL_OUTPUT, index=False)
    summary.to_csv(SUMMARY_OUTPUT, index=False)
    summary.to_csv(SHEET_OUTPUT, index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
