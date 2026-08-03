# Federal model parameter-usage audit

This report describes the current Python production path. It does not change model behaviour.

- Active scalar settings: 15
- Unused scalar settings: 25
- Code-default-only settings: 0
- Possible naming mismatches: 0

## Possible naming mismatches

- None.

## Structured inputs requiring attention

- **PARAMS preference matrix (A1:G7)** — `unused`: Python uses the state PREF_MATRIX sheets instead.
- **PARAMS MinorParty Uplift table** — `unused`: Not loaded by the Python model.
- **PARAMS Geography table** — `unused`: Not loaded by the Python model.
- **SCENARIO_STATS Votes / ScenarioTotal / Seats** — `active_metadata`: Preserved as evidence metadata for shrinkage and reliability reporting.
- **SEAT_PREF_FLOWS_LONG Votes** — `active_metadata`: Preserved for seat-level evidence, pooled statistics and variance estimation.
- **SEAT_SHRINKAGE_OVERRIDES** — `conditionally_active`: Overrides the global SEAT_SHRINKAGE_K only for rows explicitly enabled by division.
- **CANDIDATE_CLASSIFICATION** — `reference_input_pending_recompile`: Candidate-level category, subtype and observed flow evidence for the shadow recompilation pipeline; it does not yet replace production preference evidence.
- **IDEOLOGY** — `conditionally_active`: Fallback when exact/AEC/posterior evidence is incomplete or unavailable.
- **SIPHON** — `loaded_but_unused`: Loaded into params but never consulted by the Python production engine.
- **CALIBRATION_PARAMS** — `unused`: Synced but not loaded by the Python production engine.
