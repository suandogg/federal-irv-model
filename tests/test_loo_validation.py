import unittest

from loo_validation import _loo_evidence, _loo_national_matrix, _metrics


class LeaveOneOutValidationTests(unittest.TestCase):
    def test_held_out_seat_is_excluded(self):
        observations = {
            "OTH|ALP+LNP": {
                "A": {"ALP": 0.8, "LNP": 0.2},
                "B": {"ALP": 0.4, "LNP": 0.6},
            }
        }
        shares, evidence = _loo_evidence(observations, "A")
        self.assertEqual(evidence["OTH|ALP+LNP"]["seat_observations"], 1)
        self.assertAlmostEqual(shares["OTH|ALP+LNP"]["ALP"], 0.4)

    def test_distribution_metrics(self):
        mae, brier = _metrics(
            {"ALP": 0.75, "LNP": 0.25},
            {"ALP": 0.5, "LNP": 0.5},
        )
        self.assertAlmostEqual(mae, 0.25)
        self.assertAlmostEqual(brier, 0.125)

    def test_loo_matrix_excludes_held_out_seat(self):
        matrices = {
            "A": {"matrix": {"OTH": {"ALP": 1.0, "LNP": 0.0}}},
            "B": {"matrix": {"OTH": {"ALP": 0.0, "LNP": 1.0}}},
        }
        pooled = _loo_national_matrix(matrices, "A")
        self.assertAlmostEqual(pooled["matrix"]["OTH"]["ALP"], 0.0)
        self.assertAlmostEqual(pooled["matrix"]["OTH"]["LNP"], 1.0)


if __name__ == "__main__":
    unittest.main()
