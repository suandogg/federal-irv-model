from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
ARCHIVE_DIR = ROOT / "data" / "archive" / "manual_pre_candidate_recompile"
OUTPUT_DIR = ROOT / "data" / "legacy_app"

CANONICAL_ONLY_FILES = {
    "CATEGORY_PREF_FLOWS_LONG.csv",
    "CATEGORY_SCENARIO_STATS.csv",
    "CATEGORY_FLOW_OVERRIDES.csv",
    "CATEGORY_FLOW_DIAGNOSTIC.csv",
    "CATEGORY_FLOW_VALIDATION.csv",
    "CATEGORY_FLOW_PRODUCTION_IMPACT.csv",
    "NEAREST_FIELD_VALIDATION.csv",
    "CANDIDATE_CLASSIFICATION.csv",
    "CLASSIFICATION_ONLY_DIAGNOSTIC.csv",
}

ARCHIVED_MANUAL_FILES = {
    "SEAT_PREF_FLOWS.csv",
    "SEAT_PREF_FLOWS_LONG.csv",
    "SCENARIO_STATS.csv",
    "SCENARIO_AVGS.csv",
    "SCENARIO_AVGS_BY_CLASS.csv",
}


def build_snapshot() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for existing in OUTPUT_DIR.iterdir():
        if existing.is_file() or existing.is_symlink():
            existing.unlink()
        elif existing.is_dir():
            shutil.rmtree(existing)

    for source in RAW_DIR.iterdir():
        if not source.is_file() or source.name in CANONICAL_ONLY_FILES:
            continue
        shutil.copy2(source, OUTPUT_DIR / source.name)

    for filename in ARCHIVED_MANUAL_FILES:
        source = ARCHIVE_DIR / filename
        if not source.exists():
            raise FileNotFoundError(source)
        shutil.copy2(source, OUTPUT_DIR / filename)

    params_path = OUTPUT_DIR / "PARAMS.csv"
    params = pd.read_csv(params_path, header=None, keep_default_na=False)
    keys = params.iloc[:, 0].astype(str).str.strip().str.upper()
    replacements = {
        "USE_EVIDENCE_SHRINKAGE": "0",
        "USE_NEAREST_FIELD_MATCHING": "0",
        "POOL_SHRINKAGE_K": "1",
        "SEAT_SHRINKAGE_K": "1",
        "NEAREST_FIELD_SHRINKAGE_K": "1",
        "NEAREST_FIELD_MAX_DISTANCE": "99",
        "NEAREST_FIELD_REQUIRE_ALL_REQUESTED": "0",
        "USE_CLASS_EFFECTS": "0",
    }
    for key, value in replacements.items():
        params.loc[keys.eq(key), 1] = value
    params.to_csv(params_path, index=False, header=False)

    marker = OUTPUT_DIR / "LEGACY_SNAPSHOT.txt"
    marker.write_text(
        "Frozen legacy federal IRV app inputs.\n"
        "Manual seat/scenario evidence restored from "
        "data/archive/manual_pre_candidate_recompile.\n"
        "Evidence shrinkage, nearest-field matching and seat-class effects disabled.\n"
        "Google Sheets sync is disabled by app legacy mode.\n"
    )
    print(f"Legacy snapshot files: {sum(1 for path in OUTPUT_DIR.iterdir() if path.is_file())}")


if __name__ == "__main__":
    build_snapshot()
