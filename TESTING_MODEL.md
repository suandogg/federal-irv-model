# Federal Model — testing

Created 14 October 2026 by copying `combined_model_dev`. Original app and source workbook are unchanged. House, Senate and Dashboard remain available; Forecast covers the House only.

## Open the app

From this folder: `python3 -m streamlit run app.py`. Choose **Forecast**, enter national primaries and select **Run House forecast**. Opening Forecast does not run simulations. Results disappear when calculation inputs or source code change.

The isolated testing workbook is https://docs.google.com/spreadsheets/d/11Iu9neJkvUDN0VZioO57BzzmkuGUbXqF-_ghWi2gwxE/edit

- `PARAMS`: existing central federal calculation settings.
- `FORECAST PARAMS`: strict uncertainty/run controls; edit Value in column C.
- `DISPLAY PARAMS`: forecast title, probability decimals, seat-table visibility and party chart colours; edit column C. Invalid presentation values warn and default.

The app reads the testing workbook ID from `sheet_id.txt`; production sheet-ID environment variables cannot redirect it. An explicit `FEDERAL_TESTING_SHEET_ID` override is supported. Live refresh requires the existing service-account credential configuration (`gcp_service_account` in Streamlit secrets or `FEDERAL_IRV_GOOGLE_CREDENTIALS_JSON`) and read access to the new workbook. No secrets were copied. Without credentials the app explicitly uses the committed 14 October connected-workbook snapshot. The Drive connector used during development is not a credential available to a hosted Streamlit process. To host separately, use `testing/app.py` as the entry point and configure those credentials on that deployment.

## Method

Uses the existing production primary builder, partisan strengths, independent presence rules and full candidate-aware IRV count. No simplified simulation-only count, Victorian ON siphoning or Senate probabilities were introduced. Central model parameters remain fixed; no unsupported parameter uncertainty controls are exposed.

National party errors use independent provisional SDs before projection to 100%. State/territory shared errors and seat residuals are rebalanced to preserve each production draw's equal-seat aggregation and structural zeros. These totals need not equal the entered national target because the existing primary builder preserves PVI-anchored GRN/IND geography. Zero support in a production draw remains zero under local noise; candidate eligibility itself is fixed by the existing builder.

Preference perturbation occurs after the federal engine selects central flows. Exact-seat/perfect AEC/exact candidate transfers use exact-source SD; posterior, shrunk and projected candidate evidence use pooled-source SD; other evidence/matrix/ideology/special assumptions use generic SD. One origin/recipient shock is shared across seats and continuing fields, plus a shared classification-specific ON-recipient shock. Candidate transfers are perturbed once, preserving structural zeros. Widths are provisional transport assumptions, not sample-size estimates.

LNP is the Liberal–National Coalition. Majority is derived from the loaded electorate roster (currently 150 seats, majority 76). Formation events overlap and represent arithmetic only. ALP+GRN or ALP+IND routes are counted once; LNP+ON includes an explicit tied-leadership result. Neither bloc reaching majority is reported as arithmetic, not a claim that government cannot form. Independent support is not predicted.

All draw allocations must be complete. Balancing failure aborts the run. Means sum to House size; medians and quantiles need not. A winning margin means winner share above 50%. Monte Carlo errors measure simulation noise only. More draws do not calibrate assumptions; zero simulated wins does not mean impossible.

## Reproduction and outputs

`python3 run_forecast.py` regenerates `reports/forecast/` from the committed snapshot, 200 draws and seed 20261014 using the app's default central scenario: ALP 34.56, LNP 31.82, GRN 12.20, ON 6.40, IND 7.27, OTH 7.75. These are inherited scenario inputs, not current polling estimates.

Downloads include seat probabilities and MCSEs, party seat counts by draw, national primary targets by draw, seat winners by draw and a manifest. The source hash covers every SRC Python file. The calculation fingerprint includes primary/evidence data, model parameters, candidate evidence, central primaries, uncertainty settings and calibration. The UI additionally includes sync status when invalidating cached results. Narrower/wider runs scale SDs only and never edit the workbook.

`python3 -m unittest discover -s tests -p 'test_forecast.py' -v` checks zero-SD full-House winner/margin/2PP parity, reproducibility, immutability, totals, probabilities, structural zeros, government boundaries, strict validation and source-specific preference effects. The full production count is reused without optimisation, so there is no alternate fast-count implementation requiring separate parity.

Live native Sheet values and formatting were read back after creation. The Forecast and DISPLAY PARAMS tabs were also inspected in the browser. Hosted deployment has not been performed.

## Hosted testing deployment

The hosted branch retains the model input data already committed in the existing federal repository. Only app code and non-sensitive forecast/display defaults are newly published. The local connected-workbook snapshot and example-run outputs are not published to GitHub. Live refresh uses the isolated testing workbook once service-account credentials are configured.
