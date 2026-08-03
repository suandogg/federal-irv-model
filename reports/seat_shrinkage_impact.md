# Seat Shrinkage Impact Diagnostic

This isolates the effect of `SEAT_SHRINKAGE_K = 1` by comparing it with
`SEAT_SHRINKAGE_K = 0`. All other evidence, class, matrix and nearest-field
settings remain active and unchanged.

`flow_total_variation_pp` is the percentage-point redistribution mass moved
between recipients by shrinkage. `estimated_current_round_effect_pp` also
weights that difference by the eliminated party's vote in the current path.

The suggested `candidate_k_to_test = 0.5` is inactive and is only a review
prompt for Critical and High seats; it is not an automatic override.

## Review counts

| review_priority | seats |
| --- | --- |
| Critical | 4 |
| High | 1 |
| Medium | 39 |
| Low | 105 |

## Highest-priority seats

| division | state | review_priority | current_winner | unshrunk_winner | current_final_two | unshrunk_final_two | max_flow_total_variation_pp | max_estimated_round_effect_pp | most_distinctive_scenario |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Monash | VIC | Critical | IND | LNP | IND+ON | IND+LNP | 18.729 | 1.281 | OTH\|ALP+GRN+IND+LNP+ON |
| Hughes | NSW | Critical | ALP | LNP | ALP+LNP | ALP+LNP | 5.673 | 0.619 | OTH\|ALP+GRN+LNP+ON |
| Moore | WA | Critical | ALP | LNP | ALP+LNP | ALP+LNP | 13.775 | 0.427 | GRN\|ALP+IND+LNP |
| Deakin | VIC | Critical | ALP | LNP | ALP+LNP | ALP+LNP | 7.328 | 0.362 | OTH\|ALP+GRN+IND+LNP+ON |
| Flynn | QLD | High | ON | ON | LNP+ON | ALP+ON | 9.800 | 0.483 | IND\|ALP+GRN+LNP+ON+OTH |
| Bendigo | VIC | Medium | LNP | LNP | ALP+LNP | ALP+LNP | 17.954 | 1.544 | OTH\|ALP+GRN+LNP+ON |
| Fenner | ACT | Medium | ALP | ALP | ALP+GRN | ALP+GRN | 17.248 | 1.376 | OTH\|ALP+GRN+LNP |
| Bean | ACT | Medium | ALP | ALP | ALP+IND | ALP+IND | 7.250 | 1.363 | LNP\|ALP+IND |
| Macnamara | VIC | Medium | ALP | ALP | ALP+LNP | ALP+LNP | 6.994 | 1.222 | OTH\|ALP+GRN+IND+LNP+ON |
| Ryan | QLD | Medium | GRN | GRN | GRN+LNP | GRN+LNP | 6.440 | 1.145 | ON\|ALP+GRN+LNP |
| Boothby | SA | Medium | ALP | ALP | ALP+LNP | ALP+LNP | 8.396 | 1.071 | OTH\|ALP+GRN+LNP+ON |
| Paterson | NSW | Medium | ALP | ALP | ALP+ON | ALP+ON | 10.449 | 1.061 | GRN\|ALP+IND+LNP+ON |
| Lingiari | NT | Medium | ALP | ALP | ALP+ON | ALP+ON | 16.518 | 1.034 | OTH\|ALP+GRN+LNP+ON |
| Whitlam | NSW | Medium | ALP | ALP | ALP+ON | ALP+ON | 10.652 | 1.007 | IND\|ALP+GRN+LNP+ON |
| Fisher | QLD | Medium | LNP | LNP | IND+LNP | IND+LNP | 12.234 | 0.905 | OTH\|ALP+GRN+IND+LNP+ON |
| Banks | NSW | Medium | LNP | LNP | ALP+LNP | ALP+LNP | 10.753 | 0.689 | OTH\|ALP+GRN+LNP+ON |
| Bradfield | NSW | Medium | IND | IND | IND+LNP | IND+LNP | 12.370 | 0.623 | OTH\|ALP+GRN+IND+LNP+ON |
| Lindsay | NSW | Medium | LNP | LNP | ALP+LNP | ALP+LNP | 11.804 | 0.613 | IND\|ALP+GRN+LNP+ON+OTH |
| Melbourne | VIC | Medium | GRN | GRN | ALP+GRN | ALP+GRN | 20.226 | 0.582 | OTH\|ALP+GRN+IND+LNP+ON |
| Solomon | NT | Medium | LNP | LNP | ALP+LNP | ALP+LNP | 14.181 | 0.449 | OTH\|ALP+GRN+IND+LNP+ON |
| Sydney | NSW | Medium | ALP | ALP | ALP+GRN | ALP+GRN | 22.286 | 0.437 | OTH\|ALP+GRN+LNP+ON |
| Fremantle | WA | Medium | ALP | ALP | ALP+IND | ALP+IND | 13.934 | 0.400 | OTH\|ALP+GRN+IND+LNP+ON |
| Flinders | VIC | Medium | LNP | LNP | IND+LNP | IND+LNP | 23.873 | 0.340 | ALP\|IND+LNP |
| Blaxland | NSW | Medium | ALP | ALP | ALP+IND | ALP+IND | 10.349 | 0.296 | IND\|ALP+LNP |
| Parkes | NSW | Medium | ON | ON | LNP+ON | LNP+ON | 10.821 | 0.277 | IND\|ALP+GRN+LNP+ON+OTH |
| Warringah | NSW | Medium | IND | IND | IND+LNP | IND+LNP | 6.815 | 0.253 | OTH\|ALP+GRN+IND+LNP+ON |
| Kooyong | VIC | Medium | IND | IND | IND+LNP | IND+LNP | 12.258 | 0.224 | OTH\|ALP+GRN+IND+LNP+ON |
| Mackellar | NSW | Medium | IND | IND | IND+LNP | IND+LNP | 11.896 | 0.206 | GRN\|ALP+IND+LNP |
| Curtin | WA | Medium | IND | IND | IND+LNP | IND+LNP | 11.324 | 0.183 | OTH\|ALP+GRN+IND+LNP+ON |
| Werriwa | NSW | Medium | ALP | ALP | ALP+ON | ALP+ON | 7.679 | 0.177 | IND\|ALP+GRN+LNP+ON+OTH |
