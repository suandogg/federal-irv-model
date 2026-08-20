from __future__ import annotations

from pathlib import Path

import pandas as pd

from SRC.constants import PARTIES
from SRC.irv import apply_statewide_primary_adjustment
from SRC.loaders import (
    RAW_DIR,
    _to_float,
    division_key,
    load_params,
    load_partisan_vote_index,
    load_seat_metadata,
)


ROOT = Path(__file__).resolve().parent
REPORT_DIR = ROOT / "reports"
DEFAULT_TARGETS = {
    "ALP": 34.56,
    "LNP": 31.82,
    "GRN": 12.20,
    "ON": 6.40,
    "IND": 7.27,
    "OTH": 7.75,
}


def main() -> None:
    displayed = pd.read_csv(RAW_DIR / "PARTISAN_VOTE_INDEX.csv")
    displayed = displayed.rename(columns={"Division": "division", "State": "state"})
    displayed["division_key"] = displayed["division"].map(division_key)
    for party in PARTIES:
        displayed[party] = displayed[party].map(_to_float)

    params = load_params()
    corrected = load_partisan_vote_index(params)
    comparison = displayed.merge(
        corrected,
        on=["division_key"],
        how="outer",
        suffixes=("_old", "_corrected"),
    )
    for party in PARTIES:
        comparison[f"{party}_pvi_delta"] = (
            comparison[f"{party}_corrected"] - comparison[f"{party}_old"]
        )

    seats = load_seat_metadata()
    old_adjusted = apply_statewide_primary_adjustment(
        seats,
        DEFAULT_TARGETS,
        displayed,
        params=params,
    )
    corrected_adjusted = apply_statewide_primary_adjustment(
        seats,
        DEFAULT_TARGETS,
        corrected,
        params=params,
    )
    projected = old_adjusted[["division_key", *PARTIES]].merge(
        corrected_adjusted[["division_key", *PARTIES]],
        on="division_key",
        suffixes=("_old_primary", "_corrected_primary"),
    )
    for party in PARTIES:
        projected[f"{party}_primary_delta_pp"] = 100 * (
            projected[f"{party}_corrected_primary"]
            - projected[f"{party}_old_primary"]
        )

    comparison = comparison.merge(projected, on="division_key", how="left")
    delta_cols = [f"{party}_primary_delta_pp" for party in PARTIES]
    comparison["max_abs_primary_delta_pp"] = comparison[delta_cols].abs().max(axis=1)
    comparison = comparison.sort_values("max_abs_primary_delta_pp", ascending=False)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(REPORT_DIR / "primary_pvi_alignment_audit.csv", index=False)

    affected = int((comparison["max_abs_primary_delta_pp"] > 0.01).sum())
    print(f"Audited {len(comparison)} electorates; {affected} change by more than 0.01pp.")
    print(comparison[["division_old", "max_abs_primary_delta_pp"]].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
