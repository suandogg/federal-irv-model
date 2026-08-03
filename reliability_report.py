from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from SRC.irv import run_irv_all
from SRC.loaders import load_params, load_preference_matrices, load_seat_metadata


ROOT = Path(__file__).resolve().parent
REPORT_DIR = ROOT / "reports"


def build_report() -> tuple[pd.DataFrame, pd.DataFrame]:
    seats = load_seat_metadata()
    matrices = load_preference_matrices()
    params = load_params()
    _, trace = run_irv_all(seats, matrices, params, apply_calibration=True)

    columns = [
        "division",
        "round",
        "eliminated",
        "alive_after",
        "basis",
        "reliability",
        "reliability_reason",
        "pooled_evidence_seats",
        "pooled_mean_variance",
        "class_evidence_seats",
        "nearest_distance",
        "position_conflict",
        "coverage",
        "anchor_weight",
    ]
    detail = trace[[column for column in columns if column in trace.columns]].copy()
    summary = (
        detail.groupby(["reliability", "basis"], as_index=False)
        .agg(rounds=("division", "size"), seats=("division", "nunique"))
        .sort_values(["reliability", "rounds"], ascending=[True, False])
    )
    return detail, summary


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(frame.columns)
        writer.writerows(frame.itertuples(index=False, name=None))


def write_reports() -> tuple[pd.DataFrame, pd.DataFrame]:
    REPORT_DIR.mkdir(exist_ok=True)
    detail, summary = build_report()
    _write_csv(REPORT_DIR / "reliability_report_detail.csv", detail)
    _write_csv(REPORT_DIR / "reliability_report_summary.csv", summary)
    return detail, summary


if __name__ == "__main__":
    _, summary = write_reports()
    print(summary.to_string(index=False))
