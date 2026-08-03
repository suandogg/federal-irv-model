import unittest

from production_category_integration_diagnostic import build_production_impact


class ProductionCategoryIntegrationTests(unittest.TestCase):
    def test_impact_report_is_ranked_and_auditable(self):
        impact = build_production_impact()
        self.assertFalse(impact.empty)
        self.assertIn("CRITICAL", set(impact["ReviewPriority"]))
        self.assertTrue(impact["WinnerChanged"].any())
        self.assertTrue(
            impact["LegacyPredictedWinner"].notna().all()
            & impact["CanonicalPredictedWinner"].notna().all()
        )


if __name__ == "__main__":
    unittest.main()
