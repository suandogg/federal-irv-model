import pytest

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

