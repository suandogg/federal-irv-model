import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

import pandas as pd
import streamlit as st

from SRC.constants import PARTIES, PARTY_COLOURS, PARTY_LABELS, STATE_ORDER
from SRC.irv import apply_statewide_primary_adjustment, run_irv_all
from SRC.loaders import (
    load_baseline_primary_by_state,
    load_baseline_results_by_seat,
    load_district_2cp_swing,
    load_params,
    load_preference_matrices,
    load_projected_2cp,
    load_seat_metadata,
    load_sheet_baseline_results,
)


BASELINE_2PP = {
    "National": {"ALP": 55.28, "LNP": 44.72},
    "NSW": {"ALP": 55.27, "LNP": 44.73},
    "VIC": {"ALP": 56.30, "LNP": 43.70},
    "QLD": {"ALP": 49.42, "LNP": 50.58},
    "WA": {"ALP": 55.84, "LNP": 44.16},
    "SA": {"ALP": 59.19, "LNP": 40.81},
    "TAS": {"ALP": 63.34, "LNP": 36.66},
    "ACT": {"ALP": 72.49, "LNP": 27.51},
    "NT": {"ALP": 53.51, "LNP": 46.49},
}

DEFAULT_SCENARIO_PRIMARY = {
    "ALP": 34.56,
    "LNP": 31.82,
    "GRN": 12.20,
    "ON": 6.40,
    "IND": 7.27,
    "OTH": 7.75,
}


def party_cell_style(value):
    parts = str(value).split()
    if not parts:
        return ""

    party = parts[0]

    if party not in PARTY_COLOURS:
        for code, label in PARTY_LABELS.items():
            if value == label:
                party = code
                break

    if party not in PARTY_COLOURS:
        return ""

    colours = PARTY_COLOURS[party]
    return (
        f"background-color: {colours['bg']}; "
        f"color: {colours['text']}; "
        "font-weight: bold;"
    )


def blackout_cell(value):
    return "background-color: black; color: black;"


def placement_cell_style(value):
    party = str(value).strip()

    if party not in PARTY_COLOURS:
        return ""

    colours = PARTY_COLOURS[party]
    return (
        f"background-color: {colours['bg']}; "
        "color: transparent;"
    )


def elimination_position(row, position):
    order = [p for p in str(row.get("elimination_order", "")).split(">") if p]
    mapping = {
        "6th": 0,
        "5th": 1,
        "4th": 2,
        "3rd": 3,
    }
    idx = mapping[position]
    return order[idx] if len(order) > idx else ""


@st.cache_data
def load_static_inputs():
    seats = load_seat_metadata()
    matrices = load_preference_matrices()
    params = load_params()
    projected_2cp = load_projected_2cp()
    sheet_baseline_results = load_sheet_baseline_results()
    baseline_primary_by_state = load_baseline_primary_by_state()
    baseline_results_by_seat = load_baseline_results_by_seat()
    district_2cp_swing = load_district_2cp_swing()
    return (
        seats,
        matrices,
        params,
        projected_2cp,
        sheet_baseline_results,
        baseline_primary_by_state,
        baseline_results_by_seat,
        district_2cp_swing,
    )


def aggregate_primary(seats):
    totals = {party: seats[party].sum() for party in PARTIES}
    total = sum(totals.values())
    return {party: totals[party] / total * 100 if total > 0 else 0.0 for party in PARTIES}


def is_default_scenario(targets, defaults):
    return all(abs(float(targets[party]) - round(defaults[party], 2)) < 0.005 for party in PARTIES)


def apply_sheet_baseline_results(results, sheet_results):
    if sheet_results.empty:
        return results

    merged = results.merge(sheet_results, on="division_key", how="left")
    has_sheet = merged["sheet_winner"].notna()
    for column, sheet_column in [
        ("winner", "sheet_winner"),
        ("runner_up", "sheet_runner_up"),
        ("winner_pct", "sheet_winner_pct"),
        ("runner_up_pct", "sheet_runner_up_pct"),
        ("final_two", "sheet_final_two"),
    ]:
        merged.loc[has_sheet, column] = merged.loc[has_sheet, sheet_column]

    for party in PARTIES:
        final_col = f"{party}_final"
        sheet_col = f"sheet_{party}_final"
        merged.loc[has_sheet, final_col] = merged.loc[has_sheet, sheet_col]

    drop_cols = [
        col for col in merged.columns
        if col.startswith("sheet_") or col == "division_y"
    ]
    merged = merged.drop(columns=drop_cols)
    if "division_x" in merged.columns:
        merged = merged.rename(columns={"division_x": "division"})
    return merged


