from __future__ import annotations

from pathlib import Path

import pandas as pd

from SRC.loaders import load_params
from shadow_loo_validation import (
    POOL_K_GRID,
    _metrics,
    build_validation_observations,
    pool_observations,
    predict_distribution,
)


ROOT = Path(__file__).resolve().parent
REPORT_OUTPUT = ROOT / "reports" / "nearest_field_validation.csv"
SHEET_OUTPUT = ROOT / "data" / "raw" / "NEAREST_FIELD_VALIDATION.csv"
K_GRID = tuple(sorted(set(POOL_K_GRID + (0.5, 100.0))))


def build_nearest_field_validation() -> pd.DataFrame:
    _, sources = build_validation_observations()
    observations = sources["shadow_pass_through"]
    all_evidence = pool_observations(observations, "__NO_SEAT_EXCLUDED__")
    ideology = load_params().get("ideology", {})
    records = []

    for pool_k in K_GRID:
        metrics = []
        for scenario, by_seat in observations.items():
            evidence = {
                key: value
                for key, value in all_evidence.items()
                if key != scenario
            }
            for target in by_seat.values():
                predicted, match_type, _, _ = predict_distribution(
                    scenario,
                    evidence,
                    ideology,
                    pool_k,
                )
                if match_type != "nearest_field":
                    raise ValueError(
                        f"Scenario holdout did not use nearest-field evidence: {scenario}"
                    )
                metrics.append(_metrics(target["shares"], predicted))
        records.append(
            {
                "NearestFieldShrinkageK": pool_k,
                "Observations": len(metrics),
                "MeanMAE": sum(row["mae"] for row in metrics) / len(metrics),
                "MeanBrier": sum(row["brier"] for row in metrics) / len(metrics),
                "MeanTotalVariation": (
                    sum(row["total_variation"] for row in metrics) / len(metrics)
                ),
                "BrierRank": 0,
                "Selected": False,
            }
        )
    result = pd.DataFrame(records)
    result["BrierRank"] = result["MeanBrier"].rank(method="min").astype(int)
    result["Selected"] = result["BrierRank"].eq(1)
    return result.sort_values("NearestFieldShrinkageK")


def main() -> None:
    result = build_nearest_field_validation()
    REPORT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(REPORT_OUTPUT, index=False)
    result.to_csv(SHEET_OUTPUT, index=False)
    print(result.to_string(index=False))


if __name__ == "__main__":
    main()
