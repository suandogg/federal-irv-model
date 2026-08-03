import unittest
from pathlib import Path

from build_candidate_round_audit import build_candidate_round_audit


SOURCE_DIR = Path("/Users/callumrees/Desktop/federal_irv_model")


@unittest.skipUnless(
    (SOURCE_DIR / "HouseDopByDivisionDownload-31496.csv").exists(),
    "AEC distribution source is not available",
)
class CandidateRoundAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rounds, cls.transfers, cls.categories, cls.summary = (
            build_candidate_round_audit(SOURCE_DIR)
        )

    def test_aec_counts_reconcile(self):
        self.assertEqual(self.rounds["CandidateID"].nunique(), 1126)
        self.assertEqual(
            self.rounds[["State", "DivisionID"]].drop_duplicates().shape[0],
            150,
        )
        self.assertEqual(int(self.rounds["IsExcludedThisCount"].sum()), 826)
        self.assertEqual(
            int(self.rounds.loc[self.rounds["CountNumber"].gt(0), "TransferCount"].sum()),
            0,
        )

    def test_each_present_category_has_one_finish_position(self):
        duplicates = self.categories.duplicated(
            ["State", "DivisionID", "ModelCategory"]
        )
        self.assertFalse(duplicates.any())
        by_seat = self.categories.groupby(["State", "DivisionID"])
        for _, group in by_seat:
            self.assertEqual(sorted(group["FinishPosition"]), list(range(1, len(group) + 1)))

    def test_internal_exclusion_keeps_same_category_alive(self):
        internal = self.rounds[self.rounds["InternalCategoryExclusion"]]
        self.assertGreater(len(internal), 0)
        self.assertTrue(internal["SameCategoryCandidatesAliveAfter"].gt(0).all())
        self.assertFalse(internal["CategoryExitThisCount"].any())

    def test_category_exit_is_last_surviving_candidate(self):
        exits = self.rounds[self.rounds["CategoryExitThisCount"]]
        self.assertTrue(exits["SameCategoryCandidatesAliveAfter"].eq(0).all())
        self.assertTrue(exits["CandidateID"].eq(exits["LastSurvivingCandidateID"]).all())

    def test_transfer_edges_reconcile_to_each_eliminated_tally(self):
        totals = self.transfers.groupby(
            ["State", "DivisionID", "CountNumber", "EliminatedCandidateID"]
        ).agg({"TransferVotes": "sum", "EliminatedTally": "first"})
        self.assertTrue(totals["TransferVotes"].eq(totals["EliminatedTally"]).all())

    def test_cooper_oth_is_internal_before_category_exit(self):
        cooper = self.rounds[
            self.rounds["Electorate"].eq("Cooper")
            & self.rounds["ModelCategory"].eq("OTH")
            & self.rounds["IsExcludedThisCount"]
        ]
        self.assertGreaterEqual(len(cooper), 1)
        self.assertEqual(int(cooper["CategoryExitThisCount"].sum()), 1)


if __name__ == "__main__":
    unittest.main()
