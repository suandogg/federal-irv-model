import pytest
import pandas as pd

import SRC.loaders as loaders
from SRC.constants import PARTIES
from SRC.irv import apply_statewide_primary_adjustment
from SRC.loaders import load_params, load_partisan_vote_index, load_seat_metadata


DEFAULT_TARGETS = {
    "ALP": 34.56,
    "LNP": 31.82,
    "GRN": 12.20,
    "ON": 6.40,
    "IND": 7.27,
    "OTH": 7.75,
}


def test_partisan_vote_index_is_keyed_to_all_electorates():
    pvi = load_partisan_vote_index(load_params())

    assert len(pvi) == 150
    assert pvi["division_key"].nunique() == 150


def test_wentworth_uses_its_named_calculation_row():
    pvi = load_partisan_vote_index(load_params()).set_index("division_key")
    wentworth = pvi.loc["WENTWORTH"]

    assert wentworth["ALP"] == pytest.approx(-0.1959448255)
    assert wentworth["LNP"] == pytest.approx(0.03864572244)
    assert wentworth["GRN"] == pytest.approx(-0.01900793074)
    assert wentworth["ON"] == pytest.approx(-1.137378727)
    assert wentworth["IND"] == pytest.approx(0.2789966336)
    assert wentworth["OTH"] == pytest.approx(-0.07)


def test_on_logit_pvi_comes_from_authoritative_partisan_tab(monkeypatch, tmp_path):
    (tmp_path / "PARTISAN_VOTE_INDEX.csv").write_text(
        "Division,State,ALP,LNP,GRN,ON_LOGIT_PVI,IND,OTH\n"
        "Example,NSW,0.1,0.2,0.3,-1.25,0.4,0.5\n"
    )
    # A conflicting legacy source must have no effect on production loading.
    (tmp_path / "LOGIT_PVI.csv").write_text(
        ",ON\nDivision,Primary PVI\nExample,9.0\n"
    )
    monkeypatch.setattr(loaders, "RAW_DIR", tmp_path)

    pvi = loaders.load_partisan_vote_index(
        {"primary_model": {"use_logit": {"ON": True}}}
    ).set_index("division_key")

    assert pvi.loc["EXAMPLE", "ON"] == pytest.approx(-1.25)


def test_default_wentworth_primary_is_not_replaced_by_national_pattern():
    params = load_params()
    seats = load_seat_metadata()
    pvi = load_partisan_vote_index(params)
    adjusted = apply_statewide_primary_adjustment(
        seats,
        DEFAULT_TARGETS,
        pvi,
        params=params,
    )
    wentworth = adjusted.set_index("division_key").loc["WENTWORTH"]

    assert 13.0 < wentworth["ALP"] * 100 < 18.0
    assert wentworth["IND"] * 100 > 20.0
    assert sum(wentworth[party] for party in PARTIES) == pytest.approx(1.0)


def test_grn_and_ind_preserve_seat_baselines_and_apply_only_national_swing():
    seats = pd.DataFrame(
        [
            {
                "division": "Example",
                "division_key": "EXAMPLE",
                "held_by": "IND",
                "ind_candidate_status": "Incumbent",
                "ind_swing_responsiveness": float("nan"),
                **{party: 1 / len(PARTIES) for party in PARTIES},
            }
        ]
    )
    pvi_values = {party: 0.0 for party in PARTIES}
    pvi_values.update({"GRN": 0.18, "IND": 0.33})
    pvi = pd.DataFrame([{"division_key": "EXAMPLE", **pvi_values}])
    baseline = pd.DataFrame(
        [{"division_key": "EXAMPLE", "GRN_primary": 30.0, "IND_primary": 40.0}]
    )
    baseline_national = {"National": {"GRN": 12.0, "IND": 7.0}}
    params = {
        "primary_model": {
            "a": {"GRN": 0.8, "IND": 0.7},
            "use_logit": {},
        }
    }

    unchanged = apply_statewide_primary_adjustment(
        seats,
        {"ALP": 30, "LNP": 30, "GRN": 12, "ON": 10, "IND": 7, "OTH": 11},
        pvi,
        params=params,
        baseline_results_by_seat=baseline,
        baseline_primary_by_state=baseline_national,
    ).iloc[0]
    swung = apply_statewide_primary_adjustment(
        seats,
        {"ALP": 28, "LNP": 28, "GRN": 14, "ON": 10, "IND": 9, "OTH": 11},
        pvi,
        params=params,
        baseline_results_by_seat=baseline,
        baseline_primary_by_state=baseline_national,
    ).iloc[0]

    assert unchanged["GRN"] == pytest.approx(0.30)
    assert unchanged["IND"] == pytest.approx(0.40)
    assert swung["GRN"] == pytest.approx(0.30 + 0.8 * 0.02)
    assert swung["IND"] == pytest.approx(0.40 + 0.5 * 0.02)
    assert sum(swung[party] for party in PARTIES) == pytest.approx(1.0)
