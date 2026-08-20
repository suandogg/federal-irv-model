import unittest

from SRC.evidence import (
    evidence_weight,
    nearest_scenario_distribution,
    shrink_distribution,
)
from SRC.loaders import load_posterior_scenario_evidence
from SRC.preference_engine import get_preference_weights


class EvidenceShrinkageTests(unittest.TestCase):
    def test_more_seats_increase_evidence_weight(self):
        variance = {"ALP": 0.01, "LNP": 0.01}
        self.assertGreater(
            evidence_weight(20, variance, 5),
            evidence_weight(2, variance, 5),
        )

    def test_variance_reduces_evidence_weight(self):
        self.assertGreater(
            evidence_weight(10, {"ALP": 0.001}, 5),
            evidence_weight(10, {"ALP": 0.10}, 5),
        )

    def test_fractional_seat_multiplier_reduces_evidence_weight(self):
        variance = {"ALP": 0.01, "LNP": 0.01}
        self.assertGreater(
            evidence_weight(1.0, variance, 1.0),
            evidence_weight(0.25, variance, 1.0),
        )

    def test_shrunk_distribution_is_normalised(self):
        result, weight = shrink_distribution(
            {"ALP": 0.8, "LNP": 0.2},
            {"ALP": 0.5, "LNP": 0.5},
            ["ALP", "LNP"],
            seats=2,
            variance={"ALP": 0.02, "LNP": 0.02},
            shrinkage_k=5,
        )
        self.assertAlmostEqual(sum(result.values()), 1.0)
        self.assertGreater(result["ALP"], 0.5)
        self.assertLess(result["ALP"], 0.8)
        self.assertGreater(weight, 0)
        self.assertLess(weight, 1)

    def test_pooled_evidence_has_equal_seat_statistics(self):
        evidence = load_posterior_scenario_evidence()
        scenario = evidence["GRN|ALP+LNP"]
        self.assertEqual(scenario["seat_observations"], scenario["seats"])
        self.assertAlmostEqual(
            sum(scenario["equal_seat_mean_shares"].values()),
            1.0,
        )
        self.assertEqual(
            set(scenario["between_seat_variance"]),
            {"ALP", "LNP"},
        )

    def test_optional_mode_shrinks_exact_seat_flow_toward_pool(self):
        params = {
            "scalars": {
                "USE_EVIDENCE_SHRINKAGE": 1,
                "POOL_SHRINKAGE_K": 1,
                "SEAT_SHRINKAGE_K": 1,
                "MATRIX_POSTERIOR_BLEND_WEIGHT": 0.25,
            },
            "ideology": {"OTH": {"ALP": 0.5, "LNP": 0.5}},
            "POSTERIOR_SCENARIO_EVIDENCE": {
                "OTH|ALP+LNP": {
                    "equal_seat_mean_shares": {"ALP": 0.4, "LNP": 0.6},
                    "between_seat_variance": {"ALP": 0.01, "LNP": 0.01},
                    "seat_observations": 10,
                }
            },
        }
        weights, diagnostic = get_preference_weights(
            elim_party="OTH",
            alive_parties=["ALP", "LNP"],
            aec_row={},
            params=params,
            seat_flows={"OTH|ALP+LNP": {"ALP": 0.9, "LNP": 0.1}},
        )
        self.assertEqual(diagnostic["basis"], "seat_pref_flow_shrunk")
        self.assertGreater(weights["ALP"], 0.4)
        self.assertLess(weights["ALP"], 0.9)

    def test_complete_aec_row_precedes_pooled_evidence(self):
        params = {
            "scalars": {
                "USE_EVIDENCE_SHRINKAGE": 1,
                "POOL_SHRINKAGE_K": 0,
                "MATRIX_POSTERIOR_BLEND_WEIGHT": 0.25,
            },
            "ideology": {"OTH": {"ALP": 0.5, "LNP": 0.5}},
            "POSTERIOR_SCENARIO_EVIDENCE": {
                "OTH|ALP+LNP": {
                    "equal_seat_mean_shares": {"ALP": 0.4, "LNP": 0.6},
                    "between_seat_variance": {"ALP": 0.01, "LNP": 0.01},
                    "seat_observations": 10,
                }
            },
        }
        weights, diagnostic = get_preference_weights(
            elim_party="OTH",
            alive_parties=["ALP", "LNP"],
            aec_row={"ALP": 0.8, "LNP": 0.2},
            params=params,
            seat_flows={},
        )
        self.assertEqual(diagnostic["basis"], "aec_perfect")
        self.assertAlmostEqual(weights["ALP"], 0.8)

    def test_lnp_alp_on_prior_precedes_pooled_evidence(self):
        params = {
            "scalars": {
                "USE_EVIDENCE_SHRINKAGE": 1,
                "POOL_SHRINKAGE_K": 0,
                "MATRIX_POSTERIOR_BLEND_WEIGHT": 0,
            },
            "baselines": {
                "LNP_TO_ON": {"NSW": 0.70, "NAT": 0.71},
                "LNP_TO_ON_BY_SEAT": {},
            },
            "ideology": {"LNP": {"ALP": 0.1, "ON": 0.9}},
            "POSTERIOR_SCENARIO_EVIDENCE": {
                "LNP|ALP+ON": {
                    "equal_seat_mean_shares": {"ALP": 0.18, "ON": 0.82},
                    "between_seat_variance": {"ALP": 0.0, "ON": 0.0},
                    "seat_observations": 1,
                }
            },
        }
        weights, diagnostic = get_preference_weights(
            elim_party="LNP",
            alive_parties=["ALP", "ON"],
            aec_row={"ALP": 0.2, "ON": 0.8},
            params=params,
            seat_state="NSW",
        )
        self.assertEqual(diagnostic["basis"], "lnp_to_alp_on_state_baseline")
        self.assertAlmostEqual(weights["ON"], 0.70)

    def test_exact_flow_uses_category_evidence_multiplier(self):
        params = {
            "scalars": {
                "USE_EVIDENCE_SHRINKAGE": 1,
                "POOL_SHRINKAGE_K": 1,
                "SEAT_SHRINKAGE_K": 1,
            },
            "ideology": {"OTH": {"ALP": 0.5, "LNP": 0.5}},
            "POSTERIOR_SCENARIO_EVIDENCE": {
                "OTH|ALP+LNP": {
                    "equal_seat_mean_shares": {"ALP": 0.4, "LNP": 0.6},
                    "between_seat_variance": {"ALP": 0.01, "LNP": 0.01},
                    "seat_observations": 10,
                }
            },
        }
        _, full = get_preference_weights(
            "OTH",
            ["ALP", "LNP"],
            {},
            params,
            seat_flows={"OTH|ALP+LNP": {"ALP": 0.9, "LNP": 0.1}},
            seat_flow_evidence={"OTH|ALP+LNP": {"evidence_multiplier": 1.0}},
        )
        _, reduced = get_preference_weights(
            "OTH",
            ["ALP", "LNP"],
            {},
            params,
            seat_flows={"OTH|ALP+LNP": {"ALP": 0.9, "LNP": 0.1}},
            seat_flow_evidence={"OTH|ALP+LNP": {"evidence_multiplier": 0.25}},
        )
        self.assertLess(
            reduced["seat_evidence_weight"],
            full["seat_evidence_weight"],
        )

    def test_nearest_field_prefers_superset_at_equal_distance(self):
        evidence = {
            "OTH|ALP+LNP+ON": {
                "equal_seat_mean_shares": {"ALP": 0.4, "LNP": 0.4, "ON": 0.2},
                "seat_observations": 5,
                "between_seat_variance": {},
            },
            "OTH|ALP": {
                "equal_seat_mean_shares": {"ALP": 1.0},
                "seat_observations": 5,
                "between_seat_variance": {},
            },
        }
        result, diagnostic = nearest_scenario_distribution(
            "OTH",
            ["ALP", "LNP"],
            evidence,
            {"ALP": 0.5, "LNP": 0.5},
            shrinkage_k=1,
        )
        self.assertEqual(diagnostic["matched_scenarios"], ["OTH|ALP+LNP+ON"])
        self.assertGreater(result["LNP"], 0)

    def test_nearest_field_never_changes_eliminated_party(self):
        result, diagnostic = nearest_scenario_distribution(
            "GRN",
            ["ALP", "LNP"],
            {
                "OTH|ALP+LNP": {
                    "equal_seat_mean_shares": {"ALP": 0.5, "LNP": 0.5},
                    "seat_observations": 10,
                }
            },
            {"ALP": 0.5, "LNP": 0.5},
            shrinkage_k=1,
        )
        self.assertIsNone(result)
        self.assertEqual(diagnostic["matched_scenarios"], [])

    def test_nearest_field_can_require_donor_superset(self):
        result, diagnostic = nearest_scenario_distribution(
            "OTH",
            ["ALP", "LNP", "ON"],
            {
                "OTH|ALP+LNP": {
                    "equal_seat_mean_shares": {"ALP": 0.5, "LNP": 0.5},
                    "seat_observations": 10,
                }
            },
            {"ALP": 0.4, "LNP": 0.4, "ON": 0.2},
            shrinkage_k=1,
            require_all_requested=True,
        )
        self.assertIsNone(result)
        self.assertEqual(diagnostic["matched_scenarios"], [])

    def test_nearest_field_respects_maximum_distance(self):
        result, diagnostic = nearest_scenario_distribution(
            "OTH",
            ["ALP", "LNP"],
            {
                "OTH|ALP+GRN+LNP+ON": {
                    "equal_seat_mean_shares": {
                        "ALP": 0.4,
                        "GRN": 0.1,
                        "LNP": 0.4,
                        "ON": 0.1,
                    },
                    "seat_observations": 10,
                }
            },
            {"ALP": 0.5, "LNP": 0.5},
            shrinkage_k=1,
            max_distance=1,
        )
        self.assertIsNone(result)
        self.assertEqual(diagnostic["matched_scenarios"], [])

    def test_nearest_field_can_be_disabled_independently(self):
        params = {
            "scalars": {
                "USE_EVIDENCE_SHRINKAGE": 1,
                "USE_NEAREST_FIELD_MATCHING": 0,
                "POOL_SHRINKAGE_K": 1,
            },
            "ideology": {"OTH": {"ALP": 0.7, "LNP": 0.3}},
            "POSTERIOR_SCENARIO_EVIDENCE": {
                "OTH|ALP+GRN+LNP": {
                    "equal_seat_mean_shares": {
                        "ALP": 0.2,
                        "GRN": 0.5,
                        "LNP": 0.3,
                    },
                    "seat_observations": 10,
                    "between_seat_variance": {},
                }
            },
        }
        weights, diagnostic = get_preference_weights(
            "OTH",
            ["ALP", "LNP"],
            {},
            params,
        )
        self.assertEqual(diagnostic["basis"], "ideology")
        self.assertAlmostEqual(weights["ALP"], 0.7)


if __name__ == "__main__":
    unittest.main()
