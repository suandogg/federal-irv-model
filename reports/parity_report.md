# Original Sheet Parity Report

This report compares the raw Python IRV engine against the exported original Google Sheets/App Script results in `data/raw/SEAT_PROBS_3CP.csv`.

It deliberately does not use the web-app scenario controls or current `PARTISAN_VOTE_INDEX` sheet. The purpose is to test the preference/IRV port after seat-level primaries have already been fixed.

## Summary

| metric | value |
| --- | --- |
| seats_compared | 150 |
| winner_matches | 150 |
| runner_up_matches | 148 |
| final_two_matches | 146 |
| within_0_01pp | 120 |
| within_0_10pp | 124 |
| within_0_50pp | 138 |
| mean_abs_winner_diff_pp | 0.270712 |
| max_abs_winner_diff_pp | 15.0438 |
| reason_matches_original_sheet | 120 |
| reason_calibration_path_difference | 19 |
| reason_old_sheet_marked_inconsistent | 7 |
| reason_original_sheet_export_not_true_2cp | 2 |
| reason_vote_total_difference_only | 2 |

## Reason Counts

| reason | seats |
| --- | --- |
| matches_original_sheet | 120 |
| calibration_path_difference | 19 |
| old_sheet_marked_inconsistent | 7 |
| original_sheet_export_not_true_2cp | 2 |
| vote_total_difference_only | 2 |

## Largest Differences

