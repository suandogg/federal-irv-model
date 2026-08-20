import csv

import pandas as pd
import streamlit as st

from SRC.constants import PARTIES, PARTY_COLOURS, PARTY_LABELS, STATE_ORDER
from SRC.senate_scenario import DEFAULT_HOUSE_PRIMARY, PROCESSED, project_chamber


def party_style(value):
    for party, label in PARTY_LABELS.items():
        if value in {party, label}:
            colours = PARTY_COLOURS[party]
            return f"background-color: {colours['bg']}; color: {colours['text']}; font-weight: bold;"
    return ""


@st.cache_data(show_spinner="Running candidate-level Senate counts...")
def run_senate(target_items):
    return project_chamber(dict(target_items))


def baseline_chamber():
    with (PROCESSED / "senate_current_chamber_by_state.csv").open(newline="") as handle:
        row = next(row for row in csv.DictReader(handle) if row["state"] == "National")
    return {party: int(row[f"{party}_seats"]) for party in PARTIES}


st.title("Federal Senate Model")
st.subheader("Scenario Inputs")
cols = st.columns(len(PARTIES))
targets = {}
for col, party in zip(cols, PARTIES):
    with col:
        targets[party] = st.number_input(
            party,
            min_value=0.0,
            max_value=100.0,
            value=float(st.session_state.get(f"primary_{party}", DEFAULT_HOUSE_PRIMARY[party])),
            step=1.0,
            format="%.2f",
            key=f"primary_{party}",
        )

total = sum(targets.values())
st.markdown(f"**Primary total: {total:.2f}%**")
if abs(total - 100) > 0.01:
    st.warning("Primary votes should add to 100%. Senate state targets will be normalised internally.")

selected_state = st.selectbox("View", ["National", *STATE_ORDER], key="senate_state")
result = run_senate(tuple(sorted(targets.items())))
state_index = {row["state"]: row for row in result["states"]}
baseline = baseline_chamber()

if selected_state == "National":
    st.subheader("Projected Senate Chamber")
    summary = pd.DataFrame([
        {
            "Party": PARTY_LABELS[party],
            "Seats": result["chamber_seats"][party],
            "Change from election baseline": result["chamber_seats"][party] - baseline[party],
        }
        for party in PARTIES
    ])
    st.dataframe(summary.style.map(party_style, subset=["Party"]), width="stretch", hide_index=True)

    st.subheader("State Cohort Projections")
    rows = []
    for state in STATE_ORDER:
        projection = state_index[state]
        rows.append({"State": state, **{party: projection["projected_seats"][party] for party in PARTIES}})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
else:
    projection = state_index[selected_state]
    st.subheader(f"{selected_state} Senate Primary Vote")
    primary = pd.DataFrame([
        {"Party": PARTY_LABELS[party], "Projected Primary %": projection["primary_targets"][party]}
        for party in PARTIES
    ])
    st.dataframe(
        primary.style.map(party_style, subset=["Party"]),
        width="stretch",
        hide_index=True,
        column_config={"Projected Primary %": st.column_config.NumberColumn(format="%.2f%%")},
    )

    st.subheader(f"{selected_state} Elected Cohort")
    seats = pd.DataFrame([
        {"Party": PARTY_LABELS[party], "Seats": projection["projected_seats"][party]}
        for party in PARTIES
    ])
    st.dataframe(seats.style.map(party_style, subset=["Party"]), width="stretch", hide_index=True)

    st.subheader("Projected Elected Candidates")
    elected = pd.DataFrame({
        "Order": range(1, len(projection["elected_candidates"]) + 1),
        "Candidate": [candidate.partition(":")[2] for candidate in projection["elected_candidates"]],
    })
    st.dataframe(elected, width="stretch", hide_index=True)

    with st.expander("Count trace"):
        st.dataframe(pd.DataFrame(projection["trace"]), width="stretch", hide_index=True)
