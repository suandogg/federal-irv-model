from __future__ import annotations

import csv
from pathlib import Path

from SRC.loaders import load_seat_preference_evidence


ROOT = Path(__file__).resolve().parent
REPORT_DIR = ROOT / "reports"


def build_report() -> list[dict]:
    evidence = load_seat_preference_evidence()
    if evidence.empty:
        return []

    scenario_columns = [
        "Seat",
        "Eliminated",
        "ReportedAliveSet",
        "AliveSet",
        "AliveSetSource",
        "AliveSetPositionConflict",
        "RecordedPosition",
        "TopThree",
    ]
    return (
        evidence[scenario_columns]
        .drop_duplicates(["Seat", "Eliminated", "AliveSet"])
        .sort_values(["Seat", "Eliminated"])
        .to_dict("records")
    )


def write_report() -> Path:
    rows = build_report()
    REPORT_DIR.mkdir(exist_ok=True)
    path = REPORT_DIR / "alive_set_provenance_audit.csv"

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)
    return path


if __name__ == "__main__":
    print(write_report().relative_to(ROOT))
