import unittest

import pandas as pd

from build_candidate_classification import suggested_classification
from SRC.loaders import load_candidate_classification


class CandidateClassificationTests(unittest.TestCase):
    def test_major_party_mappings(self):
        self.assertEqual(suggested_classification("ALP", 0.4)[:2], ("ALP", "ALP"))
        self.assertEqual(suggested_classification("LP", 0.4)[:2], ("LNP", "LIB"))
        self.assertEqual(suggested_classification("NP", 0.4)[:2], ("LNP", "NAT"))
        self.assertEqual(suggested_classification("GRN", 0.1)[:2], ("GRN", "GRN"))
        self.assertEqual(suggested_classification("ON", 0.1)[:2], ("ON", "ON"))

    def test_independent_threshold(self):
        self.assertEqual(
            suggested_classification("IND", 0.05)[:2],
            ("IND", "IND_PROMINENT"),
        )
        self.assertEqual(
            suggested_classification("IND", 0.0499)[:2],
            ("OTH", "IND_MINOR"),
        )

    def test_minor_party_maps_to_oth_with_party_code(self):
        self.assertEqual(
            suggested_classification("LTP", 0.1)[:2],
            ("OTH", "OTH_LTP"),
        )

    def test_generated_candidate_classification_is_loadable(self):
        classification = load_candidate_classification()

        self.assertEqual(len(classification), 1126)
        self.assertEqual(classification["CandidateID"].nunique(), 1126)
        self.assertEqual(set(classification["ModelCategory"]), {
            "ALP", "LNP", "GRN", "ON", "IND", "OTH"
        })
        self.assertTrue(
            pd.api.types.is_numeric_dtype(classification["PrimaryShare"])
        )


if __name__ == "__main__":
    unittest.main()
