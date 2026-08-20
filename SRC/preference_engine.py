from __future__ import annotations

import math

from .constants import PARTIES
from .evidence import nearest_scenario_distribution, shrink_distribution


def _clamp01(value) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _normalise_alive(vector: list[float], alive: set[str]) -> list[float]:
    out = vector[:]
    total = 0.0

    for i, party in enumerate(PARTIES):
        if party in alive:
            total += out[i]
        else:
            out[i] = 0.0

    if total > 0:
        return [
            value / total if PARTIES[i] in alive else 0.0
            for i, value in enumerate(out)
        ]

    if not alive:
        return [0.0] * len(PARTIES)

    return [1.0 / len(alive) if party in alive else 0.0 for party in PARTIES]


def _parse_share(value) -> float:
    if value is None:
        return 0.0

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return 0.0
        if text.endswith("%"):
            try:
                return max(0.0, float(text[:-1].strip()) / 100.0)
            except ValueError:
                return 0.0
        value = text

    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0

    if not math.isfinite(number) or number <= 0:
        return 0.0
    return number / 100.0 if number > 1.5 else number


def _scalar(params: dict, key: str, default: float) -> float:
    scalars = params.get("scalars", {})
    return float(scalars.get(key, default))


def _evidence_shrinkage_enabled(params: dict) -> bool:
    return _scalar(params, "USE_EVIDENCE_SHRINKAGE", 1.0) >= 0.5


def _nearest_field_enabled(params: dict) -> bool:
    return _scalar(params, "USE_NEAREST_FIELD_MATCHING", 1.0) >= 0.5


def _nearest_field_options(params: dict) -> dict:
    max_distance = _scalar(params, "NEAREST_FIELD_MAX_DISTANCE", 99.0)
    return {
        "max_distance": int(max_distance) if max_distance < 99 else None,
        "require_all_requested": (
            _scalar(params, "NEAREST_FIELD_REQUIRE_ALL_REQUESTED", 0.0) >= 0.5
        ),
    }


def _seat_shrinkage_k(params: dict, division_key: str | None) -> float:
    key = str(division_key or "").strip().upper()
    override = params.get("SEAT_SHRINKAGE_K_BY_DIVISION", {}).get(key)
    if override is not None:
        return max(float(override), 0.0)
    return _scalar(params, "SEAT_SHRINKAGE_K", 1.0)


def _scenario_evidence_diagnostic(
    params: dict,
    scenario_key: str,
) -> dict[str, float | int]:
    evidence = params.get("POSTERIOR_SCENARIO_EVIDENCE", {}).get(
        scenario_key, {}
    )
    variances = [
        float(value)
        for value in evidence.get("between_seat_variance", {}).values()
    ]
    return {
        "pooled_evidence_seats": int(
            evidence.get("seat_observations", evidence.get("seats", 0)) or 0
        ),
        "pooled_mean_variance": (
            sum(variances) / len(variances) if variances else 0.0
        ),
    }


def _shrunk_pooled_scenario(
    elim: str,
    alive_key: str,
    alive: set[str],
    params: dict,
    seat_class: str = "",
) -> tuple[dict[str, float] | None, float, float | None, int]:
    evidence = params.get("POSTERIOR_SCENARIO_EVIDENCE", {}).get(
        f"{elim}|{alive_key}"
    )
    if not evidence:
        return None, 0.0, None, 0

    empirical = evidence.get("equal_seat_mean_shares") or evidence.get("shares") or {}
    ideology = params.get("ideology", {}).get(elim, {})
    parties = [party for party in PARTIES if party in alive]
    shrunk, weight = shrink_distribution(
        empirical=empirical,
        prior=ideology,
        parties=parties,
        seats=int(evidence.get("seat_observations", evidence.get("seats", 0)) or 0),
        variance=evidence.get("between_seat_variance", {}),
        shrinkage_k=_scalar(params, "POOL_SHRINKAGE_K", 1.0),
    )
    class_weight = None
    class_seats = 0
    use_class = _scalar(params, "USE_CLASS_EFFECTS", 1.0) >= 0.5
    class_evidence = params.get(
        "POSTERIOR_SCENARIO_EVIDENCE_BY_CLASS", {}
    ).get(str(seat_class or "").strip(), {})
    if use_class and class_evidence:
        scenario_key = f"{elim}|{alive_key}"
        class_scenario = class_evidence.get(scenario_key)
        if class_scenario:
            class_seats = int(
                class_scenario.get(
                    "seat_observations",
                    class_scenario.get("seats", 0),
                )
                or 0
            )
            shrunk, class_weight = shrink_distribution(
                empirical=class_scenario.get("equal_seat_mean_shares", {}),
                prior=shrunk,
                parties=parties,
                seats=class_seats,
                variance=class_scenario.get("between_seat_variance", {}),
                shrinkage_k=_scalar(
                    params,
                    "CLASS_EFFECT_SHRINKAGE_K",
                    10.0,
                ),
            )
        elif _nearest_field_enabled(params):
            nearest, diagnostic = nearest_scenario_distribution(
                eliminated=elim,
                requested_alive=parties,
                scenario_evidence=class_evidence,
                ideology_prior=shrunk,
                shrinkage_k=_scalar(
                    params,
                    "CLASS_EFFECT_SHRINKAGE_K",
                    10.0,
                ),
                **_nearest_field_options(params),
            )
            if nearest:
                shrunk = nearest
                class_weight = diagnostic.get("evidence_weight")
                class_seats = sum(
                    int(
                        class_evidence.get(key, {}).get(
                            "seat_observations", 0
                        )
                        or 0
                    )
                    for key in diagnostic.get("matched_scenarios", [])
                )

    return shrunk, weight, class_weight, class_seats


