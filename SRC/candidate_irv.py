from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pandas as pd

from .constants import PARTIES
from .irv import run_irv_for_seat
from .preference_engine import get_preference_weights
from .reliability import assess_reliability


ROOT = Path(__file__).resolve().parents[1]
CLASSIFICATION_PATH = ROOT / "data" / "raw" / "CANDIDATE_CLASSIFICATION.csv"
ROUNDS_PATH = ROOT / "data" / "derived" / "AEC_CANDIDATE_ROUNDS_LONG.csv"
TRANSFERS_PATH = ROOT / "data" / "derived" / "AEC_CANDIDATE_TRANSFERS_LONG.csv"


def _division_key(value: object) -> str:
    return str(value or "").replace("*", "").strip().upper()


def _candidate_entity(candidate_id: object) -> str:
    return f"IND:{int(float(candidate_id))}"


def _entity_category(entity: str) -> str:
    return "IND" if entity.startswith("IND:") else entity


def load_candidate_irv_evidence() -> dict:
    candidates = pd.read_csv(CLASSIFICATION_PATH)
    candidates["division_key"] = candidates["Electorate"].map(_division_key)
    candidates["CandidateID"] = pd.to_numeric(candidates["CandidateID"], errors="coerce")
    candidates["PrimaryVotes"] = pd.to_numeric(candidates["PrimaryVotes"], errors="coerce").fillna(0.0)
    candidates = candidates[candidates["CandidateID"].notna()].copy()
    candidates["CandidateID"] = candidates["CandidateID"].astype(int)

    roster = {}
    candidate_lookup = {}
    for division_key, group in candidates.groupby("division_key"):
        records = []
        for _, row in group.iterrows():
            record = {
                "candidate_id": int(row["CandidateID"]),
                "candidate_name": str(row.get("CandidateName", "") or ""),
                "category": str(row.get("ModelCategory", "") or "").strip().upper(),
                "subtype": str(row.get("CandidateSubtype", "") or ""),
                "primary_votes": float(row["PrimaryVotes"]),
                "elected": str(row.get("Elected", "") or "").strip().upper() == "Y",
            }
            records.append(record)
            candidate_lookup[(division_key, record["candidate_id"])] = record
        roster[division_key] = records

    rounds = pd.read_csv(ROUNDS_PATH)
    rounds["division_key"] = rounds["Electorate"].map(_division_key)
    eliminated_rounds = rounds[rounds["IsExcludedThisCount"].fillna(False).astype(bool)].copy()

    transfers = pd.read_csv(TRANSFERS_PATH)
    transfers["division_key"] = transfers["Electorate"].map(_division_key)
    transfer_groups = {
        (key, int(candidate_id), int(count)): group
        for (key, candidate_id, count), group in transfers.groupby(
            ["division_key", "EliminatedCandidateID", "CountNumber"]
        )
    }

    exact_transfers = {}
    candidate_profiles = {}
    for _, row in eliminated_rounds.iterrows():
        key = row["division_key"]
        candidate_id = int(row["CandidateID"])
        count = int(row["CountNumber"])
        group = transfer_groups.get((key, candidate_id, count))
        if group is None or group.empty:
            continue

        alive_ids = {
            int(value)
            for value in str(row.get("AliveCandidateIDsAfter", "") or "").split(">")
            if value.strip().isdigit()
        }
        alive_entities = set()
        for alive_id in alive_ids:
            record = candidate_lookup.get((key, alive_id))
            if not record or record["category"] not in PARTIES:
                continue
            alive_entities.add(
                _candidate_entity(alive_id) if record["category"] == "IND" else record["category"]
            )

        distribution = defaultdict(float)
        for _, transfer in group.iterrows():
            recipient_id = int(transfer["RecipientCandidateID"])
            record = candidate_lookup.get((key, recipient_id))
            if not record or record["category"] not in PARTIES:
                continue
            entity = (
                _candidate_entity(recipient_id)
                if record["category"] == "IND"
                else record["category"]
            )
            distribution[entity] += float(transfer.get("TransferVotes", 0.0) or 0.0)

        total = sum(distribution.values())
        if total <= 0:
            continue
        normalised = {entity: value / total for entity, value in distribution.items()}
        exact_transfers[(key, candidate_id, frozenset(alive_entities))] = normalised
        candidate_profiles[(key, candidate_id)] = normalised

    return {
        "roster": roster,
        "exact_transfers": exact_transfers,
        "candidate_profiles": candidate_profiles,
    }


