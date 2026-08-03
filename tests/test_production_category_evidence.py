import unittest

from build_production_category_evidence import build_production_category_evidence


class ProductionCategoryEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seat_flows, cls.scenario_stats = build_production_category_evidence()

    def test_all_category_exits_are_production_scenarios(self):
        scenarios = self.seat_flows[
            ["Seat", "Eliminated", "AliveSet"]
        ].drop_duplicates()
        self.assertEqual(len(scenarios), 488)

    def test_production_defaults_to_pass_through_method(self):
        self.assertEqual(
            set(self.seat_flows["Method"]),
            {"PROPORTIONAL_PRIMARY_ORIGIN_PASS_THROUGH"},
        )

    def test_pass_through_uses_full_category_evidence_weight(self):
        self.assertTrue(
            self.seat_flows["EffectiveEvidenceMultiplier"].eq(1.0).all()
        )

    def test_each_seat_distribution_sums_to_one(self):
        totals = self.seat_flows.groupby(
            ["Seat", "Eliminated", "AliveSet"]
        )["Share"].sum()
        self.assertTrue((totals.sub(1.0).abs() < 1e-9).all())

    def test_pooled_shares_are_equal_seat_means(self):
        scenario = self.scenario_stats.iloc[0]
        rows = self.seat_flows[
            self.seat_flows["Eliminated"].eq(scenario["Eliminated"])
            & self.seat_flows["AliveSet"].eq(scenario["AliveSet"])
            & self.seat_flows["Recipient"].eq(scenario["Recipient"])
        ]
        self.assertAlmostEqual(float(scenario["Share"]), rows["Share"].mean())
        self.assertEqual(scenario["PoolingWeight"], "EQUAL_SEAT")


if __name__ == "__main__":
    unittest.main()