def _apply_protected_entry(
    prior: list[float],
    missing: list[int],
    supported: list[int],
    params: dict,
    alive: set[str],
) -> list[float]:
    if not missing:
        return prior

    floor = _clamp01(_scalar(params, "POST_ENTRY_FLOOR", 0.15))
    strength = _clamp01(_scalar(params, "POST_ENTRY_STRENGTH", 0.75))
    cur_missing = sum(prior[i] for i in missing)
    reserve = min(max(floor, strength * cur_missing), 0.95)

    if not supported:
        return prior

    out = [0.0] * len(PARTIES)

    if cur_missing > 0:
        for i in missing:
            out[i] = reserve * (prior[i] / cur_missing)
    else:
        for i in missing:
            out[i] = reserve / len(missing)

    remaining = 1.0 - reserve
    cur_supported = sum(prior[i] for i in supported)

    if cur_supported > 0 and remaining > 0:
        for i in supported:
            out[i] = remaining * (prior[i] / cur_supported)
    else:
        for i in supported:
            out[i] = remaining / len(supported)

    return _normalise_alive(out, alive)


def _calibrate_supported_only(
    vector: list[float],
    supported: list[int],
    target_aec: list[float],
    frozen_missing_mass: float,
    alive: set[str],
) -> list[float]:
    eps = 1e-12
    a_sum = sum(target_aec[i] for i in supported)
    v_sum = sum(vector[i] for i in supported)

    if not (a_sum > 0 and v_sum > 0):
        return vector

    cal = vector[:]
    for i in supported:
        a = max(target_aec[i] / a_sum, eps)
        q = max(vector[i] / v_sum, eps)
        cal[i] *= math.exp(math.log(a) - math.log(q))

    sup_sum = sum(cal[i] for i in supported)
    out = cal[:]
    remaining = 1.0 - frozen_missing_mass

    if sup_sum > 0 and remaining > 0:
        for i in supported:
            out[i] = remaining * (cal[i] / sup_sum)

    return _normalise_alive(out, alive)