def _normalise(values: dict[str, float], alive: set[str]) -> dict[str, float]:
    filtered = {entity: max(float(values.get(entity, 0.0) or 0.0), 0.0) for entity in alive}
    total = sum(filtered.values())
    if total <= 0:
        return {entity: 1.0 / len(alive) for entity in alive}
    return {entity: value / total for entity, value in filtered.items()}


def _project_candidate_profile(
    profile: dict[str, float],
    alive: set[str],
    votes: dict[str, float],
) -> dict[str, float] | None:
    projected = defaultdict(float)
    alive_by_category = defaultdict(list)
    for entity in alive:
        alive_by_category[_entity_category(entity)].append(entity)

    for recipient, share in profile.items():
        if recipient in alive:
            projected[recipient] += share
            continue
        category = _entity_category(recipient)
        recipients = alive_by_category.get(category, [])
        if not recipients:
            continue
        denominator = sum(votes.get(entity, 0.0) for entity in recipients)
        for entity in recipients:
            fraction = votes.get(entity, 0.0) / denominator if denominator > 0 else 1.0 / len(recipients)
            projected[entity] += share * fraction

    if sum(projected.values()) <= 0:
        return None
    return _normalise(projected, alive)


def _split_category_weights(
    category_weights: dict[str, float],
    alive: set[str],
    votes: dict[str, float],
) -> dict[str, float]:
    result = defaultdict(float)
    by_category = defaultdict(list)
    for entity in alive:
        by_category[_entity_category(entity)].append(entity)
    for category, share in category_weights.items():
        recipients = by_category.get(category, [])
        if not recipients:
            continue
        denominator = sum(votes.get(entity, 0.0) for entity in recipients)
        for entity in recipients:
            fraction = votes.get(entity, 0.0) / denominator if denominator > 0 else 1.0 / len(recipients)
            result[entity] += share * fraction
    return _normalise(result, alive)


