# Shadow category-flow leave-one-seat-out validation

The target is the official last-surviving-candidate category-exit flow.
Every held-out electorate is excluded from the evidence pool for every method.
Each seat/scenario target has equal validation weight.

Best method: `existing_manual_evidence` with pool K 1.

## Best setting for each evidence method

| method | pool_k | observations | exact_matches | nearest_matches | ideology_fallbacks | mean_mae | mean_brier | mean_total_variation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| existing_manual_evidence | 1 | 488 | 476 | 12 | 0 | 0.0709765 | 0.0346903 | 0.112953 |
| shadow_direct_unweighted | 2 | 488 | 478 | 10 | 0 | 0.0716042 | 0.0359658 | 0.11392 |
| shadow_pass_through | 2 | 488 | 478 | 10 | 0 | 0.0717718 | 0.0359849 | 0.114167 |
| shadow_direct_coverage | 1 | 488 | 478 | 10 | 0 | 0.0714332 | 0.0362821 | 0.11346 |
| ideology_only | 0 | 488 | 0 | 0 | 488 | 0.115604 | 0.0783842 | 0.182192 |

## Paired uncertainty checks

| subset | challenger | reference | observations | seats | mean_brier_difference | brier_ci_low | brier_ci_high | probability_challenger_better_brier | mean_tvd_difference | tvd_ci_low | tvd_ci_high | probability_challenger_better_tvd |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all | shadow_direct_unweighted | existing_manual_evidence | 488 | 150 | 0.00127547 | -0.00139807 | 0.00559666 | 0.28525 | 0.000967344 | -0.00154412 | 0.00448937 | 0.28525 |
| all | shadow_direct_coverage | existing_manual_evidence | 488 | 150 | 0.00159178 | -0.000876211 | 0.00581517 | 0.251 | 0.000506946 | -0.00208438 | 0.00400954 | 0.41125 |
| all | shadow_pass_through | existing_manual_evidence | 488 | 150 | 0.00129456 | -0.00151714 | 0.00562022 | 0.29025 | 0.00121433 | -0.00136936 | 0.00483475 | 0.22925 |
| all | shadow_direct_coverage | shadow_direct_unweighted | 488 | 150 | 0.000316304 | -0.000591408 | 0.00137143 | 0.27475 | -0.000460398 | -0.00156553 | 0.0006779 | 0.7965 |

## Interpretation

Coverage weighting changes both the pooled mean and the effective evidence size.
The pass-through method is evaluated as a diagnostic approximation, not as
official observed flow. Existing manual evidence uses its current canonical
alive-set corrections and excludes the held-out seat.
