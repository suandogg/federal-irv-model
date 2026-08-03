from __future__ import annotations


def assess_reliability(diagnostic: dict) -> dict[str, str | float | int]:
    basis = str(diagnostic.get("basis") or "")
    seats = int(diagnostic.get("pooled_evidence_seats", 0) or 0)
    variance = float(diagnostic.get("pooled_mean_variance", 0.0) or 0.0)
    nearest_distance = diagnostic.get("nearest_distance")
    position_conflict = bool(diagnostic.get("position_conflict", False))

    if basis.startswith("seat_pref_flow"):
        rating = "Low" if position_conflict else "Medium"
        reason = (
            "Seat-specific historical flow with a position conflict."
            if position_conflict
            else "Seat-specific historical flow from one election."
        )
    elif "nearest" in basis:
        distance = int(nearest_distance or 0)
        if distance <= 1 and seats >= 5:
            rating = "Medium"
        else:
            rating = "Low"
        reason = f"Nearest-field evidence at distance {distance}, based on {seats} seats."
    elif "posterior" in basis:
        if seats >= 10 and variance <= 0.02:
            rating = "High"
        elif seats >= 3:
            rating = "Medium"
        else:
            rating = "Low"
        reason = f"Exact pooled scenario based on {seats} seats."
    elif basis in {"aec", "aec_perfect", "lnp_to_alp_on_state_baseline"}:
        rating = "Medium"
        reason = "Historical matrix or explicit baseline evidence."
    else:
        rating = "Low"
        reason = "Fallback evidence with limited direct scenario support."

    return {
        "reliability": rating,
        "reliability_reason": reason,
    }
