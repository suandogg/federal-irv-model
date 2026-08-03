import unittest
from pathlib import Path

from build_shadow_category_flows import (
    DIRECT_METHOD,
    PASS_THROUGH_METHOD,
    build_category_flow_diagnostic,
    build_category_flow_overrides,
    compile_shadow_category_flows,
)


SOURCE_DIR = Path("/Users/callumrees/Desktop/federal_irv_model")


@unittest.skipUnless(
    (SOURCE_DIR / "HouseDopByDivisionDownload-31496.csv").exists(),
    "AEC distribution source is not available",
)
class ShadowCategoryFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.flows, cls.comparison, cls.impact, cls.summary = (
            compile_shadow_category_flows(SOURCE_DIR)
        )

    def test_both_methods_cover_every_category_exit(self):
        keys = ["State", "DivisionID", "EliminatedModelCategory"]
        scenarios = self.flows[keys + ["Method"]].drop_duplicates()
        counts = scenarios.groupby(keys)["Method"].nunique()
        self.assertTrue(counts.eq(2).all())
        self.assertEqual(set(self.flows["Method"]), {DIRECT_METHOD, PASS_THROUGH_METHOD})

    def test_each_distribution_sums_to_one(self):
        keys = ["State", "DivisionID", "EliminatedModelCategory", "Method"]
        totals = self.flows.groupby(keys)["Share"].sum()
        self.assertTrue((totals.sub(1.0).abs() < 1e-9).all())

    def test_every_recipient_is_in_alive_set(self):
        for _, row in self.flows.iterrows():
            self.assertIn(
                row["RecipientModelCategory"],
                row["AliveModelCategoriesAfter"].split(">"),
            )

    def test_single_candidate_categories_have_identical_methods(self):
        single = self.impact[self.impact["CandidateCount"].eq(1)]
        self.assertTrue((single["TotalVariationDistance"].abs() < 1e-9).all())

    def test_multi_candidate_categories_can_differ(self):
        multiple = self.impact[self.impact["CandidateCount"].gt(1)]
        self.assertGreater(len(multiple), 0)
        self.assertTrue(multiple["TotalVariationDistance"].gt(0).any())

    def test_direct_method_is_not_marked_approximate(self):
        direct = self.flows[self.flows["Method"].eq(DIRECT_METHOD)]
        passed = self.flows[self.flows["Method"].eq(PASS_THROUGH_METHOD)]
        self.assertFalse(direct["IsApproximation"].any())
        self.assertTrue(passed["IsApproximation"].all())

    def test_default_multiplier_is_coverage_only_for_combined_categories(self):
        direct = self.flows[self.flows["Method"].eq(DIRECT_METHOD)]
        single = direct[direct["CandidateCount"].eq(1)]
        multiple = direct[direct["CandidateCount"].gt(1)]
        self.assertTrue(single["DefaultEvidenceMultiplier"].eq(1.0).all())
        self.assertTrue(
            multiple["DefaultEvidenceMultiplier"].eq(
                multiple["LastSurvivorPrimaryCoverage"]
            ).all()
        )

    def test_override_template_only_contains_combined_categories(self):
        overrides = build_category_flow_overrides(
            self.impact,
            existing_path=Path("/path/that/does/not/exist.csv"),
        )
        self.assertTrue(overrides["CandidateCount"].gt(1).all())
        self.assertTrue(overrides["UseOverride"].eq("FALSE").all())
        self.assertEqual(len(overrides), 132)

    def test_diagnostic_has_review_priority(self):
        diagnostic = build_category_flow_diagnostic(self.impact)
        self.assertEqual(
            set(diagnostic["ReviewPriority"]),
            {"CRITICAL", "HIGH", "MEDIUM", "LOW"},
        )


if __name__ == "__main__":
    unittest.main()
