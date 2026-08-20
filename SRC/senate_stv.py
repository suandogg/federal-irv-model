"""Candidate-level Senate STV replay using AEC formal ballot records."""

from __future__ import annotations

import csv
import io
import math
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw" / "aec"
ELECTION_IDS = {2022: 27966, 2025: 31496}
META_COLUMNS = 6


def _number(value: str) -> int | None:
    value = value.strip()
    return int(value) if value.isdigit() and int(value) > 0 else None


def _valid_prefix(values: list[int | None], minimum: int) -> list[int] | None:
    indexes: dict[int, list[int]] = defaultdict(list)
    for index, value in enumerate(values):
        if value is not None:
            indexes[value].append(index)
    if any(len(indexes[number]) != 1 for number in range(1, minimum + 1)):
        return None
    result = []
    number = 1
    while len(indexes[number]) == 1:
        result.append(indexes[number][0])
        number += 1
    return result


def load_ballot_patterns(year: int, state: str) -> tuple[list[str], Counter[tuple[str, ...]]]:
    """Return candidate labels and compressed formal candidate preference sequences."""
    election_id = ELECTION_IDS[year]
    archive = RAW / str(year) / f"aec-senate-formalpreferences-{election_id}-{state}.zip"
    candidates_path = RAW / str(year) / f"SenateCandidatesDownload-{election_id}.csv"
    with candidates_path.open(newline="", encoding="utf-8-sig") as handle:
        next(handle)
        candidate_count = sum(row["StateAb"] == state for row in csv.DictReader(handle))

    patterns: Counter[tuple[str, ...]] = Counter()
    with zipfile.ZipFile(archive) as zipped:
        with zipped.open(zipped.namelist()[0]) as raw, io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as text:
            reader = csv.reader(text)
            header = next(reader)
            candidate_start = len(header) - candidate_count
            group_headers = header[META_COLUMNS:candidate_start]
            candidate_headers = header[candidate_start:]
            ticket_candidates: dict[str, list[str]] = defaultdict(list)
            for candidate in candidate_headers:
                ticket_candidates[candidate.partition(":")[0].strip()].append(candidate)

            for row in reader:
                atl = [_number(value) for value in row[META_COLUMNS:candidate_start]]
                btl = [_number(value) for value in row[candidate_start:]]
                btl_order = _valid_prefix(btl, 6)
                if btl_order is not None:
                    sequence = tuple(candidate_headers[index] for index in btl_order)
                else:
                    atl_order = _valid_prefix(atl, 1)
                    if atl_order is None:
                        continue
                    expanded = []
                    for index in atl_order:
                        ticket = group_headers[index].partition(":")[0].strip()
                        expanded.extend(ticket_candidates[ticket])
                    sequence = tuple(expanded)
                if sequence:
                    patterns[sequence] += 1
    return candidate_headers, patterns


@dataclass
class Parcel:
    sequence: tuple[str, ...]
    position: int
    papers: int
    value: float


def _next_position(sequence: tuple[str, ...], start: int, continuing: set[str]) -> int | None:
    for index in range(start, len(sequence)):
        if sequence[index] in continuing:
            return index
    return None


def run_stv(candidate_names: list[str], patterns: Counter[tuple[str, ...]], vacancies: int) -> dict:
    formal_papers = sum(patterns.values())
    quota = math.floor(formal_papers / (vacancies + 1)) + 1
    continuing = set(candidate_names)
    elected: list[str] = []
    excluded: list[str] = []
    allocations: dict[str, list[Parcel]] = defaultdict(list)
    exhausted_value = 0.0
    trace: list[dict] = []

    for sequence, papers in patterns.items():
        position = _next_position(sequence, 0, continuing)
        if position is not None:
            allocations[sequence[position]].append(Parcel(sequence, position, papers, 1.0))

    def totals() -> dict[str, float]:
        return {
            candidate: sum(parcel.papers * parcel.value for parcel in allocations[candidate])
            for candidate in continuing
        }

    def transfer(candidate: str, transfer_value: float | None) -> float:
        nonlocal exhausted_value
        moved = 0.0
        parcels = allocations.pop(candidate, [])
        for parcel in parcels:
            value = parcel.value if transfer_value is None else min(parcel.value, transfer_value)
            position = _next_position(parcel.sequence, parcel.position + 1, continuing)
            parcel_value = parcel.papers * value
            if position is None:
                exhausted_value += parcel_value
            else:
                allocations[parcel.sequence[position]].append(
                    Parcel(parcel.sequence, position, parcel.papers, value)
                )
                moved += parcel_value
        return moved

    count = 1
    while len(elected) < vacancies and continuing:
        current = totals()
        vacancies_left = vacancies - len(elected)
        if len(continuing) <= vacancies_left:
            for candidate in sorted(continuing, key=lambda name: (-current[name], name)):
                elected.append(candidate)
                trace.append({"count": count, "action": "elected_remaining", "candidate": candidate, "votes": current[candidate]})
            break

        qualifiers = [candidate for candidate, votes in current.items() if votes >= quota]
        if qualifiers:
            candidate = max(qualifiers, key=lambda name: (current[name], name))
            votes = current[candidate]
            papers = sum(parcel.papers for parcel in allocations[candidate])
            surplus = max(0.0, votes - quota)
            continuing.remove(candidate)
            elected.append(candidate)
            transfer_value = surplus / papers if papers and surplus else 0.0
            moved = transfer(candidate, transfer_value)
            trace.append({
                "count": count, "action": "elected", "candidate": candidate,
                "votes": votes, "surplus": surplus, "transfer_value": transfer_value,
                "transferred": moved,
            })
        else:
            candidate = min(continuing, key=lambda name: (current[name], name))
            votes = current[candidate]
            continuing.remove(candidate)
            excluded.append(candidate)
            moved = transfer(candidate, None)
            trace.append({"count": count, "action": "excluded", "candidate": candidate, "votes": votes, "transferred": moved})
        count += 1

    return {
        "formal_papers": formal_papers,
        "quota": quota,
        "elected": elected[:vacancies],
        "excluded": excluded,
        "exhausted_value": exhausted_value,
        "trace": trace,
    }
