from __future__ import annotations

import math


def normalise_distribution(
    values: dict[str, float],
    parties: list[str],
) -> dict[str, float]:
    clean = {
        party: max(float(values.get(party, 0.0) or 0.0), 0.0)
        for party in parties
    }
    total = sum(clean.values())
    if total > 0:
        return {party: value / total for party, value in clean.items()}
    if not parties:
        return {}
    return {party: 1.0 / len(parties) for party in parties}


def evidence_weight(
    seats: float,
    variance: dict[str, float] | None,
    shrinkage_k: float,
) -> float:
    n = max(float(seats), 0.0)
    if n <= 0:
        return 0.0

    finite_variances = [
        max(float(value), 0.0)
        for value in (variance or {}).values()
        if math.isfinite(float(value))
    ]
    dispersion = sum(finite_variances) / len(finite_variances) if finite_variances else 0.0

    # Preference shares are bounded in [0, 1], with maximum variance 0.25.
    # Convert dispersion to a 0–1 penalty before calculating effective seats.
    dispersion_penalty = min(dispersion / 0.25, 1.0)
    effective_seats = n / (1.0 + dispersion_penalty)
    k = max(float(shrinkage_k), 0.0)
    return effective_seats / (effective_seats + k) if effective_seats + k > 0 else 0.0


def shrink_distribution(
    empirical: dict[str, float],
    prior: dict[str, float],
    parties: list[str],
    seats: float,
    variance: dict[str, float] | None,
    shrinkage_k: float,
) -> tuple[dict[str, float], float]:
    empirical_norm = normalise_distribution(empirical, parties)
    prior_norm = normalise_distribution(prior, parties)
    weight = evidence_weight(seats, variance, shrinkage_k)
    blended = {
        party: weight * empirical_norm[party] + (1.0 - weight) * prior_norm[party]
        for party in parties
    }
    return normalise_distribution(blended, parties), weight


def nearest_scenario_distribution(
    eliminated: str,
    requested_alive: list[str],
    scenario_evidence: dict[str, dict],
    ideology_prior: dict[str, float],
    shrinkage_k: float,
    max_distance: int | None = None,
    require_all_requested: bool = False,
) -> tuple[dict[str, float] | None, dict]:
    requested = set(requested_alive)
    candidates = []

    for key, evidence in scenario_evidence.items():
        try:
            donor_eliminated, donor_alive_text = key.split("|", 1)
        except ValueError:
            continue
        if donor_eliminated != eliminated:
            continue

        donor_alive = set(donor_alive_text.split("+"))
        missing = requested - donor_alive
        extra = donor_alive - requested
        distance = len(missing) + len(extra)
        if max_distance is not None and distance > max(int(max_distance), 0):
            continue
        if require_all_requested and missing:
            continue
        # At equal total distance, prefer a donor with removable extra parties
        # over one lacking a party required by the requested field.
        score = (distance, len(missing))
        candidates.append((score, key, donor_alive, evidence))

    if not candidates:
        return None, {
            "matched_scenarios": [],
            "distance": None,
            "missing_requested_parties": sorted(requested),
            "max_distance": max_distance,
            "require_all_requested": require_all_requested,
        }

    best_score = min(item[0] for item in candidates)
    selected = [item for item in candidates if item[0] == best_score]
    combined = {party: 0.0 for party in requested_alive}
    total_weight = 0.0
    total_seats = 0
    matched_keys = []
    missing_across_matches = set(requested)

    for _, key, donor_alive, evidence in selected:
        empirical = (
            evidence.get("equal_seat_mean_shares")
            or evidence.get("shares")
            or {}
        )
        projected = {
            party: float(empirical.get(party, 0.0) or 0.0)
            for party in requested_alive
            if party in donor_alive
        }
        if sum(projected.values()) <= 0:
            continue
        projected = normalise_distribution(projected, requested_alive)
        seats = int(
            evidence.get("seat_observations", evidence.get("seats", 0)) or 0
        )
        reliability = evidence_weight(
            seats,
            evidence.get("between_seat_variance", {}),
            shrinkage_k,
        )
        weight = max(seats, 1) * max(reliability, 1e-6)
        for party in requested_alive:
            combined[party] += weight * projected.get(party, 0.0)
        total_weight += weight
        total_seats += seats
        matched_keys.append(key)
        missing_across_matches &= requested - donor_alive

    if total_weight <= 0:
        return None, {
            "matched_scenarios": matched_keys,
            "distance": best_score[0],
            "missing_requested_parties": sorted(missing_across_matches),
        }

    empirical = {
        party: combined[party] / total_weight for party in requested_alive
    }
    # Shrinking the projected evidence toward ideology supplies controlled
    # probability mass to requested parties absent from every donor field.
    result, weight = shrink_distribution(
        empirical=empirical,
        prior=ideology_prior,
        parties=requested_alive,
        seats=max(total_seats, 1),
        variance={},
        shrinkage_k=shrinkage_k,
    )
    return result, {
        "matched_scenarios": matched_keys,
        "distance": best_score[0],
        "missing_requested_parties": sorted(missing_across_matches),
        "evidence_weight": weight,
        "evidence_seats": total_seats,
        "source": "nearest_alive_set",
        "max_distance": max_distance,
        "require_all_requested": require_all_requested,
    }
