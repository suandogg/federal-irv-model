import unittest
from pathlib import Path

import pandas as pd

from SRC.loaders import (
    load_posterior_scenario_evidence,
    load_seat_preference_evidence,
    load_seat_preference_flow_evidence,
)


class AliveSetProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = load_seat_preference_evidence()

    def test_every_recipient_is_in_canonical_alive_set(self):
        for _, row in self.evidence.iterrows():
            self.assertIn(row["Recipient"], row["AliveSet"].split("+"))

    def test_archived_manual_top_three_provenance_is_preserved(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "archive"
            / "manual_pre_candidate_recompile"
            / "SEAT_PREF_FLOWS_LONG_CANONICAL.csv"
        )
        archived = pd.read_csv(path)
        scenarios = archived.drop_duplicates(["Seat", "Eliminated", "AliveSet"])
        for _, row in scenarios.iterrows():
            top_three = [party for party in str(row["TopThree"]).split("+") if party]
            if row["Eliminated"] in top_three:
                continue
            self.assertTrue(set(top_three).issubset(set(row["AliveSet"].split("+"))))

    def test_only_approved_seat_rows_enter_evidence(self):
        self.assertNotIn("New South Wales", set(self.evidence["Seat"]))
        self.assertNotIn("Victoria", set(self.evidence["Seat"]))
        self.assertNotIn("Calwell*", set(self.evidence["Seat"]))

    def test_cooper_oth_category_exit_preserves_lnp_without_conflict(self):
        rows = self.evidence[
            self.evidence["Seat"].eq("Cooper")
            & self.evidence["Eliminated"].eq("OTH")
        ]
        self.assertFalse(rows.empty)
        self.assertFalse(rows["AliveSetPositionConflict"].any())
        self.assertTrue(rows["AliveSet"].str.split("+", regex=False).map(lambda x: "LNP" in x).all())
        self.assertTrue(
            rows["Method"].eq("PROPORTIONAL_PRIMARY_ORIGIN_PASS_THROUGH").all()
        )

    def test_seat_evidence_preserves_votes_and_provenance(self):
        evidence = load_seat_preference_flow_evidence()
        cooper = evidence["COOPER"]["OTH|ALP+GRN+LNP"]
        self.assertGreater(cooper["scenario_total"], 0)
        self.assertEqual(cooper["seats"], 1)
        self.assertFalse(cooper["position_conflict"])
        self.assertEqual(
            cooper["method"], "PROPORTIONAL_PRIMARY_ORIGIN_PASS_THROUGH"
        )
        self.assertEqual(cooper["evidence_multiplier"], 1.0)

    def test_pooled_evidence_preserves_sample_size(self):
        evidence = load_posterior_scenario_evidence()
        scenario = evidence["GRN|ALP+LNP"]
        self.assertGreater(scenario["scenario_total"], 0)
        self.assertGreater(scenario["seats"], 1)
        self.assertAlmostEqual(sum(scenario["shares"].values()), 1.0)


if __name__ == "__main__":
    unittest.main()
