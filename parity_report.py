from __future__ import annotations

from pathlib import Path

import pandas as pd

from SRC.constants import PARTIES
from SRC.irv import run_irv_all
from SRC.loaders import load_params, load_preference_matrices, load_seat_metadata, load_sheet_baseline_results

ROOT = Path(__file__).resolve().parent
REPORT_DIR = ROOT / "reports"


def _load_sheet_notes() -> dict[str, str]:
    path = ROOT / "data" / "raw" / "SEAT_PREF_FLOWS.csv"
    if not path.exists():
        return {}
    notes: dict[str, str] = {}
    raw = pd.read_csv(path, header=None)
    for _, row in raw.iterrows():
        division = str(row.iloc[1] if len(row) > 1 else "").strip()
        note = str(row.iloc[0] if len(row) > 0 else "").strip()
        if division and division.upper() != "DIVISION" and note and note.lower() != "nan":
            notes[division.upper()] = note
    return notes


def _positive_sheet_parties(row: pd.Series) -> list[str]:
    return [party for party in PARTIES if float(row.get(f"sheet_{party}_final", 0.0) or 0.0) > 1e-12]


def _join_results(py: pd.DataFrame, suffix: str) -> pd.DataFrame:
    cols = [
        "division_key", "winner", "runner_up", "winner_pct", "runner_up_pct", "final_two",
        *[f"{party}_final" for party in PARTIES],
    ]
    return py[cols].rename(columns={
        "winner": f"winner_{suffix}",
        "runner_up": f"runner_up_{suffix}",
        "winner_pct": f"winner_pct_{suffix}",
        "runner_up_pct": f"runner_up_pct_{suffix}",
        "final_two": f"final_two_{suffix}",
        **{f"{party}_final": f"{party}_final_{suffix}" for party in PARTIES},
    })


def _classify(row: pd.Series) -> str:
    if row["winner_match"] and row["runner_match"] and row["final_two_match"] and row["winner_diff_pp"] < 0.01:
        return "matches_original_sheet"
    if row["sheet_positive_parties"] != 2:
        return "original_sheet_export_not_true_2cp"
    if row["sheet_note"]:
        return "old_sheet_marked_inconsistent"
    cal_off_closer = row["winner_diff_pp_no_calibration"] < row["winner_diff_pp"]
    no_cal_final_two_match = row["final_two_no_calibration"] == row["sheet_final_two"]
    if cal_off_closer and no_cal_final_two_match:
        return "calibration_path_difference"
    if row["final_two_match"]:
        return "vote_total_difference_only"
    return "needs_formula_trace"


def build_report() -> tuple[pd.DataFrame, pd.DataFrame]:
    seats = load_seat_metadata()
    matrices = load_preference_matrices()
    params = load_params()
    sheet = load_sheet_baseline_results()
    notes = _load_sheet_notes()

    cal_results, _ = run_irv_all(seats, matrices, params, apply_calibration=True)
    no_cal_results, _ = run_irv_all(seats, matrices, params, apply_calibration=False)

    report = (
        sheet.merge(_join_results(cal_results, "python"), on="division_key", how="left")
        .merge(_join_results(no_cal_results, "no_calibration"), on="division_key", how="left")
    )
    report["sheet_positive_parties"] = report.apply(lambda row: len(_positive_sheet_parties(row)), axis=1)
    report["sheet_note"] = report["division_key"].map(notes).fillna("")
    report["winner_match"] = report["winner_python"] == report["sheet_winner"]
    report["runner_match"] = report["runner_up_python"] == report["sheet_runner_up"]
    report["final_two_match"] = report["final_two_python"] == report["sheet_final_two"]
    report["winner_diff_pp"] = (report["winner_pct_python"] - report["sheet_winner_pct"]).abs() * 100
    report["runner_diff_pp"] = (report["runner_up_pct_python"] - report["sheet_runner_up_pct"]).abs() * 100
    report["winner_diff_pp_no_calibration"] = (report["winner_pct_no_calibration"] - report["sheet_winner_pct"]).abs() * 100
    report["reason"] = report.apply(_classify, axis=1)

    ordered_cols = [
        "division", "reason", "sheet_winner", "winner_python", "winner_no_calibration",
        "sheet_runner_up", "runner_up_python", "runner_up_no_calibration",
        "sheet_final_two", "final_two_python", "final_two_no_calibration",
        "sheet_winner_pct", "winner_pct_python", "winner_pct_no_calibration",
        "winner_diff_pp", "winner_diff_pp_no_calibration", "runner_diff_pp",
        "sheet_positive_parties", "sheet_note",
    ]
    report = report[ordered_cols].sort_values(["reason", "winner_diff_pp"], ascending=[True, False])

    summary = pd.DataFrame([
        {"metric": "seats_compared", "value": len(report)},
        {"metric": "winner_matches", "value": int(report["sheet_winner"].eq(report["winner_python"]).sum())},
        {"metric": "runner_up_matches", "value": int(report["sheet_runner_up"].eq(report["runner_up_python"]).sum())},
        {"metric": "final_two_matches", "value": int(report["sheet_final_two"].eq(report["final_two_python"]).sum())},
        {"metric": "within_0_01pp", "value": int((report["winner_diff_pp"] < 0.01).sum())},
        {"metric": "within_0_10pp", "value": int((report["winner_diff_pp"] < 0.10).sum())},
        {"metric": "within_0_50pp", "value": int((report["winner_diff_pp"] < 0.50).sum())},
        {"metric": "mean_abs_winner_diff_pp", "value": report["winner_diff_pp"].mean()},
        {"metric": "max_abs_winner_diff_pp", "value": report["winner_diff_pp"].max()},
    ])
    reason_counts = report["reason"].value_counts().rename_axis("metric").reset_index(name="value")
    reason_counts["metric"] = "reason_" + reason_counts["metric"]
    summary = pd.concat([summary, reason_counts], ignore_index=True)
    return report, summary



def _markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_(no rows)_"
    cols = [str(col) for col in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        values = []
        for col in df.columns:
            value = row[col]
            if isinstance(value, float):
                value = f"{value:.6g}"
            values.append(str(value).replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def write_markdown(report: pd.DataFrame, summary: pd.DataFrame) -> None:
    REPORT_DIR.mkdir(exist_ok=True)
    lines = [
        "# Original Sheet Parity Report", "",
        "This report compares the raw Python IRV engine against the exported original Google Sheets/App Script results in `data/raw/SEAT_PROBS_3CP.csv`.", "",
        "It deliberately does not use the web-app scenario controls or current `PARTISAN_VOTE_INDEX` sheet. The purpose is to test the preference/IRV port after seat-level primaries have already been fixed.", "",
        "## Summary", "", _markdown_table(summary), "",
        "## Reason Counts", "", _markdown_table(report["reason"].value_counts().rename_axis("reason").reset_index(name="seats")), "",
        "## Largest Differences", "", _markdown_table(report.sort_values("winner_diff_pp", ascending=False).head(25)), "",
    ]
    (REPORT_DIR / "parity_report.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    report, summary = build_report()
    REPORT_DIR.mkdir(exist_ok=True)
    report.to_csv(REPORT_DIR / "parity_report.csv", index=False)
    summary.to_csv(REPORT_DIR / "parity_summary.csv", index=False)
    write_markdown(report, summary)
    print(summary.to_string(index=False))
    print(f"\nWrote {REPORT_DIR / 'parity_report.md'}")


if __name__ == "__main__":
    main()