def run_candidate_irv_for_seat(
    seat_row: pd.Series,
    matrix_info: dict | None,
    params: dict,
    evidence: dict,
    apply_calibration: bool = True,
) -> tuple[dict, list[dict]]:
    base_result, base_trace = run_irv_for_seat(
        seat_row,
        matrix_info,
        params,
        apply_calibration=apply_calibration,
    )
    key = str(seat_row.get("division_key", ""))
    roster = evidence["roster"].get(key, [])
    independent_candidates = [record for record in roster if record["category"] == "IND"]
    if len(independent_candidates) <= 1:
        base_result["candidate_mode"] = False
        base_result["winner_candidate"] = ""
        return base_result, base_trace

    votes = {
        party: float(seat_row.get(party, 0.0) or 0.0)
        for party in PARTIES
        if party != "IND" and float(seat_row.get(party, 0.0) or 0.0) > 0
    }
    ind_total = float(seat_row.get("IND", 0.0) or 0.0)
    roster_total = sum(record["primary_votes"] for record in independent_candidates)
    names = {}
    ids = {}
    for record in independent_candidates:
        entity = _candidate_entity(record["candidate_id"])
        share = record["primary_votes"] / roster_total if roster_total > 0 else 1.0 / len(independent_candidates)
        votes[entity] = ind_total * share
        names[entity] = record["candidate_name"]
        ids[entity] = record["candidate_id"]

    total = sum(votes.values())
    votes = {entity: value / total for entity, value in votes.items()}
    alive = {entity for entity, value in votes.items() if value > 0}
    trace = []
    round_no = 1
    matrix = (matrix_info or {}).get("matrix", {})
    seat_flows = (matrix_info or {}).get("seat_flows", {})
    seat_flow_evidence = (matrix_info or {}).get("seat_flow_evidence", {})

    while len(alive) > 2:
        eliminated = min(alive, key=lambda entity: (votes.get(entity, 0.0), entity))
        alive_after = alive - {eliminated}
        basis = "category_preference"
        weights = None

        if eliminated.startswith("IND:"):
            candidate_id = ids[eliminated]
            exact = evidence["exact_transfers"].get(
                (key, candidate_id, frozenset(alive_after))
            )
            if exact:
                weights = _normalise(exact, alive_after)
                basis = "exact_candidate_transfer"
            else:
                profile = evidence["candidate_profiles"].get((key, candidate_id))
                if profile:
                    weights = _project_candidate_profile(profile, alive_after, votes)
                    if weights:
                        basis = "projected_candidate_transfer"

        if weights is None:
            eliminated_category = _entity_category(eliminated)
            alive_categories = sorted({_entity_category(entity) for entity in alive_after})
            category_weights, diagnostic = get_preference_weights(
                elim_party=eliminated_category,
                alive_parties=alive_categories,
                aec_row=matrix.get(eliminated_category, {}),
                params=params,
                apply_calibration=apply_calibration,
                seat_state=(matrix_info or {}).get("state", "NAT"),
                division_key=key,
                seat_flows=seat_flows,
                seat_flow_evidence=seat_flow_evidence,
                aec_row_party=eliminated_category,
                seat_class=str(seat_row.get("classification", "") or ""),
            )
            weights = _split_category_weights(category_weights, alive_after, votes)
            basis = diagnostic.get("basis", basis)
            diagnostic.update(assess_reliability(diagnostic))

        transfer = votes[eliminated]
        trace.append(
            {
                "round": round_no,
                "division": seat_row["division"],
                "division_key": key,
                "eliminated": _entity_category(eliminated),
                "eliminated_candidate": names.get(eliminated, ""),
                "eliminated_entity": eliminated,
                "transfer": transfer,
                "alive_after": "+".join(sorted(_entity_category(entity) for entity in alive_after)),
                "alive_candidates_after": "+".join(sorted(names.get(entity, entity) for entity in alive_after)),
                "basis": basis,
            }
        )
        votes[eliminated] = 0.0
        for entity in alive_after:
            votes[entity] += transfer * weights.get(entity, 0.0)
        alive = alive_after
        round_no += 1

    final = sorted(alive, key=lambda entity: votes[entity], reverse=True)
    final_total = sum(votes[entity] for entity in final)
    winner_entity, runner_entity = final[0], final[1]
    base_result.update(
        {
            "candidate_mode": True,
            "winner": _entity_category(winner_entity),
            "runner_up": _entity_category(runner_entity),
            "winner_candidate": names.get(winner_entity, ""),
            "runner_up_candidate": names.get(runner_entity, ""),
            "winner_pct": votes[winner_entity] / final_total,
            "runner_up_pct": votes[runner_entity] / final_total,
            "final_two": "+".join(sorted([_entity_category(winner_entity), _entity_category(runner_entity)])),
            "candidate_elimination_order": ">".join(row["eliminated_entity"] for row in trace),
        }
    )
    return base_result, trace


def run_candidate_irv_all(
    seats: pd.DataFrame,
    matrices: dict[str, dict],
    params: dict,
    evidence: dict,
    apply_calibration: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    results = []
    traces = []
    for _, row in seats.iterrows():
        result, trace = run_candidate_irv_for_seat(
            row,
            matrices.get(row.get("division_key", row["division"])),
            params,
            evidence,
            apply_calibration,
        )
        results.append(result)
        traces.extend(trace)
    return pd.DataFrame(results), pd.DataFrame(traces)
