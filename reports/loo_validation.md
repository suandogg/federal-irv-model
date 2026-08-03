# Leave-one-seat-out validation

Each seat/scenario observation has equal weight. Ballot totals do not act as
independent sample size. The held-out seat is excluded from pooled evidence.

The held-out seat is excluded from both pooled scenario evidence and the
equal-seat national preference matrix.

Best overall method: `posterior_only` (pool K 2, matrix weight 0%)

Best genuine hybrid: pool K 1, matrix weight 10%

## Flow accuracy

| pool_k | matrix_weight | method | observations | mean_mae | mean_brier |
| --- | --- | --- | --- | --- | --- |
| 2 | 0 | posterior_only | 488 | 0.0634056 | 0.0283863 |
| 1 | 0 | posterior_only | 488 | 0.0629491 | 0.0284475 |
| 1 | 0.1 | hybrid | 488 | 0.0640016 | 0.0291093 |
| 0 | 0.1 | hybrid | 488 | 0.0637482 | 0.0293126 |
| 0 | 0 | posterior_only | 488 | 0.0634181 | 0.0293321 |
| 5 | 0 | posterior_only | 488 | 0.0657501 | 0.0293558 |
| 2 | 0.1 | hybrid | 488 | 0.0648188 | 0.0294142 |
| 0 | 0.25 | hybrid | 488 | 0.0661226 | 0.0307517 |
| 5 | 0.1 | hybrid | 488 | 0.0676835 | 0.0308934 |
| 1 | 0.25 | hybrid | 488 | 0.0670811 | 0.0313231 |
| 10 | 0 | posterior_only | 488 | 0.0696735 | 0.0319111 |
| 2 | 0.25 | hybrid | 488 | 0.0682773 | 0.0320272 |
| 10 | 0.1 | hybrid | 488 | 0.071571 | 0.0336329 |
| 5 | 0.25 | hybrid | 488 | 0.071246 | 0.0340182 |
| 10 | 0.25 | hybrid | 488 | 0.0747938 | 0.0368508 |
| 20 | 0 | posterior_only | 488 | 0.0753523 | 0.0369194 |
| 0 | 0.5 | hybrid | 488 | 0.0738092 | 0.0370653 |
| 1 | 0.5 | hybrid | 488 | 0.0751357 | 0.0382695 |
| 20 | 0.1 | hybrid | 488 | 0.0768343 | 0.0384081 |
| 2 | 0.5 | hybrid | 488 | 0.0762834 | 0.0392389 |
| 20 | 0.25 | hybrid | 488 | 0.0794589 | 0.0411649 |
| 5 | 0.5 | hybrid | 488 | 0.0788508 | 0.0414088 |
| 10 | 0.5 | hybrid | 488 | 0.0815977 | 0.0439079 |
| 50 | 0 | posterior_only | 488 | 0.0848561 | 0.0466628 |
| 20 | 0.5 | hybrid | 488 | 0.0849526 | 0.047156 |
| 50 | 0.1 | hybrid | 488 | 0.0853529 | 0.0471586 |
| 0 | 0.75 | hybrid | 488 | 0.0854876 | 0.0482729 |
| 50 | 0.25 | hybrid | 488 | 0.0864644 | 0.0484337 |
| 1 | 0.75 | hybrid | 488 | 0.0863996 | 0.0492866 |
| 2 | 0.75 | hybrid | 488 | 0.0871 | 0.0500213 |
| 5 | 0.75 | hybrid | 488 | 0.0885378 | 0.0515276 |
| 50 | 0.5 | hybrid | 488 | 0.0895631 | 0.051976 |
| 10 | 0.75 | hybrid | 488 | 0.0900351 | 0.0530825 |
| 20 | 0.75 | hybrid | 488 | 0.0917323 | 0.0548925 |
| 50 | 0.75 | hybrid | 488 | 0.0940042 | 0.0572896 |
| 0 | 1 | matrix_only | 488 | 0.099218 | 0.0643745 |
| 1 | 1 | matrix_only | 488 | 0.099218 | 0.0643745 |
| 2 | 1 | matrix_only | 488 | 0.099218 | 0.0643745 |
| 5 | 1 | matrix_only | 488 | 0.099218 | 0.0643745 |
| 10 | 1 | matrix_only | 488 | 0.099218 | 0.0643745 |
| 20 | 1 | matrix_only | 488 | 0.099218 | 0.0643745 |
| 50 | 1 | matrix_only | 488 | 0.099218 | 0.0643745 |

## Secondary seat outcomes

| method | seats | winner_matches | final_two_matches |
| --- | --- | --- | --- |
| hybrid | 148 | 131 | 131 |
| posterior_only | 148 | 130 | 129 |
| matrix_only | 148 | 125 | 120 |

## Limitation

This tests generalisation across electorates within one election. It cannot
fully validate the persistence of a seat-specific flow into a later election.
State and seat-class pooling are intentionally deferred to the later empirical
effects stage.
