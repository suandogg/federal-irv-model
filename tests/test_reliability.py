import unittest

from SRC.reliability import assess_reliability


class ReliabilityTests(unittest.TestCase):
    def test_large_consistent_posterior_is_high(self):
        result = assess_reliability(
            {
                "basis": "posterior_shrunk",
                "pooled_evidence_seats": 20,
                "pooled_mean_variance": 0.01,
            }
        )
        self.assertEqual(result["reliability"], "High")

    def test_nearest_field_is_capped_below_high(self):
        result = assess_reliability(
            {
                "basis": "posterior_nearest_field",
                "pooled_evidence_seats": 20,
                "nearest_distance": 1,
            }
        )
        self.assertEqual(result["reliability"], "Medium")

    def test_position_conflict_downgrades_seat_flow(self):
        result = assess_reliability(
            {
                "basis": "seat_pref_flow_shrunk",
                "position_conflict": True,
            }
        )
        self.assertEqual(result["reliability"], "Low")


if __name__ == "__main__":
    unittest.main()
