from __future__ import annotations

from pathlib import Path

import pandas as pd

from SRC.loaders import load_seat_metadata


ROOT = Path(__file__).resolve().parent
OLD_REPORT = (
    ROOT
    / "data"
    / "archive"
    / "manual_pre_candidate_recompile"
    / "baseline_reconstruction_report.csv"
)
NEW_REPORT = ROOT / "reports" / "baseline_reconstruction_report.csv"
REPORT_OUTPUT = ROOT / "reports" / "production_category_evidence_impact.csv"
SHEET_OUTPUT = ROOT / "data" / "raw" / "CATEGORY_FLOW_PRODUCTION_IMPACT.csv"


def build_production_impact() -> pd.DataFrame:
    old = pd.read_csv(OLD_REPORT).set_index("division_key")
    new = pd.read_csv(NEW_REPORT).set_index("division_key")
    metadata = load_seat_metadata().set_index("division_key")
    common = old.index.intersection(new.index)
    rows = []

    for key in common:
        winner_changed = old.at[key, "winner"] != new.at[key, "winner"]
        final_two_changed = old.at[key, "final_two"] != new.at[key, "final_two"]
        runner_up_changed = old.at[key, "runner_up"] != new.at[key, "runner_up"]
        delta_pp = (
            float(new.at[key, "winner_pct"]) - float(old.at[key, "winner_pct"])
        ) * 100.0
        if not (winner_changed or final_two_changed or runner_up_changed or abs(delta_pp) >= 0.25):
            continue
        priority = "LOW"
        if abs(delta_pp) >= 2.0:
            priority = "MEDIUM"
        if final_two_changed or abs(delta_pp) >= 5.0:
            priority = "HIGH"
        if winner_changed:
            priority = "CRITICAL"
        rows.append(
            {
                "ReviewPriority": priority,
                "State": metadata.at[key, "state"] if key in metadata.index else "",
                "Electorate": new.at[key, "division"],
                "ActualWinner": new.at[key, "actual_winner"],
                "ActualFinalTwo": new.at[key, "actual_final_two"],
                "LegacyPredictedWinner": old.at[key, "winner"],
                "CanonicalPredictedWinner": new.at[key, "winner"],
                "WinnerChanged": winner_changed,
                "LegacyPredictedFinalTwo": old.at[key, "final_two"],
                "CanonicalPredictedFinalTwo": new.at[key, "final_two"],
                "FinalTwoChanged": final_two_changed,
                "LegacyWinnerShare": float(old.at[key, "winner_pct"]),
                "CanonicalWinnerShare": float(new.at[key, "winner_pct"]),
                "WinnerShareDeltaPP": delta_pp,
                "LegacyWinnerMatchedActual": bool(old.at[key, "winner_match"]),
                "CanonicalWinnerMatchedActual": bool(new.at[key, "winner_match"]),
                "LegacyFinalTwoMatchedActual": bool(old.at[key, "final_two_match"]),
                "CanonicalFinalTwoMatchedActual": bool(new.at[key, "final_two_match"]),
            }
        )
    result = pd.DataFrame(rows)
    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    result["_priority"] = result["ReviewPriority"].map(priority_order)
    result["_absolute_delta"] = result["WinnerShareDeltaPP"].abs()
    return result.sort_values(
        ["_priority", "_absolute_delta"], ascending=[True, False]
    ).drop(columns=["_priority", "_absolute_delta"])


def main() -> None:
    result = build_production_impact()
    result.to_csv(REPORT_OUTPUT, index=False)
    result.to_csv(SHEET_OUTPUT, index=False)
    print(f"Materially changed seats: {len(result)}")
    print(f"Winner changes: {int(result['WinnerChanged'].sum())}")
    print(f"Final-two changes: {int(result['FinalTwoChanged'].sum())}")


if __name__ == "__main__":
    main()