def add_district_2cp_swing(results, sheet_results, district_swings):
    if sheet_results.empty or district_swings.empty:
        results["district_2cp_swing"] = pd.NA
        return results

    cols = [
        "division_key",
        "sheet_winner",
        "sheet_winner_pct",
        "sheet_final_two",
    ]
    merged = (
        results
        .merge(sheet_results[cols], on="division_key", how="left")
        .merge(district_swings, on="division_key", how="left")
    )

    comparable = (
        merged["district_2cp_swing"].notna()
        & (merged["winner"] == merged["sheet_winner"])
        & (merged["final_two"] == merged["sheet_final_two"])
    )
    merged.loc[comparable, "district_2cp_swing"] = (
        merged.loc[comparable, "district_2cp_swing"]
        + (
            merged.loc[comparable, "winner_pct"]
            - merged.loc[comparable, "sheet_winner_pct"]
        ) * 100
    )
    merged.loc[~comparable, "district_2cp_swing"] = pd.NA

    return merged.drop(
        columns=[
            "sheet_winner",
            "sheet_winner_pct",
            "sheet_final_two",
        ],
        errors="ignore",
    )


def trace_baseline_stage(row):
    alive_count = sum(1 for party in PARTIES if float(row.get(party, 0.0) or 0.0) > 1e-9)
    if alive_count <= 2:
        return "2CP"
    if alive_count == 3:
        return "3CP"
    return "primary"


def add_trace_swings(seat_trace, selected_division, baseline_results_by_seat):
    seat_trace = seat_trace.copy()
    seat_trace["baseline_stage"] = seat_trace.apply(trace_baseline_stage, axis=1)

    baseline = baseline_results_by_seat[
        baseline_results_by_seat["division"].eq(selected_division)
    ]
    if baseline.empty:
        for party in PARTIES:
            seat_trace[f"{party}_swing"] = pd.NA
        return seat_trace

    baseline_row = baseline.iloc[0]
    for party in PARTIES:
        swing_col = f"{party}_swing"
        seat_trace[swing_col] = seat_trace.apply(
            lambda row, p=party: (
                row[p] - baseline_row.get(f"{p}_{row['baseline_stage']}", 0.0)
                if p in row and pd.notna(row[p])
                else pd.NA
            ),
            axis=1,
        )
    return seat_trace


def render_table(df):
    st.dataframe(
        df.style.map(party_cell_style, subset=[c for c in ["Party", "winner", "runner_up"] if c in df.columns]),
        width="stretch",
        hide_index=True,
    )


def render_result_table(df):
    styled = (
        df.style
        .map(party_cell_style, subset=[c for c in ["held_by", "winner", "runner_up"] if c in df.columns])
        .map(placement_cell_style, subset=[c for c in ["2nd", "3rd", "4th", "5th", "6th"] if c in df.columns])
    )
    st.dataframe(
        styled,
        width="stretch",
        hide_index=True,
        column_config={
            "Winner 2CP %": st.column_config.NumberColumn(format="%.2f%%"),
            "Runner-up 2CP %": st.column_config.NumberColumn(format="%.2f%%"),
            "2CP Swing %": st.column_config.NumberColumn(format="%.2f%%"),
        },
    )


st.set_page_config(page_title="Federal IRV Model", layout="wide")
st.title("Federal IRV Election Model")

(
    seats,
    matrices,
    params,
    projected_2cp,
    sheet_baseline_results,
    baseline_primary_by_state,
    baseline_results_by_seat,
    district_2cp_swing,
) = load_static_inputs()
raw_primary = aggregate_primary(seats)
default_primary = DEFAULT_SCENARIO_PRIMARY

st.subheader("Scenario Inputs")

if st.button("Reset scenario inputs"):
    for party in PARTIES:
        st.session_state[f"primary_{party}"] = round(default_primary[party], 2)
    st.rerun()