| division | reason | sheet_winner | winner_python | winner_no_calibration | sheet_runner_up | runner_up_python | runner_up_no_calibration | sheet_final_two | final_two_python | final_two_no_calibration | sheet_winner_pct | winner_pct_python | winner_pct_no_calibration | winner_diff_pp | winner_diff_pp_no_calibration | runner_diff_pp | sheet_positive_parties | sheet_note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Fenner | original_sheet_export_not_true_2cp | ALP | ALP | ALP | GRN | GRN | GRN | ALP+GRN+LNP | ALP+GRN | ALP+GRN | 0.564855 | 0.715293 | 0.715293 | 15.0438 | 15.0438 | 5.38225 | 3 |  |
| Franklin | old_sheet_marked_inconsistent | ALP | ALP | ALP | IND | IND | IND | ALP+IND | ALP+IND | ALP+IND | 0.558958 | 0.501737 | 0.558958 | 5.72207 | 2.28905e-09 | 5.72207 | 2 | Base merges IND when it should exclude lowest 2 |
| Bean | original_sheet_export_not_true_2cp | ALP | ALP | ALP | IND | IND | IND | ALP+IND+LNP | ALP+IND | ALP+IND | 0.478324 | 0.515514 | 0.515514 | 3.719 | 3.719 | 14.687 | 3 |  |
| Moncrieff | old_sheet_marked_inconsistent | LNP | LNP | LNP | ALP | ON | ALP | ALP+LNP | LNP+ON | ALP+LNP | 0.601565 | 0.570255 | 0.599732 | 3.13099 | 0.183293 | 3.13099 | 2 | Base merges IND when it should exclude lowest 2 |
| Dickson | calibration_path_difference | ALP | ALP | ALP | LNP | LNP | LNP | ALP+LNP | ALP+LNP | ALP+LNP | 0.505964 | 0.524756 | 0.505964 | 1.87921 | 2.06823e-10 | 1.87921 | 2 |  |
| Mayo | calibration_path_difference | OTH | OTH | OTH | ALP | ON | ALP | ALP+OTH | ON+OTH | ALP+OTH | 0.654185 | 0.668453 | 0.654185 | 1.42682 | 1.27575e-09 | 1.42682 | 2 |  |
| Wannon | old_sheet_marked_inconsistent | LNP | LNP | LNP | IND | IND | IND | IND+LNP | IND+LNP | IND+LNP | 0.538732 | 0.526357 | 0.538732 | 1.23748 | 1.32002e-09 | 1.23748 | 2 | Rethrow prefs |
| Groom | old_sheet_marked_inconsistent | LNP | LNP | LNP | IND | IND | IND | IND+LNP | IND+LNP | IND+LNP | 0.534071 | 0.52191 | 0.534071 | 1.21615 | 6.72682e-09 | 1.21615 | 2 | Base merges IND when it should exclude lowest 2 |
| Lindsay | vote_total_difference_only | LNP | LNP | LNP | ALP | ALP | ALP | ALP+LNP | ALP+LNP | ALP+LNP | 0.543576 | 0.532271 | 0.532271 | 1.13045 | 1.13045 | 1.13045 | 2 |  |
| Fairfax | old_sheet_marked_inconsistent | LNP | LNP | LNP | ALP | ALP | ALP | ALP+LNP | ALP+LNP | ALP+LNP | 0.576867 | 0.568983 | 0.576867 | 0.788389 | 1.079e-09 | 0.788389 | 2 | Base merges IND when it should exclude lowest 2 |
| Barker | calibration_path_difference | LNP | LNP | LNP | ON | ON | ON | LNP+ON | LNP+ON | LNP+ON | 0.584741 | 0.577566 | 0.584741 | 0.717497 | 1.59741e-09 | 0.717497 | 2 |  |
| Clark | calibration_path_difference | IND | IND | IND | GRN | GRN | GRN | GRN+IND | GRN+IND | GRN+IND | 0.688768 | 0.694615 | 0.688768 | 0.584686 | 4.68023e-09 | 0.584686 | 2 |  |
| McPherson | old_sheet_marked_inconsistent | LNP | LNP | LNP | ALP | ALP | ALP | ALP+LNP | ALP+LNP | ALP+LNP | 0.57182 | 0.576771 | 0.57182 | 0.495183 | 1.78947e-09 | 0.495183 | 2 | Base merges IND when it should exclude lowest 2 |
| Wright | calibration_path_difference | ON | ON | ON | LNP | LNP | LNP | LNP+ON | LNP+ON | LNP+ON | 0.550105 | 0.554131 | 0.550105 | 0.402577 | 1.12375e-09 | 0.402577 | 2 |  |
| Bowman | calibration_path_difference | LNP | LNP | LNP | ALP | ALP | ALP | ALP+LNP | ALP+LNP | ALP+LNP | 0.551023 | 0.554479 | 0.551023 | 0.345524 | 1.12972e-09 | 0.345524 | 2 |  |
| Bonner | calibration_path_difference | ALP | ALP | ALP | LNP | LNP | LNP | ALP+LNP | ALP+LNP | ALP+LNP | 0.51309 | 0.516494 | 0.51309 | 0.3404 | 1.61317e-09 | 0.3404 | 2 |  |
| Canning | vote_total_difference_only | LNP | LNP | LNP | ALP | ALP | ALP | ALP+LNP | ALP+LNP | ALP+LNP | 0.559055 | 0.562408 | 0.562408 | 0.33536 | 0.33536 | 0.33536 | 2 |  |
| Petrie | calibration_path_difference | LNP | LNP | LNP | ALP | ALP | ALP | ALP+LNP | ALP+LNP | ALP+LNP | 0.520378 | 0.523384 | 0.520378 | 0.300614 | 1.51827e-09 | 0.300614 | 2 |  |
| Lingiari | calibration_path_difference | ALP | ALP | ALP | ON | ON | ON | ALP+ON | ALP+ON | ALP+ON | 0.557702 | 0.554973 | 0.557702 | 0.2729 | 8.9117e-09 | 0.2729 | 2 |  |
| Lyons | calibration_path_difference | ALP | ALP | ALP | ON | ON | ON | ALP+ON | ALP+ON | ALP+ON | 0.540679 | 0.538 | 0.540679 | 0.267909 | 3.31023e-09 | 0.267909 | 2 |  |
| Solomon | calibration_path_difference | ALP | ALP | ALP | LNP | LNP | LNP | ALP+LNP | ALP+LNP | ALP+LNP | 0.510367 | 0.50807 | 0.510367 | 0.229753 | 5.68371e-09 | 0.229753 | 2 |  |
| Canberra | calibration_path_difference | ALP | ALP | ALP | GRN | GRN | GRN | ALP+GRN | ALP+GRN | ALP+GRN | 0.638042 | 0.636049 | 0.638042 | 0.199287 | 5.89011e-09 | 0.199287 | 2 |  |
| Bass | calibration_path_difference | ALP | ALP | ALP | ON | ON | ON | ALP+ON | ALP+ON | ALP+ON | 0.527818 | 0.529506 | 0.528902 | 0.168753 | 0.108358 | 0.036121 | 2 |  |
| Blair | calibration_path_difference | ON | ON | ON | ALP | ALP | ALP | ALP+ON | ALP+ON | ALP+ON | 0.525598 | 0.527104 | 0.525598 | 0.150614 | 1.43877e-09 | 0.150614 | 2 |  |
| Herbert | calibration_path_difference | LNP | LNP | LNP | ALP | ALP | ALP | ALP+LNP | ALP+LNP | ALP+LNP | 0.644266 | 0.642942 | 0.644266 | 0.132427 | 7.37397e-09 | 0.132427 | 2 |  |

