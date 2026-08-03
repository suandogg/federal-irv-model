import unittest

from parameter_usage_audit import build_scalar_audit, build_structured_input_audit


class ParameterUsageAuditTests(unittest.TestCase):
    def test_detects_active_and_unused_parameters(self):
        rows = {row["parameter"]: row for row in build_scalar_audit()}
        self.assertEqual(rows["POST_ENTRY_FLOOR"]["status"], "active")
        self.assertEqual(rows["SMOOTH_LAMBDA"]["status"], "unused")

    def test_anchor_setting_uses_canonical_sheet_name(self):
        rows = {row["parameter"]: row for row in build_scalar_audit()}
        self.assertEqual(rows["AEC_ANCHOR_WHEN_MISSING"]["status"], "active")
        self.assertEqual(rows["AEC_ANCHOR_WHEN_MISSING"]["possible_name_mismatch"], "")
        self.assertNotIn("AEC_ANCHOR_WHEN_MISS", rows)

    def test_flags_discarded_scenario_evidence(self):
        rows = {row["input"]: row for row in build_structured_input_audit()}
        self.assertEqual(
            rows["SCENARIO_STATS Votes / ScenarioTotal / Seats"]["status"],
            "active_metadata",
        )


if __name__ == "__main__":
    unittest.main()
