from __future__ import annotations

import pandas as pd

from .constants import PARTIES
from .preference_engine import get_preference_weights


def run_irv_for_seat(
    seat_row: pd.Series,
    matrix_info: dict | None,
    params: dict,
    apply_calibration: bool = True,
) -> tuple[dict, list[dict]]:
    division = seat_row["division"]
    div_key = seat_row.get("division_key", division)
    state = (matrix_info or {}).get("state", "")
    matrix = (matrix_info or {}).get("matrix", {})
    seat_flows = (matrix_info or {}).get("seat_flows", {})

    votes = {party: float(seat_row.get(party, 0.0) or 0.0) for party in PARTIES}
    total = sum(votes.values())
    if total > 0:
        votes = {party: value / total for party, value in votes.items()}

    alive = {party for party, value in votes.items() if value > 0}
    trace = []
    round_no = 1

    while len(alive) > 2:
        eliminated = min(alive, key=lambda party: (votes.get(party, 0.0), party))
        alive_after = sorted(alive - {eliminated})
        aec_row = matrix.get(eliminated, {})

        weights, diagnostic = get_preference_weights(
            elim_party=eliminated,
            alive_parties=alive_after,
            aec_row=aec_row,
            params=params,
            apply_calibration=apply_calibration,
            seat_state=state or "NAT",
            division_key=div_key,
            seat_flows=seat_flows,
            aec_row_party=eliminated,
        )

        transfer = votes.get(eliminated, 0.0)

        trace.append(
            {
                "round": round_no,
                "division": division,
                "eliminated": eliminated,
                "transfer": transfer,
                "alive_after": "+".join(alive_after),
                "basis": diagnostic["basis"],
                "coverage": diagnostic["coverage"],
                "anchor_weight": diagnostic["anchor_weight"],
                "missing": "+".join(diagnostic["missing"]),
                **{party: votes.get(party, 0.0) for party in PARTIES},
                **{f"{party}_flow": weights.get(party, 0.0) for party in PARTIES},
            }
        )

        votes[eliminated] = 0.0
        for party in alive_after:
            votes[party] = votes.get(party, 0.0) + transfer * weights.get(party, 0.0)

        alive = set(alive_after)
        round_no += 1

    final_total = sum(votes[p] for p in alive)
    final = sorted(
        alive,
        key=lambda party: votes.get(party, 0.0),
        reverse=True,
    )
    winner = final[0]
    runner_up = final[1] if len(final) > 1 else ""
    winner_pct = votes[winner] / final_total if final_total > 0 else 0.0
    runner_up_pct = votes[runner_up] / final_total if runner_up and final_total > 0 else 0.0

    result = {
        "division": division,
        "division_key": seat_row.get("division_key", division),
        "state": state,
        "classification": seat_row.get("classification", ""),
        "held_by": seat_row.get("held_by", ""),
        "winner": winner,
        "runner_up": runner_up,
        "winner_pct": winner_pct,
        "runner_up_pct": runner_up_pct,
        "final_two": "+".join(sorted(alive)),
        "elimination_order": ">".join(row["eliminated"] for row in trace),
        **{f"{party}_primary": float(seat_row.get(party, 0.0) or 0.0) for party in PARTIES},
    }

    for party in PARTIES:
        result[f"{party}_final"] = votes.get(party, 0.0) / final_total if final_total > 0 else 0.0

    alp_lnp = run_forced_pair(
        seat_row,
        matrix_info,
        params,
        pair=("ALP", "LNP"),
        apply_calibration=apply_calibration,
    )
    alp_on = run_forced_pair(
        seat_row,
        matrix_info,
        params,
        pair=("ALP", "ON"),
        apply_calibration=apply_calibration,
    )

    result["ALP_2PP"] = alp_lnp["ALP"]
    result["LNP_2PP"] = alp_lnp["LNP"]
    result["ALP_ON_2CP"] = alp_on["ALP"]
    result["ON_ALP_2CP"] = alp_on["ON"]

    return result, trace


