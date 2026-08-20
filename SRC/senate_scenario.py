"""Scenario reweighting and full-chamber Senate projection."""

from __future__ import annotations

import csv
import gzip
from collections import Counter
from pathlib import Path

from .senate_stv import run_stv


ROOT = Path(__file__).resolve().parents[1]
MODEL_DATA = ROOT / "data" / "senate" / "model"
PROCESSED = ROOT / "data" / "senate" / "processed"
STATES = ("NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT")
PARTIES = ("ALP", "LNP", "GRN", "ON", "IND", "OTH")
DEFAULT_HOUSE_PRIMARY = {"ALP": 34.56, "LNP": 31.82, "GRN": 12.20, "ON": 6.40, "IND": 7.27, "OTH": 7.75}


def load_candidate_sample(state: str, year: int = 2025):
    patterns = Counter()
    candidates = set()
    with gzip.open(MODEL_DATA / f"candidate_patterns_{year}_{state}.csv.gz", "rt", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            sequence = tuple(row["preference_sequence"].split(">"))
            patterns[sequence] = float(row["weight"])
            candidates.update(sequence)
    with (MODEL_DATA / f"candidate_map_{year}_{state}.csv").open(newline="", encoding="utf-8") as handle:
        candidate_map = {row["candidate"]: row["canonical_party"] for row in csv.DictReader(handle)}
    return sorted(candidates), patterns, candidate_map


def load_pvi() -> dict[str, dict[str, float]]:
    with (PROCESSED / "senate_pvi_by_state.csv").open(newline="", encoding="utf-8") as handle:
        return {
            row["state"]: {party: float(row[f"{party}_additive_pvi"]) for party in PARTIES}
            for row in csv.DictReader(handle)
        }


def state_primary_targets(national_house_primary: dict[str, float], state: str, pvi: dict[str, dict[str, float]]) -> dict[str, float]:
    raw = {party: max(0.0, float(national_house_primary[party]) + pvi[state][party]) for party in PARTIES}
    total = sum(raw.values())
    return {party: 100 * value / total for party, value in raw.items()}


def reweight_patterns(patterns: Counter, candidate_map: dict[str, str], targets: dict[str, float]) -> Counter:
    formal = sum(patterns.values())
    baseline = Counter()
    for sequence, weight in patterns.items():
        baseline[candidate_map.get(sequence[0], "OTH")] += weight
    scale = {
        party: (formal * targets[party] / 100) / baseline[party] if baseline[party] else 0.0
        for party in PARTIES
    }
    return Counter({
        sequence: weight * scale[candidate_map.get(sequence[0], "OTH")]
        for sequence, weight in patterns.items()
    })


def continuing_seats() -> dict[str, dict[str, int]]:
    result = {state: {party: 0 for party in PARTIES} for state in STATES}
    with (PROCESSED / "senate_elected_seats_by_state.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            state = row["state"]
            if int(row["election_year"]) != 2022 or state not in result or state in {"ACT", "NT"}:
                continue
            result[state] = {party: int(row[f"{party}_seats"]) for party in PARTIES}
    return result


def project_state(national_house_primary: dict[str, float], state: str, pvi: dict[str, dict[str, float]] | None = None) -> dict:
    pvi = pvi or load_pvi()
    candidates, patterns, candidate_map = load_candidate_sample(state)
    targets = state_primary_targets(national_house_primary, state, pvi)
    weighted = reweight_patterns(patterns, candidate_map, targets)
    vacancies = 2 if state in {"ACT", "NT"} else 6
    result = run_stv(candidates, weighted, vacancies)
    projected = Counter(candidate_map.get(candidate, "OTH") for candidate in result["elected"])
    return {
        "state": state,
        "primary_targets": targets,
        "projected_seats": {party: projected[party] for party in PARTIES},
        "elected_candidates": result["elected"],
        "quota": result["quota"],
        "trace": result["trace"],
    }


def project_chamber(national_house_primary: dict[str, float]) -> dict:
    pvi = load_pvi()
    continuing = continuing_seats()
    states = [project_state(national_house_primary, state, pvi) for state in STATES]
    chamber = Counter()
    for result in states:
        state = result["state"]
        for party in PARTIES:
            chamber[party] += result["projected_seats"][party] + continuing[state][party]
    return {"states": states, "chamber_seats": {party: chamber[party] for party in PARTIES}}
