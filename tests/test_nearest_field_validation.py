import unittest

from nearest_field_validation import build_nearest_field_validation


class NearestFieldValidationTests(unittest.TestCase):
    def test_scenario_holdout_selects_k_five(self):
        result = build_nearest_field_validation()
        selected = result[result["Selected"]]
        self.assertEqual(len(selected), 1)
        self.assertEqual(float(selected.iloc[0]["NearestFieldShrinkageK"]), 5.0)
        self.assertTrue(result["Observations"].eq(488).all())


if __name__ == "__main__":
    unittest.main()