def run_forced_pair(
    seat_row: pd.Series,
    matrix_info: dict | None,
    params: dict,
    pair: tuple[str, str],
    apply_calibration: bool = True,
) -> dict[str, float]:
    state = (matrix_info or {}).get("state", "")
    div_key = seat_row.get("division_key", seat_row.get("division", ""))
    matrix = (matrix_info or {}).get("matrix", {})
    seat_flows = (matrix_info or {}).get("seat_flows", {})
    pair_set = set(pair)

    votes = {party: float(seat_row.get(party, 0.0) or 0.0) for party in PARTIES}
    total = sum(votes.values())
    if total > 0:
        votes = {party: value / total for party, value in votes.items()}

    alive = {party for party in PARTIES if votes.get(party, 0.0) > 0 or party in pair_set}

    while any(party not in pair_set for party in alive):
        eliminable = [party for party in alive if party not in pair_set]
        eliminated = min(eliminable, key=lambda party: (votes.get(party, 0.0), party))
        alive_after = sorted(alive - {eliminated})
        aec_row = matrix.get(eliminated, {})

        weights, _ = get_preference_weights(
            elim_party=eliminated,
            alive_parties=alive_after,
            aec_row=aec_row,
            params=params,
            apply_calibration=apply_calibration,
            seat_state=state or "NAT",
            division_key=div_key,
            seat_flows=seat_flows,
            aec_row_party=eliminated,
        )

        transfer = votes.get(eliminated, 0.0)
        votes[eliminated] = 0.0
        for party in alive_after:
            votes[party] = votes.get(party, 0.0) + transfer * weights.get(party, 0.0)

        alive = set(alive_after)

    pair_total = sum(votes.get(party, 0.0) for party in pair)
    if pair_total <= 0:
        return {party: 0.0 for party in pair}

    return {party: votes.get(party, 0.0) / pair_total for party in pair}


def run_irv_all(
    seats: pd.DataFrame,
    matrices: dict[str, dict],
    params: dict,
    apply_calibration: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    results = []
    traces = []

    for _, row in seats.iterrows():
        result, trace = run_irv_for_seat(
            row,
            matrices.get(row.get("division_key", row["division"])),
            params,
            apply_calibration=apply_calibration,
        )
        results.append(result)
        traces.extend(trace)

    return pd.DataFrame(results), pd.DataFrame(traces)


def apply_statewide_primary_adjustment(
    seats: pd.DataFrame,
    targets: dict[str, float],
    partisan_vote_index: pd.DataFrame | None = None,
    iterations: int = 8,
) -> pd.DataFrame:
    adjusted = seats.copy()

    target_total = sum(targets.values())
    target_shares = {
        party: (targets.get(party, 0.0) / target_total if target_total > 0 else 0.0)
        for party in PARTIES
    }

    if partisan_vote_index is not None and not partisan_vote_index.empty:
        pvi = partisan_vote_index.set_index("division_key")
        for idx, row in adjusted.iterrows():
            div_key = row.get("division_key")
            if div_key not in pvi.index:
                continue

            raw_values = {}
            for party in PARTIES:
                index = float(pvi.at[div_key, party]) if party in pvi.columns else 0.0
                raw_values[party] = target_shares[party] * max(index, 0.0)

            raw_total = sum(raw_values.values())
            if raw_total > 0:
                for party in PARTIES:
                    adjusted.at[idx, party] = raw_values[party] / raw_total

    for _ in range(iterations):
        current_totals = {party: adjusted[party].sum() for party in PARTIES}
        current_total = sum(current_totals.values())

        for party in PARTIES:
            current_share = current_totals[party] / current_total if current_total > 0 else 0.0
            multiplier = target_shares[party] / current_share if current_share > 0 else 1.0
            adjusted[party] = adjusted[party] * multiplier

        row_totals = adjusted[PARTIES].sum(axis=1)
        for party in PARTIES:
            adjusted[party] = adjusted[party] / row_totals.where(row_totals > 0, 1.0)

    return adjusted
