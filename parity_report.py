from __future__ import annotations

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
                "actual_winner_pct": shares[ordered[0]],
            }
        )

    return pd.DataFrame(rows)


def build_report() -> tuple[pd.DataFrame, pd.DataFrame]:
    seats = load_seat_metadata()
    matrices = load_preference_matrices()
    params = load_params()
    predicted, _ = run_irv_all(seats, matrices, params, apply_calibration=True)

    report = _actual_results().merge(
        predicted[
            [
                "division",
                "division_key",
                "winner",
                "runner_up",
                "final_two",
                "winner_pct",
            ]
        ],
        on="division_key",
        how="left",
    )
    report["winner_match"] = report["winner"].eq(report["actual_winner"])
    report["runner_up_match"] = report["runner_up"].eq(report["actual_runner_up"])
    report["final_two_match"] = report["final_two"].eq(report["actual_final_two"])
    report["winner_diff_pp"] = (
        report["winner_pct"] * 100 - report["actual_winner_pct"]
    ).abs()

    summary = pd.DataFrame(
        [
            {"metric": "seats_compared", "value": len(report)},
            {"metric": "winner_matches", "value": int(report["winner_match"].sum())},
            {"metric": "runner_up_matches", "value": int(report["runner_up_match"].sum())},
            {"metric": "final_two_matches", "value": int(report["final_two_match"].sum())},
            {"metric": "mean_abs_winner_diff_pp", "value": report["winner_diff_pp"].mean()},
            {"metric": "max_abs_winner_diff_pp", "value": report["winner_diff_pp"].max()},
        ]
    )
    return report.sort_values("winner_diff_pp", ascending=False), summary


def _markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_(no rows)_"

    cols = [str(col) for col in df.columns]
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join(["---"] * len(cols)) + " |",
    ]
    for _, row in df.iterrows():
        values = []
        for col in df.columns:
            value = row[col]
            if isinstance(value, float):
                value = f"{value:.6g}"
            values.append(str(value).replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def write_reports(report: pd.DataFrame, summary: pd.DataFrame) -> None:
    REPORT_DIR.mkdir(exist_ok=True)
    report.to_csv(REPORT_DIR / "baseline_reconstruction_report.csv", index=False)
    summary.to_csv(REPORT_DIR / "baseline_reconstruction_summary.csv", index=False)

    lines = [
        "# Baseline Reconstruction Report",
        "",
        "This compares the deterministic IRV engine with the official baseline results",
        "stored in `BASELINE_RESULTS_BY_SEAT.csv`. It is a reconstruction check, not",
        "an out-of-sample accuracy test.",
        "",
        "## Summary",
        "",
        _markdown_table(summary),
        "",
        "## Largest differences",
        "",
        _markdown_table(report.head(25)),
        "",
    ]
    (REPORT_DIR / "baseline_reconstruction_report.md").write_text("\n".join(lines))


def main() -> None:
    report, summary = build_report()
    write_reports(report, summary)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
