import unittest
from pathlib import Path

from shadow_loo_validation import (
    FLOW_OUTPUT,
    _metrics,
    build_shadow_loo_validation,
    build_pairwise_uncertainty,
    pool_observations,
    predict_distribution,
)


@unittest.skipUnless(FLOW_OUTPUT.exists(), "Shadow category flows are not available")
class ShadowLooValidationTests(unittest.TestCase):
    def test_pool_excludes_held_out_seat(self):
        observations = {
            "OTH|ALP+LNP": {
                "A": {"shares": {"ALP": 1.0, "LNP": 0.0}, "weight": 1.0},
                "B": {"shares": {"ALP": 0.0, "LNP": 1.0}, "weight": 0.5},
            }
        }
        pooled = pool_observations(observations, "A")
        self.assertEqual(pooled["OTH|ALP+LNP"]["seat_observations"], 1)
        self.assertEqual(pooled["OTH|ALP+LNP"]["effective_seats"], 0.5)
        self.assertEqual(pooled["OTH|ALP+LNP"]["shares"]["LNP"], 1.0)

    def test_prediction_is_normalised(self):
        evidence = {
            "OTH|ALP+LNP": {
                "shares": {"ALP": 0.4, "LNP": 0.6},
                "variance": {"ALP": 0.01, "LNP": 0.01},
                "seat_observations": 3,
                "effective_seats": 2.0,
            }
        }
        prediction, match, _, _ = predict_distribution(
            "OTH|ALP+LNP",
            evidence,
            {"OTH": {"ALP": 0.5, "LNP": 0.5}},
            1.0,
        )
        self.assertEqual(match, "exact")
        self.assertAlmostEqual(sum(prediction.values()), 1.0)

    def test_metrics_are_zero_for_exact_prediction(self):
        result = _metrics({"ALP": 0.4, "LNP": 0.6}, {"ALP": 0.4, "LNP": 0.6})
        self.assertEqual(result, {"mae": 0.0, "brier": 0.0, "total_variation": 0.0})

    def test_full_validation_covers_all_official_category_exits(self):
        detail, summary, _ = build_shadow_loo_validation()
        self.assertTrue(summary["observations"].eq(488).all())
        self.assertEqual(summary["method"].nunique(), 5)
        pairwise = build_pairwise_uncertainty(
            detail,
            summary,
            bootstrap_samples=20,
            seed=1,
        )
        self.assertEqual(set(pairwise["subset"]), {
            "all", "combined_categories", "oth", "combined_oth"
        })


if __name__ == "__main__":
    unittest.main()
