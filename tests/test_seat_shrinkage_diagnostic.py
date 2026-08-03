import unittest

import pandas as pd

from SRC.preference_engine import _seat_shrinkage_k
from seat_shrinkage_diagnostic import _params_with_seat_k, _review_priority


class SeatShrinkageDiagnosticTests(unittest.TestCase):
    def test_params_with_seat_k_preserves_original(self):
        params = {"scalars": {"SEAT_SHRINKAGE_K": 1.0}}
        adjusted = _params_with_seat_k(params, 0.0)

        self.assertEqual(params["scalars"]["SEAT_SHRINKAGE_K"], 1.0)
        self.assertEqual(adjusted["scalars"]["SEAT_SHRINKAGE_K"], 0.0)
        self.assertEqual(adjusted["scalars"]["USE_EVIDENCE_SHRINKAGE"], 1.0)

    def test_review_priority_marks_winner_change_critical(self):
        row = pd.Series(
            {
                "winner_changed": True,
                "final_two_changed": True,
                "elimination_order_changed": True,
                "final_distribution_change_pp": 0.0,
                "max_estimated_round_effect_pp": 0.0,
                "max_flow_total_variation_pp": 0.0,
            }
        )

        priority, _ = _review_priority(row)

        self.assertEqual(priority, "Critical")

    def test_review_priority_marks_material_flow_medium(self):
        row = pd.Series(
            {
                "winner_changed": False,
                "final_two_changed": False,
                "elimination_order_changed": False,
                "final_distribution_change_pp": 0.0,
                "max_estimated_round_effect_pp": 0.0,
                "max_flow_total_variation_pp": 12.0,
            }
        )

        priority, _ = _review_priority(row)

        self.assertEqual(priority, "Medium")

    def test_seat_override_takes_precedence_over_global_k(self):
        params = {
            "scalars": {"SEAT_SHRINKAGE_K": 1.0},
            "SEAT_SHRINKAGE_K_BY_DIVISION": {"MONASH": 0.5},
        }

        self.assertEqual(_seat_shrinkage_k(params, "MONASH"), 0.5)
        self.assertEqual(_seat_shrinkage_k(params, "DEAKIN"), 1.0)


if __name__ == "__main__":
    unittest.main()
