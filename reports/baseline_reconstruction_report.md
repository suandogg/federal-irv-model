# Baseline Reconstruction Report

This compares the deterministic IRV engine with the official baseline results
stored in `BASELINE_RESULTS_BY_SEAT.csv`. It is a reconstruction check, not
an out-of-sample accuracy test.

## Summary

| metric | value |
| --- | --- |
| seats_compared | 148 |
| winner_matches | 134 |
| runner_up_matches | 134 |
| final_two_matches | 140 |
| mean_abs_winner_diff_pp | 1.30125 |
| max_abs_winner_diff_pp | 10.2871 |

## Largest differences

| division_key | actual_winner | actual_runner_up | actual_final_two | actual_winner_pct | division | winner | runner_up | final_two | winner_pct | winner_match | runner_up_match | final_two_match | winner_diff_pp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FLINDERS | LNP | IND | IND+LNP | 62.4925 | Flinders | LNP | IND | IND+LNP | 0.522054 | True | True | True | 10.2871 |
| RIVERINA | LNP | IND | IND+LNP | 61.7066 | Riverina | LNP | ON | LNP+ON | 0.529711 | True | False | False | 8.73548 |
| NICHOLLS | LNP | IND | IND+LNP | 60.4812 | Nicholls | LNP | IND | IND+LNP | 0.528155 | True | True | True | 7.66567 |
| GREY | LNP | IND | IND+LNP | 52.2261 | Grey | ON | IND | IND+ON | 0.586229 | False | True | False | 6.39685 |
| FRANKLIN | ALP | IND | ALP+IND | 55.8958 | Franklin | IND | ALP | ALP+IND | 0.50049 | False | False | True | 5.84675 |
| HERBERT | LNP | ALP | ALP+LNP | 64.4266 | Herbert | LNP | ON | LNP+ON | 0.589544 | True | False | False | 5.47222 |
| FARRER | LNP | IND | IND+LNP | 52.8772 | Farrer | LNP | IND | IND+LNP | 0.572936 | True | True | True | 4.41639 |
| DUNKLEY | ALP | ON | ALP+ON | 55.2569 | Dunkley | ALP | ON | ALP+ON | 0.516535 | True | True | True | 3.60336 |
| HAWKE | ON | ALP | ALP+ON | 50.0249 | Hawke | ON | ALP | ALP+ON | 0.535028 | True | True | True | 3.47788 |
| FORREST | LNP | IND | IND+LNP | 50.4318 | Forrest | ON | IND | IND+ON | 0.538949 | False | True | False | 3.46307 |
| MACQUARIE | ALP | ON | ALP+ON | 54.2699 | Macquarie | ALP | ON | ALP+ON | 0.50839 | True | True | True | 3.43095 |
| EDEN-MONARO | ALP | ON | ALP+ON | 53.9163 | Eden-Monaro | ALP | ON | ALP+ON | 0.505583 | True | True | True | 3.35804 |
| MOORE | LNP | ALP | ALP+LNP | 50.8176 | Moore | ALP | LNP | ALP+LNP | 0.54173 | False | False | True | 3.35537 |
| JAGAJAGA | ALP | LNP | ALP+LNP | 62.6059 | Jagajaga | ALP | LNP | ALP+LNP | 0.593517 | True | True | True | 3.25416 |
| ISAACS | ALP | ON | ALP+ON | 61.7935 | Isaacs | ALP | ON | ALP+ON | 0.586821 | True | True | True | 3.11136 |
| STURT | ALP | LNP | ALP+LNP | 54.7999 | Sturt | ALP | LNP | ALP+LNP | 0.516972 | True | True | True | 3.10268 |
| LINGIARI | ALP | ON | ALP+ON | 55.7702 | Lingiari | ALP | ON | ALP+ON | 0.528263 | True | True | True | 2.9439 |
| BALLARAT | ALP | ON | ALP+ON | 57.424 | Ballarat | ALP | ON | ALP+ON | 0.545548 | True | True | True | 2.86924 |
| BRADFIELD | IND | LNP | IND+LNP | 50.1668 | Bradfield | IND | LNP | IND+LNP | 0.530267 | True | True | True | 2.85989 |
| CAPRICORNIA | ON | ALP | ALP+ON | 60.0421 | Capricornia | ON | ALP | ALP+ON | 0.628789 | True | True | True | 2.83679 |
| LONGMAN | ON | ALP | ALP+ON | 54.2654 | Longman | ON | ALP | ALP+ON | 0.570871 | True | True | True | 2.82168 |
| PATERSON | ALP | ON | ALP+ON | 53.1524 | Paterson | ALP | ON | ALP+ON | 0.503996 | True | True | True | 2.75277 |
| BRADDON | ON | ALP | ALP+ON | 50.7991 | Braddon | ON | ALP | ALP+ON | 0.535053 | True | True | True | 2.70623 |
| BRUCE | ALP | ON | ALP+ON | 56.7583 | Bruce | ALP | ON | ALP+ON | 0.540694 | True | True | True | 2.68886 |
| MCMAHON | ALP | ON | ALP+ON | 56.845 | McMahon | ALP | ON | ALP+ON | 0.542191 | True | True | True | 2.62585 |
