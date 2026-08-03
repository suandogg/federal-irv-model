import hashlib
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
LEGACY_DIR = ROOT / "data" / "legacy_app"
ARCHIVE_DIR = ROOT / "data" / "archive" / "manual_pre_candidate_recompile"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LegacyAppSnapshotTests(unittest.TestCase):
    def test_legacy_snapshot_uses_archived_manual_evidence(self):
        for filename in [
            "SEAT_PREF_FLOWS.csv",
            "SEAT_PREF_FLOWS_LONG.csv",
            "SCENARIO_STATS.csv",
            "SCENARIO_AVGS.csv",
            "SCENARIO_AVGS_BY_CLASS.csv",
        ]:
            self.assertEqual(
                _digest(LEGACY_DIR / filename),
                _digest(ARCHIVE_DIR / filename),
            )

    def test_legacy_snapshot_cannot_prefer_canonical_evidence(self):
        self.assertFalse((LEGACY_DIR / "CATEGORY_PREF_FLOWS_LONG.csv").exists())
        self.assertFalse((LEGACY_DIR / "CATEGORY_SCENARIO_STATS.csv").exists())

    def test_legacy_enhancements_are_disabled(self):
        params = pd.read_csv(LEGACY_DIR / "PARAMS.csv", header=None)
        values = {
            str(row.iloc[0]).strip().upper(): float(row.iloc[1])
            for _, row in params.iterrows()
            if str(row.iloc[0]).strip().upper()
            in {
                "USE_EVIDENCE_SHRINKAGE",
                "USE_NEAREST_FIELD_MATCHING",
                "USE_CLASS_EFFECTS",
            }
        }
        self.assertEqual(
            values,
            {
                "USE_EVIDENCE_SHRINKAGE": 0.0,
                "USE_NEAREST_FIELD_MATCHING": 0.0,
                "USE_CLASS_EFFECTS": 0.0,
            },
        )


if __name__ == "__main__":
    unittest.main()
