# Senate Development Integration

This development copy combines the existing House app with a candidate-level
Senate projection and an overall dashboard. The production repository has not
been changed.

## Model views

- **House** runs the backed-up lower-house application unchanged.
- **Senate** reweights a deterministic sample of official 2025 AEC formal
  ballots and runs candidate-level STV counts in every state and territory.
- **Dashboard** runs both engines from the shared scenario inputs.

## Validation

- All 2022 and 2025 raw formal-ballot files reconcile to AEC first preferences.
- Full historical candidate replay returns the correct winners in all 16 contests.
- The compact 2025 projection samples return the correct winners in all eight contests.
- Default House inputs reproduce every official 2025 elected-party cohort.

## Baseline meaning

Senate changes currently compare projected seats with the party under which each
senator was elected. A future `SENATE_CURRENT_AFFILIATION` input should explicitly
record defections or party changes for a current-composition dashboard.
