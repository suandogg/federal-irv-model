import pandas as pd
import streamlit as st

from SRC.candidate_irv import load_candidate_irv_evidence, run_candidate_irv_all
from SRC.constants import PARTIES, PARTY_COLOURS, PARTY_LABELS
from SRC.irv import apply_statewide_primary_adjustment, run_irv_all
from SRC.loaders import (
    load_baseline_primary_by_state,
    load_baseline_results_by_seat,
    load_params,
    load_partisan_vote_index,
    load_preference_matrices,
    load_seat_metadata,
)
from SRC.senate_scenario import DEFAULT_HOUSE_PRIMARY, project_chamber


def party_style(value):
    for party, label in PARTY_LABELS.items():
        if value in {party, label}:
            colours = PARTY_COLOURS[party]
            return f"background-color: {colours['bg']}; color: {colours['text']}; font-weight: bold;"
    return ""


@st.cache_data(show_spinner="Running House and Senate models...")
def run_dashboard(target_items):
    targets = dict(target_items)
    seats = load_seat_metadata()
    matrices = load_preference_matrices()
    params = load_params()
    baseline_primary = load_baseline_primary_by_state()
    baseline_results = load_baseline_results_by_seat()
    pvi = load_partisan_vote_index(params)
    adjusted = apply_statewide_primary_adjustment(
        seats, targets, pvi, params=params,
        baseline_results_by_seat=baseline_results,
        baseline_primary_by_state=baseline_primary,
    )
    if float(params.get("scalars", {}).get("USE_CANDIDATE_LEVEL_IND_IRV", 1.0)) >= 0.5:
        house, _ = run_candidate_irv_all(adjusted, matrices, params, load_candidate_irv_evidence(), apply_calibration=True)
    else:
        house, _ = run_irv_all(adjusted, matrices, params, apply_calibration=True)
    return house["winner"].value_counts().to_dict(), project_chamber(targets)


st.title("Federal Election Dashboard")
st.subheader("Scenario Inputs")
cols = st.columns(len(PARTIES))
targets = {}
for col, party in zip(cols, PARTIES):
    with col:
        targets[party] = st.number_input(
            party, min_value=0.0, max_value=100.0,
            value=float(st.session_state.get(f"primary_{party}", DEFAULT_HOUSE_PRIMARY[party])),
            step=1.0, format="%.2f", key=f"primary_{party}",
        )

house_seats, senate = run_dashboard(tuple(sorted(targets.items())))
left, right = st.columns(2)
with left:
    st.subheader("House")
    house_df = pd.DataFrame([
        {"Party": PARTY_LABELS[party], "Seats": house_seats.get(party, 0)} for party in PARTIES
    ])
    st.dataframe(house_df.style.map(party_style, subset=["Party"]), width="stretch", hide_index=True)
with right:
    st.subheader("Senate")
    senate_df = pd.DataFrame([
        {"Party": PARTY_LABELS[party], "Seats": senate["chamber_seats"][party]} for party in PARTIES
    ])
    st.dataframe(senate_df.style.map(party_style, subset=["Party"]), width="stretch", hide_index=True)

alp_house = house_seats.get("ALP", 0)
lnp_house = house_seats.get("LNP", 0)
st.subheader("Government Position")
if alp_house >= 76:
    st.success(f"Labor majority government: {alp_house} House seats")
elif lnp_house >= 76:
    st.success(f"Coalition majority government: {lnp_house} House seats")
else:
    leader = "Labor" if alp_house >= lnp_house else "Coalition"
    st.warning(f"Hung House. {leader} is the largest bloc; 76 seats are required for a majority.")
