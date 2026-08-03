from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd

import SRC.loaders as loaders
from build_production_category_evidence import build_production_category_evidence
from build_shadow_category_flows import DIRECT_METHOD, PASS_THROUGH_METHOD
from SRC.constants import PARTIES
from SRC.irv import run_irv_all


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
REPORT_DIR = ROOT / "reports"
DETAIL_OUTPUT = REPORT_DIR / "classification_only_comparison.csv"
SUMMARY_OUTPUT = REPORT_DIR / "classification_only_summary.csv"
SHEET_OUTPUT = RAW_DIR / "CLASSIFICATION_ONLY_DIAGNOSTIC.csv"


def _run_model(*, evidence_mode: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    original_raw_dir = loaders.RAW_DIR
    temporary_directory: tempfile.TemporaryDirectory[str] | None = None

    temporary_directory = tempfile.TemporaryDirectory()
    legacy_raw_dir = Path(temporary_directory.name)
    for path in RAW_DIR.iterdir():
        if path.name in {
            "CATEGORY_PREF_FLOWS_LONG.csv",
            "CATEGORY_SCENARIO_STATS.csv",
        }:
            continue
        os.symlink(path, legacy_raw_dir / path.name)
    if evidence_mode != "legacy":
        if evidence_mode in {"canonical_direct", "canonical_pass_through"}:
            method = (
                DIRECT_METHOD
                if evidence_mode == "canonical_direct"
                else PASS_THROUGH_METHOD
            )
            seat_flows, scenario_stats = build_production_category_evidence(
                default_method=method
            )
            seat_flows.to_csv(
                legacy_raw_dir / "CATEGORY_PREF_FLOWS_LONG.csv", index=False
            )
            scenario_stats.to_csv(
                legacy_raw_dir / "CATEGORY_SCENARIO_STATS.csv", index=False
            )
        else:
            raise ValueError(f"Unsupported evidence mode: {evidence_mode}")
    loaders.RAW_DIR = legacy_raw_dir

    try:
        seats = loaders.load_seat_metadata()
        matrices = loaders.load_preference_matrices()
        params = loaders.load_params()
        params["scalars"]["USE_EVIDENCE_SHRINKAGE"] = 0.0
        params["scalars"]["USE_CLASS_EFFECTS"] = 0.0
        return run_irv_all(seats, matrices, params, apply_calibration=True)
    finally:
        loaders.RAW_DIR = original_raw_dir
        if temporary_directory is not None:
            temporary_directory.cleanup()


def _actual_results() -> pd.DataFrame:
    baseline = loaders.load_baseline_results_by_seat()
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
                "ActualWinner": ordered[0],
                "ActualRunnerUp": ordered[1],
                "ActualFinalTwo": "+".join(sorted(final)),
                "ActualWinnerShare": shares[ordered[0]],
            }
        )
    return pd.DataFrame(rows)