cols = st.columns(len(PARTIES))
targets = {}
for col, party in zip(cols, PARTIES):
    with col:
        targets[party] = st.number_input(
            party,
            min_value=0.0,
            max_value=100.0,
            value=round(default_primary[party], 2),
            step=1.0,
            format="%.2f",
            key=f"primary_{party}",
        )

total_primary = sum(targets.values())
st.markdown(f"**Primary total: {total_primary:.2f}%**")
if abs(total_primary - 100.0) > 0.01:
    st.warning("Primary votes should add to 100%. The model will normalise internally.")

selected_state = st.selectbox("View", ["National", *STATE_ORDER], index=0)
apply_calibration = st.checkbox("Apply supported-AEC calibration", value=True)

adjusted_seats = apply_statewide_primary_adjustment(seats, targets)
results_df, traces_df = run_irv_all(adjusted_seats, matrices, params, apply_calibration=apply_calibration)
baseline_exact = apply_calibration and is_default_scenario(targets, raw_primary)
if baseline_exact:
    results_df = apply_sheet_baseline_results(results_df, sheet_baseline_results)
results_df = add_district_2cp_swing(results_df, sheet_baseline_results, district_2cp_swing)

if selected_state != "National":
    view_results = results_df[results_df["state"] == selected_state].copy()
    view_seats = adjusted_seats[adjusted_seats["division"].isin(view_results["division"])].copy()
else:
    view_results = results_df.copy()
    view_seats = adjusted_seats.copy()

st.subheader(f"{selected_state} Primary Vote")
view_primary = aggregate_primary(view_seats)
baseline_primary = baseline_primary_by_state.get(
    selected_state,
    baseline_primary_by_state.get("National", raw_primary),
)
primary_df = pd.DataFrame(
    [
        {
            "Party": PARTY_LABELS[party],
            "Primary Vote %": view_primary[party],
            "Swing %": view_primary[party] - baseline_primary.get(party, 0.0),
        }
        for party in PARTIES
    ]
)
st.dataframe(
    primary_df.style.map(party_cell_style, subset=["Party"]),
    width="stretch",
    hide_index=True,
    column_config={
        "Primary Vote %": st.column_config.NumberColumn(format="%.2f%%"),
        "Swing %": st.column_config.NumberColumn(format="%.2f%%"),
    },
)

st.subheader(f"{selected_state} Summary")
seat_counts = view_results["winner"].value_counts().to_dict()
baseline_2pp = BASELINE_2PP.get(selected_state, BASELINE_2PP["National"])
alp_2pp = view_results["ALP_2PP"].mean() * 100
lnp_2pp = view_results["LNP_2PP"].mean() * 100

summary_df = pd.DataFrame(
    [
        {
            "Party": PARTY_LABELS["ALP"],
            "2PP %": alp_2pp,
            "2PP Swing %": alp_2pp - baseline_2pp["ALP"],
            "Seats": seat_counts.get("ALP", 0),
        },
        {
            "Party": PARTY_LABELS["LNP"],
            "2PP %": lnp_2pp,
            "2PP Swing %": lnp_2pp - baseline_2pp["LNP"],
            "Seats": seat_counts.get("LNP", 0),
        },
        *[
            {
                "Party": PARTY_LABELS[party],
                "2PP %": 0.0,
                "2PP Swing %": 0.0,
                "Seats": seat_counts.get(party, 0),
            }
            for party in ["GRN", "ON", "IND", "OTH"]
        ],
    ]
)

summary_style = (
    summary_df.style
    .map(party_cell_style, subset=["Party"])
    .map(
        blackout_cell,
        subset=pd.IndexSlice[
            summary_df.index[2:],
            ["2PP %", "2PP Swing %"]
        ],
    )
)

st.dataframe(
    summary_style,
    width="stretch",
    hide_index=True,
    column_config={
        "2PP %": st.column_config.NumberColumn(format="%.2f%%"),
        "2PP Swing %": st.column_config.NumberColumn(format="%.2f%%"),
    },
)

st.subheader(f"{selected_state} Alternate 2CP")

alp_on_2cp = view_results["ALP_ON_2CP"].mean() * 100
on_alp_2cp = view_results["ON_ALP_2CP"].mean() * 100

