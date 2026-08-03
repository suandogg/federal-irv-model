import unittest

from geography_validation import _group_evidence, _group_prediction


class GeographyValidationTests(unittest.TestCase):
    def test_group_evidence_excludes_held_out_seat(self):
        observations = {
            "OTH|ALP+LNP": {
                "A": {"ALP": 0.8, "LNP": 0.2},
                "B": {"ALP": 0.4, "LNP": 0.6},
                "C": {"ALP": 0.2, "LNP": 0.8},
            }
        }
        profiles = {
            "A": {"state": "VIC"},
            "B": {"state": "VIC"},
            "C": {"state": "NSW"},
        }
        evidence = _group_evidence(
            observations,
            excluded_seat="A",
            profiles=profiles,
            field="state",
            group_value="VIC",
        )
        self.assertEqual(evidence["OTH|ALP+LNP"]["seat_observations"], 1)
        self.assertAlmostEqual(
            evidence["OTH|ALP+LNP"]["equal_seat_mean_shares"]["ALP"],
            0.4,
        )

    def test_sparse_group_is_shrunk_toward_national(self):
        prediction = _group_prediction(
            "OTH|ALP+LNP",
            {
                "OTH|ALP+LNP": {
                    "equal_seat_mean_shares": {"ALP": 0.9, "LNP": 0.1},
                    "between_seat_variance": {"ALP": 0.0, "LNP": 0.0},
                    "seat_observations": 1,
                }
            },
            national_prediction={"ALP": 0.5, "LNP": 0.5},
            group_k=5,
        )
        self.assertGreater(prediction["ALP"], 0.5)
        self.assertLess(prediction["ALP"], 0.9)


if __name__ == "__main__":
    unittest.main()