def build_classification_only_validation() -> tuple[pd.DataFrame, pd.DataFrame]:
    legacy_results, legacy_trace = _run_model(evidence_mode="legacy")
    direct_results, direct_trace = _run_model(evidence_mode="canonical_direct")
    canonical_results, canonical_trace = _run_model(
        evidence_mode="canonical_pass_through"
    )

    prohibited_basis = "nearest|shrunk|class"
    for label, trace in (
        ("legacy", legacy_trace),
        ("canonical direct", direct_trace),
        ("canonical pass-through", canonical_trace),
    ):
        invalid = trace[trace["basis"].str.contains(prohibited_basis, case=False, regex=True)]
        if not invalid.empty:
            raise AssertionError(
                f"{label} classification-only arm used enhanced evidence logic: "
                f"{sorted(invalid['basis'].unique())}"
            )

    result_columns = [
        "division",
        "division_key",
        "winner",
        "runner_up",
        "final_two",
        "winner_pct",
        "elimination_order",
    ]
    legacy = legacy_results[result_columns].rename(
        columns={
            "division": "Electorate",
            "winner": "LegacyWinner",
            "runner_up": "LegacyRunnerUp",
            "final_two": "LegacyFinalTwo",
            "winner_pct": "LegacyWinnerShare",
            "elimination_order": "LegacyEliminationOrder",
        }
    )
    canonical = canonical_results[result_columns].drop(columns="division").rename(
        columns={
            "winner": "CanonicalWinner",
            "runner_up": "CanonicalRunnerUp",
            "final_two": "CanonicalFinalTwo",
            "winner_pct": "CanonicalWinnerShare",
            "elimination_order": "CanonicalEliminationOrder",
        }
    )
    direct = direct_results[result_columns].drop(columns="division").rename(
        columns={
            "winner": "DirectWinner",
            "runner_up": "DirectRunnerUp",
            "final_two": "DirectFinalTwo",
            "winner_pct": "DirectWinnerShare",
            "elimination_order": "DirectEliminationOrder",
        }
    )
    comparison = (
        legacy.merge(direct, on="division_key", how="inner")
        .merge(canonical, on="division_key", how="inner")
        .merge(_actual_results(), on="division_key", how="inner")
    )
    comparison["WinnerChanged"] = comparison["LegacyWinner"].ne(
        comparison["CanonicalWinner"]
    )
    comparison["FinalTwoChanged"] = comparison["LegacyFinalTwo"].ne(
        comparison["CanonicalFinalTwo"]
    )
    comparison["EliminationOrderChanged"] = comparison[
        "LegacyEliminationOrder"
    ].ne(comparison["CanonicalEliminationOrder"])
    comparison["WinnerShareDeltaPP"] = (
        comparison["CanonicalWinnerShare"] - comparison["LegacyWinnerShare"]
    ) * 100.0
    comparison["LegacyWinnerMatchedActual"] = comparison["LegacyWinner"].eq(
        comparison["ActualWinner"]
    )
    comparison["DirectWinnerMatchedActual"] = comparison["DirectWinner"].eq(
        comparison["ActualWinner"]
    )
    comparison["CanonicalWinnerMatchedActual"] = comparison["CanonicalWinner"].eq(
        comparison["ActualWinner"]
    )
    comparison["LegacyFinalTwoMatchedActual"] = comparison["LegacyFinalTwo"].eq(
        comparison["ActualFinalTwo"]
    )
    comparison["DirectFinalTwoMatchedActual"] = comparison["DirectFinalTwo"].eq(
        comparison["ActualFinalTwo"]
    )
    comparison["CanonicalFinalTwoMatchedActual"] = comparison[
        "CanonicalFinalTwo"
    ].eq(comparison["ActualFinalTwo"])
    comparison["LegacyAbsoluteWinnerErrorPP"] = (
        comparison["LegacyWinnerShare"] - comparison["ActualWinnerShare"] / 100.0
    ).abs() * 100.0
    comparison["DirectAbsoluteWinnerErrorPP"] = (
        comparison["DirectWinnerShare"] - comparison["ActualWinnerShare"] / 100.0
    ).abs() * 100.0
    comparison["CanonicalAbsoluteWinnerErrorPP"] = (
        comparison["CanonicalWinnerShare"]
        - comparison["ActualWinnerShare"] / 100.0
    ).abs() * 100.0
    comparison["AbsoluteErrorChangePP"] = (
        comparison["CanonicalAbsoluteWinnerErrorPP"]
        - comparison["LegacyAbsoluteWinnerErrorPP"]
    )

    comparison["ReviewPriority"] = "LOW"
    comparison.loc[
        comparison["WinnerShareDeltaPP"].abs().ge(2.0), "ReviewPriority"
    ] = "MEDIUM"
    comparison.loc[comparison["FinalTwoChanged"], "ReviewPriority"] = "HIGH"
    comparison.loc[comparison["WinnerChanged"], "ReviewPriority"] = "CRITICAL"
    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    comparison["_priority"] = comparison["ReviewPriority"].map(priority_order)
    comparison["_absolute_delta"] = comparison["WinnerShareDeltaPP"].abs()
    comparison = comparison.sort_values(
        ["_priority", "_absolute_delta"], ascending=[True, False]
    ).drop(columns=["_priority", "_absolute_delta"])

    summary = pd.DataFrame(
        [
            {
                "Metric": "Seats compared",
                "Legacy manual": len(comparison),
                "Canonical direct": len(comparison),
                "Canonical pass-through": len(comparison),
            },
            {
                "Metric": "Winner matches",
                "Legacy manual": int(comparison["LegacyWinnerMatchedActual"].sum()),
                "Canonical direct": int(comparison["DirectWinnerMatchedActual"].sum()),
                "Canonical pass-through": int(comparison["CanonicalWinnerMatchedActual"].sum()),
            },
            {
                "Metric": "Final-two matches",
                "Legacy manual": int(comparison["LegacyFinalTwoMatchedActual"].sum()),
                "Canonical direct": int(comparison["DirectFinalTwoMatchedActual"].sum()),
                "Canonical pass-through": int(comparison["CanonicalFinalTwoMatchedActual"].sum()),
            },
            {
                "Metric": "Mean absolute winner error (pp)",
                "Legacy manual": comparison["LegacyAbsoluteWinnerErrorPP"].mean(),
                "Canonical direct": comparison["DirectAbsoluteWinnerErrorPP"].mean(),
                "Canonical pass-through": comparison["CanonicalAbsoluteWinnerErrorPP"].mean(),
            },
            {
                "Metric": "Pass-through winners changed vs legacy",
                "Legacy manual": 0,
                "Canonical direct": "",
                "Canonical pass-through": int(comparison["WinnerChanged"].sum()),
            },
            {
                "Metric": "Pass-through final twos changed vs legacy",
                "Legacy manual": 0,
                "Canonical direct": "",
                "Canonical pass-through": int(comparison["FinalTwoChanged"].sum()),
            },
            {
                "Metric": "Pass-through elimination orders changed vs legacy",
                "Legacy manual": 0,
                "Canonical direct": "",
                "Canonical pass-through": int(comparison["EliminationOrderChanged"].sum()),
            },
        ]
    )
    return comparison, summary


def main() -> None:
    comparison, summary = build_classification_only_validation()
    REPORT_DIR.mkdir(exist_ok=True)
    comparison.to_csv(DETAIL_OUTPUT, index=False)
    summary.to_csv(SUMMARY_OUTPUT, index=False)
    comparison.to_csv(SHEET_OUTPUT, index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
