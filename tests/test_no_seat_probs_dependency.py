import unittest
from pathlib import Path

from SRC.loaders import load_lnp_to_on_by_seat, load_primary_2cp_lnp_to_on


ROOT = Path(__file__).resolve().parents[1]


class SeatProbDependencyTests(unittest.TestCase):
    def test_lnp_to_on_inputs_come_only_from_primary_2cp(self):
        self.assertEqual(
            load_lnp_to_on_by_seat(),
            load_primary_2cp_lnp_to_on(),
        )

    def test_abandoned_sheet_is_not_referenced_by_model_or_sync_manifest(self):
        checked_files = (
            ROOT / "app.py",
            ROOT / "SRC" / "loaders.py",
            ROOT / "parity_report.py",
            ROOT / "data" / "raw" / "_manifest.csv",
        )
        forbidden_names = ("SEAT_PROBS_3CP", "SEAT_PROBS (3CP)")

        for path in checked_files:
            contents = path.read_text(encoding="utf-8")
            for forbidden_name in forbidden_names:
                self.assertNotIn(forbidden_name, contents, str(path))


if __name__ == "__main__":
    unittest.main()