def get_preference_weights(
    elim_party: str,
    alive_parties: list[str],
    aec_row: dict[str, float],
    params: dict,
    apply_calibration: bool = True,
    seat_state: str = "NAT",
    division_key: str | None = None,
    seat_flows: dict[str, dict[str, float]] | None = None,
    seat_flow_evidence: dict[str, dict] | None = None,
    aec_row_party: str | None = None,
    seat_class: str = "",
) -> tuple[dict[str, float], dict]:
    elim = str(elim_party or "").strip().upper()
    alive_arr = [p for p in [str(p).strip().upper() for p in alive_parties] if p in PARTIES]
    alive = set(alive_arr)

    if elim not in PARTIES or not alive:
        raise ValueError("bad redistribution inputs")

    base = [float(aec_row.get(party, 0.0) or 0.0) for party in PARTIES]
    row_party = str(aec_row_party or "").strip().upper()
    row_party_ok = not row_party or row_party == elim

    supported = [i for i, party in enumerate(PARTIES) if party in alive and base[i] > 0]
    missing = [i for i, party in enumerate(PARTIES) if party in alive and base[i] <= 0]
    total_row = sum(base)
    alive_mass = sum(base[i] for i, party in enumerate(PARTIES) if party in alive)

    aec_usable = row_party_ok and alive_mass > 0
    aec_proj = _normalise_alive(base, alive) if aec_usable else None
    coverage = alive_mass / total_row if total_row > 0 else 0.0
    aec_perfect = aec_usable and not missing and coverage >= 0.999
    aec_incomplete = aec_usable and bool(missing)

    alive_is_alp_lnp = alive == {"ALP", "LNP"}
    force_posterior_on_2cp = elim == "ON" and alive_is_alp_lnp
    alive_key = "+".join(sorted(alive_arr))

    seat_flow = (seat_flows or {}).get(f"{elim}|{alive_key}")
    scenario_key = f"{elim}|{alive_key}"
    current_seat_evidence = (seat_flow_evidence or {}).get(scenario_key, {})
    evidence_diagnostic = _scenario_evidence_diagnostic(params, scenario_key)
    if seat_flow:
        if _evidence_shrinkage_enabled(params):
            pooled, pooled_weight, class_weight, class_seats = _shrunk_pooled_scenario(
                elim,
                alive_key,
                alive,
                params,
                seat_class,
            )
            if pooled:
                scenario_evidence = params.get(
                    "POSTERIOR_SCENARIO_EVIDENCE", {}
                ).get(f"{elim}|{alive_key}", {})
                shrunk, seat_weight = shrink_distribution(
                    empirical=seat_flow,
                    prior=pooled,
                    parties=[party for party in PARTIES if party in alive],
                    seats=max(
                        float(current_seat_evidence.get("evidence_multiplier", 1.0) or 0.0),
                        0.0,
                    ),
                    variance=scenario_evidence.get("between_seat_variance", {}),
                    shrinkage_k=_seat_shrinkage_k(params, division_key),
                )
                vec = [shrunk.get(party, 0.0) for party in PARTIES]
                vec = _normalise_alive(vec, alive)
                return _dict_from_vector(vec), {
                    "basis": "seat_pref_flow_shrunk",
                    "coverage": coverage,
                    "missing": [PARTIES[i] for i in missing],
                    "anchor_weight": 0.0,
                    "seat_evidence_weight": seat_weight,
                    "seat_evidence_multiplier": float(
                        current_seat_evidence.get("evidence_multiplier", 1.0) or 0.0
                    ),
                    "seat_evidence_method": current_seat_evidence.get("method", ""),
                    "pooled_evidence_weight": pooled_weight,
                    "class_evidence_weight": class_weight,
                    "class_evidence_seats": class_seats,
                    "position_conflict": bool(
                        current_seat_evidence
                        .get("position_conflict", False)
                    ),
                    **evidence_diagnostic,
                }

        vec = [float(seat_flow.get(party, 0.0) or 0.0) for party in PARTIES]
        vec = _normalise_alive(vec, alive)
        return _dict_from_vector(vec), {
            "basis": "seat_pref_flow",
            "coverage": coverage,
            "missing": [PARTIES[i] for i in missing],
            "anchor_weight": 0.0,
            "position_conflict": bool(
                current_seat_evidence
                .get("position_conflict", False)
            ),
            **evidence_diagnostic,
        }

    # Explicit final-pair priors are deliberate model inputs and take
    # precedence over pooled fallback evidence for the same alive set.
    if elim == "LNP" and alive == {"ALP", "ON"}:
        baselines = params.get("baselines", {})
        p_on = baselines.get("LNP_TO_ON_BY_SEAT", {}).get(str(division_key or "").upper())
        if p_on is None:
            p_on = baselines.get("LNP_TO_ON", {}).get(
                seat_state,
                baselines.get("LNP_TO_ON", {}).get("NAT"),
            )
        if p_on is not None and math.isfinite(float(p_on)):
            out = [0.0] * len(PARTIES)
            out[PARTIES.index("ON")] = float(p_on)
            out[PARTIES.index("ALP")] = 1.0 - float(p_on)
            vec = _normalise_alive(out, alive)
            return _dict_from_vector(vec), {
                "basis": "lnp_to_alp_on_state_baseline",
                "coverage": coverage,
                "missing": [PARTIES[i] for i in missing],
                "anchor_weight": 0.0,
            }

    # A complete seat-specific AEC row is stronger evidence than a pooled
    # national scenario. ON-to-ALP/LNP remains the intentional exception.
    if aec_perfect and not force_posterior_on_2cp:
        return _dict_from_vector(aec_proj), {
            "basis": "aec_perfect",
            "coverage": coverage,
            "missing": [PARTIES[i] for i in missing],
            "anchor_weight": 1.0,
        }

    if _evidence_shrinkage_enabled(params):
        explicit_pooled, pooled_weight, class_weight, class_seats = _shrunk_pooled_scenario(
            elim,
            alive_key,
            alive,
            params,
            seat_class,
        )
        if explicit_pooled:
            matrix_weight = _clamp01(
                _scalar(params, "MATRIX_POSTERIOR_BLEND_WEIGHT", 0.0)
            )
            posterior_vec = [
                float(explicit_pooled.get(party, 0.0) or 0.0)
                for party in PARTIES
            ]
            if aec_usable and aec_proj:
                blended = [
                    matrix_weight * aec_proj[i]
                    + (1.0 - matrix_weight) * posterior_vec[i]
                    for i in range(len(PARTIES))
                ]
                vec = _normalise_alive(blended, alive)
                if matrix_weight <= 0:
                    basis = "posterior_shrunk"
                elif matrix_weight >= 1:
                    basis = "aec"
                else:
                    basis = "matrix_posterior_explicit_blend"
                return _dict_from_vector(vec), {
                    "basis": basis,
                    "coverage": coverage,
                    "missing": [PARTIES[i] for i in missing],
                    "anchor_weight": matrix_weight,
                    "pooled_evidence_weight": pooled_weight,
                    "class_evidence_weight": class_weight,
                    "class_evidence_seats": class_seats,
                    **evidence_diagnostic,
                }

            vec = _normalise_alive(posterior_vec, alive)
            return _dict_from_vector(vec), {
                "basis": "posterior_shrunk",
                "coverage": coverage,
                "missing": [PARTIES[i] for i in missing],
                "anchor_weight": 0.0,
                "pooled_evidence_weight": pooled_weight,
                "class_evidence_weight": class_weight,
                "class_evidence_seats": class_seats,
                **evidence_diagnostic,
            }

    def resolve_anchor_weight() -> float:
        if force_posterior_on_2cp:
            return _clamp01(_scalar(params, "AEC_2CP_ANCHOR_ON", 0.15))
        if aec_incomplete:
            w = _clamp01(_scalar(params, "AEC_ANCHOR_WHEN_MISSING", 0.4))
            cap = _clamp01(_scalar(params, "AEC_MISMATCH_MAX", 0.3))
            return min(w, cap, 0.999999)
        return _clamp01((coverage - 0.5) / 0.4)

    post = params.get("POSTERIOR_SCENARIOS", {}).get(f"{elim}|{alive_key}")
    pooled_evidence_weight = None
    class_evidence_weight = None
    class_evidence_seats = 0
    if post and _evidence_shrinkage_enabled(params):
        (
            shrunk_post,
            pooled_evidence_weight,
            class_evidence_weight,
            class_evidence_seats,
        ) = _shrunk_pooled_scenario(
            elim,
            alive_key,
            alive,
            params,
            seat_class,
        )
        if shrunk_post:
            post = shrunk_post

    if post:
        vec = [0.0] * len(PARTIES)
        post_sum = 0.0
        for i, party in enumerate(PARTIES):
            if party not in alive:
                continue
            vec[i] = _parse_share(post.get(party))
            post_sum += vec[i]

        if post_sum > 0:
            vec = [value / post_sum if PARTIES[i] in alive else 0.0 for i, value in enumerate(vec)]

        post_side = _normalise_alive(vec, alive)

        if missing:
            post_side = _apply_protected_entry(post_side, missing, supported, params, alive)
            if apply_calibration and len(supported) >= 2 and aec_usable:
                miss_mass = sum(post_side[i] for i in missing)
                post_side = _calibrate_supported_only(
                    post_side,
                    supported,
                    base,
                    _clamp01(miss_mass),
                    alive,
                )

        if aec_usable and aec_proj:
            w = resolve_anchor_weight()
            blended = [
                w * aec_proj[i] + (1.0 - w) * post_side[i]
                for i in range(len(PARTIES))
            ]
            vec = _normalise_alive(blended, alive)
            return _dict_from_vector(vec), {
                "basis": (
                    "posterior_shrunk_aec_blend"
                    if pooled_evidence_weight is not None
                    else "posterior_aec_blend"
                ),
                "coverage": coverage,
                "missing": [PARTIES[i] for i in missing],
                "anchor_weight": w,
                "pooled_evidence_weight": pooled_evidence_weight,
                "class_evidence_weight": class_evidence_weight,
                "class_evidence_seats": class_evidence_seats,
                **evidence_diagnostic,
            }

        return _dict_from_vector(post_side), {
            "basis": (
                "posterior_shrunk"
                if pooled_evidence_weight is not None
                else "posterior"
            ),
            "coverage": coverage,
            "missing": [PARTIES[i] for i in missing],
            "anchor_weight": 0.0,
            "pooled_evidence_weight": pooled_evidence_weight,
            "class_evidence_weight": (
                class_evidence_weight
                if pooled_evidence_weight is not None
                else None
            ),
            "class_evidence_seats": (
                class_evidence_seats
                if pooled_evidence_weight is not None
                else 0
            ),
            **evidence_diagnostic,
        }

    if _evidence_shrinkage_enabled(params) and _nearest_field_enabled(params):
        nearest, nearest_diagnostic = nearest_scenario_distribution(
            eliminated=elim,
            requested_alive=[party for party in PARTIES if party in alive],
            scenario_evidence=params.get("POSTERIOR_SCENARIO_EVIDENCE", {}),
            ideology_prior=params.get("ideology", {}).get(elim, {}),
            shrinkage_k=_scalar(params, "NEAREST_FIELD_SHRINKAGE_K", 1.0),
            **_nearest_field_options(params),
        )
        if nearest:
            vec = [nearest.get(party, 0.0) for party in PARTIES]
            vec = _normalise_alive(vec, alive)
            return _dict_from_vector(vec), {
                "basis": "posterior_nearest_field",
                "coverage": coverage,
                "missing": [PARTIES[i] for i in missing],
                "anchor_weight": 0.0,
                "nearest_distance": nearest_diagnostic.get("distance"),
                "nearest_scenarios": "+".join(
                    nearest_diagnostic.get("matched_scenarios", [])
                ),
                "pooled_evidence_weight": nearest_diagnostic.get(
                    "evidence_weight"
                ),
                "pooled_evidence_seats": nearest_diagnostic.get(
                    "evidence_seats", 0
                ),
                "pooled_mean_variance": 0.0,
            }

    ideology = params.get("ideology", {}).get(elim)

    if aec_incomplete:
        prior = [0.0] * len(PARTIES)
        if ideology:
            for i, party in enumerate(PARTIES):
                if party in alive:
                    prior[i] = float(ideology.get(party, 0.0) or 0.0)
        else:
            for i, party in enumerate(PARTIES):
                if party in alive:
                    prior[i] = 1.0

        prior_side = _normalise_alive(prior, alive)
        prior_side = _apply_protected_entry(prior_side, missing, supported, params, alive)

        if apply_calibration and len(supported) >= 2 and aec_usable:
            miss_mass = sum(prior_side[i] for i in missing)
            prior_side = _calibrate_supported_only(
                prior_side,
                supported,
                base,
                _clamp01(miss_mass),
                alive,
            )

        if aec_usable and aec_proj:
            w = resolve_anchor_weight()
            blended = [
                w * aec_proj[i] + (1.0 - w) * prior_side[i]
                for i in range(len(PARTIES))
            ]
            vec = _normalise_alive(blended, alive)
            return _dict_from_vector(vec), {
                "basis": "ideology_aec_blend",
                "coverage": coverage,
                "missing": [PARTIES[i] for i in missing],
                "anchor_weight": w,
            }

        return _dict_from_vector(prior_side), {
            "basis": "ideology_missing_entry",
            "coverage": coverage,
            "missing": [PARTIES[i] for i in missing],
            "anchor_weight": 0.0,
        }

    if aec_usable and aec_proj:
        return _dict_from_vector(aec_proj), {
            "basis": "aec",
            "coverage": coverage,
            "missing": [PARTIES[i] for i in missing],
            "anchor_weight": 1.0,
        }

    if ideology:
        vec = [
            float(ideology.get(party, 0.0) or 0.0) if party in alive else 0.0
            for party in PARTIES
        ]
        vec = _normalise_alive(vec, alive)
        return _dict_from_vector(vec), {
            "basis": "ideology",
            "coverage": coverage,
            "missing": [PARTIES[i] for i in missing],
            "anchor_weight": 0.0,
        }

    vec = _normalise_alive([1.0] * len(PARTIES), alive)
    return _dict_from_vector(vec), {
        "basis": "uniform",
        "coverage": coverage,
        "missing": [PARTIES[i] for i in missing],
        "anchor_weight": 0.0,
    }


def _dict_from_vector(vector: list[float]) -> dict[str, float]:
    return {party: vector[i] for i, party in enumerate(PARTIES)}