alternate_2cp_df = pd.DataFrame(
    [
        {"Party": PARTY_LABELS["ALP"], "2CP %": alp_on_2cp},
        {"Party": PARTY_LABELS["ON"], "2CP %": on_alp_2cp},
    ]
)

st.dataframe(
    alternate_2cp_df.style.map(party_cell_style, subset=["Party"]),
    width="stretch",
    hide_index=True,
    column_config={
        "2CP %": st.column_config.NumberColumn(format="%.2f%%"),
    },
)

st.subheader(f"{selected_state} District Results")
display_cols = [
    "division",
    "state",
    "classification",
    "held_by",
    "division_key",
    "winner",
    "runner_up",
    "winner_pct",
    "runner_up_pct",
    "district_2cp_swing",
    "final_two",
    "elimination_order",
]
display_df = view_results[display_cols].copy()
display_df["Winner 2CP %"] = display_df["winner_pct"] * 100
display_df["Runner-up 2CP %"] = display_df["runner_up_pct"] * 100
display_df["2CP Swing %"] = display_df["district_2cp_swing"]
display_df["2nd"] = display_df["runner_up"]
for position in ["3rd", "4th", "5th", "6th"]:
    display_df[position] = display_df.apply(
        lambda row, pos=position: elimination_position(row, pos),
        axis=1,
    )
display_df = display_df.drop(columns=["winner_pct", "runner_up_pct", "district_2cp_swing"])
display_df = display_df[
    [
        "division",
        "state",
        "classification",
        "held_by",
        "winner",
        "runner_up",
        "Winner 2CP %",
        "Runner-up 2CP %",
        "2CP Swing %",
        "2nd",
        "3rd",
        "4th",
        "5th",
        "6th",
        "final_two",
        "elimination_order",
    ]
]
render_result_table(display_df)

st.subheader(f"{selected_state} Seats Changing Hands")

changes_df = display_df[
    (display_df["held_by"] != "") &
    (display_df["held_by"] != display_df["winner"])
].copy()

render_result_table(changes_df)

st.subheader("Seat Detail")
selected_division = st.selectbox("Select division", sorted(view_results["division"].unique()))

seat_trace = traces_df[traces_df["division"] == selected_division].copy()
for party in PARTIES:
    if party in seat_trace.columns:
        seat_trace[party] = seat_trace[party] * 100
    flow_col = f"{party}_flow"
    if flow_col in seat_trace.columns:
        seat_trace[flow_col] = seat_trace[flow_col] * 100

selected_result = results_df[results_df["division"] == selected_division].iloc[0]
final_trace_row = {
    "round": "Final",
    "eliminated": "",
    "transfer": pd.NA,
    "alive_after": selected_result["final_two"],
    "basis": "final_2cp",
    "coverage": pd.NA,
    "anchor_weight": pd.NA,
    "missing": "",
}
for party in PARTIES:
    final_trace_row[party] = selected_result.get(f"{party}_final", 0.0) * 100
    final_trace_row[f"{party}_flow"] = pd.NA
seat_trace = pd.concat([seat_trace, pd.DataFrame([final_trace_row])], ignore_index=True)
seat_trace = add_trace_swings(seat_trace, selected_division, baseline_results_by_seat)
seat_trace["round"] = seat_trace["round"].astype(str)

trace_columns = [
    "round",
    "eliminated",
    "transfer",
    "alive_after",
    "baseline_stage",
    "basis",
    "coverage",
    "anchor_weight",
    "missing",
    *PARTIES,
    *[f"{party}_swing" for party in PARTIES],
    *[f"{party}_flow" for party in PARTIES],
]
trace_columns = [col for col in trace_columns if col in seat_trace.columns]
st.dataframe(
    seat_trace[trace_columns],
    width="stretch",
    hide_index=True,
    column_config={
        "transfer": st.column_config.NumberColumn(format="%.2f"),
        "coverage": st.column_config.NumberColumn(format="%.2f"),
        "anchor_weight": st.column_config.NumberColumn(format="%.2f"),
        **{party: st.column_config.NumberColumn(format="%.2f%%") for party in PARTIES},
        **{f"{party}_swing": st.column_config.NumberColumn(format="%.2f%%") for party in PARTIES},
        **{f"{party}_flow": st.column_config.NumberColumn(format="%.2f%%") for party in PARTIES},
    },
)
