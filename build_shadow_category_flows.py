from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import pandas as pd

from build_candidate_round_audit import (
    CATEGORY_ORDER,
    CLASSIFICATION_FILE,
    DEFAULT_SOURCE_DIR,
    build_candidate_round_audit,
)


ROOT = Path(__file__).resolve().parent
DERIVED_DIR = ROOT / "data" / "derived"
FLOW_OUTPUT = DERIVED_DIR / "SHADOW_CATEGORY_FLOWS_LONG.csv"
COMPARISON_OUTPUT = ROOT / "reports" / "shadow_category_flow_comparison.csv"
IMPACT_OUTPUT = ROOT / "reports" / "shadow_category_flow_impact_by_seat.csv"
SUMMARY_OUTPUT = ROOT / "reports" / "shadow_category_flow_summary.csv"
OVERRIDES_OUTPUT = ROOT / "data" / "raw" / "CATEGORY_FLOW_OVERRIDES.csv"
DIAGNOSTIC_OUTPUT = ROOT / "data" / "raw" / "CATEGORY_FLOW_DIAGNOSTIC.csv"

DIRECT_METHOD = "OBSERVED_LAST_SURVIVOR_EXIT"
PASS_THROUGH_METHOD = "PROPORTIONAL_PRIMARY_ORIGIN_PASS_THROUGH"


def _ordered_categories(values) -> str:
    present = {str(value).strip().upper() for value in values if str(value).strip()}
    ordered = [category for category in CATEGORY_ORDER if category in present]
    ordered.extend(sorted(present - set(CATEGORY_ORDER)))
    return ">".join(ordered)


def _weighted_mix(group: pd.DataFrame, column: str) -> str:
    values = group.copy()
    values[column] = values[column].fillna("").astype(str).str.strip().str.upper()
    values.loc[values[column].eq(""), column] = "UNSPECIFIED"
    totals = values.groupby(column, dropna=False)["PrimaryVotes"].sum().sort_values(ascending=False)
    return "|".join(f"{label}:{int(votes)}" for label, votes in totals.items())


def _base_metadata(
    seat_categories: pd.DataFrame,
    base_candidates: pd.DataFrame,
    eliminated_category: str,
    alive_after: str,
) -> dict:
    category = seat_categories[
        seat_categories["ModelCategory"].eq(eliminated_category)
    ].iloc[0]
    candidates = base_candidates[
        base_candidates["ModelCategory"].eq(eliminated_category)
    ]
    last_survivor = candidates[
        candidates["CandidateID"].eq(int(category["LastSurvivingCandidateID"]))
    ].iloc[0]
    category_primary = int(category["PrimaryVotes"])
    last_primary = int(last_survivor["PrimaryVotes"])
    candidate_count = int(category["CandidateCount"])
    coverage = last_primary / category_primary
    return {
        "State": category["State"],
        "DivisionID": int(category["DivisionID"]),
        "Electorate": category["Electorate"],
        "EliminatedModelCategory": eliminated_category,
        "FinishPosition": int(category["FinishPosition"]),
        "CategoryExitCount": int(category["CategoryExitCount"]),
        "AliveModelCategoriesAfter": alive_after,
        "CandidateCount": candidate_count,
        "InternalCandidateExclusions": int(category["InternalCandidateExclusions"]),
        "CategoryPrimaryVotes": category_primary,
        "LastSurvivorCandidateID": int(last_survivor["CandidateID"]),
        "LastSurvivorCandidate": last_survivor["CandidateName"],
        "LastSurvivorSubtype": last_survivor["CandidateSubtype"],
        "LastSurvivorIdeologyFamily": (
            str(last_survivor["IdeologyFamily"]).strip().upper()
            if pd.notna(last_survivor["IdeologyFamily"])
            else ""
        ),
        "LastSurvivorPrimaryVotes": last_primary,
        "LastSurvivorPrimaryCoverage": coverage,
        "DefaultEvidenceMultiplier": coverage if candidate_count > 1 else 1.0,
        "CategorySubtypeMix": _weighted_mix(candidates, "CandidateSubtype"),
        "CategoryIdeologyMix": _weighted_mix(candidates, "IdeologyFamily"),
    }


def compile_shadow_category_flows(
    source_dir: Path = DEFAULT_SOURCE_DIR,
    classification_path: Path = CLASSIFICATION_FILE,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rounds, _, categories, _ = build_candidate_round_audit(
        source_dir=source_dir,
        classification_path=classification_path,
    )
    records = []

    seat_columns = ["State", "DivisionID", "Electorate"]
    for seat_key, seat_rounds in rounds.groupby(seat_columns, sort=False):
        seat_rounds = seat_rounds.sort_values(["CountNumber", "BallotPosition"])
        base = seat_rounds[seat_rounds["CountNumber"].eq(0)].copy()
        seat_categories = categories[
            categories[seat_columns].eq(pd.Series(seat_key, index=seat_columns)).all(axis=1)
        ]

        candidate_category = base.set_index("CandidateID")["ModelCategory"].to_dict()
        candidate_primary = base.set_index("CandidateID")["PrimaryVotes"].astype(float).to_dict()
        holdings: dict[int, dict[int, float]] = {
            int(candidate_id): {int(candidate_id): float(primary)}
            for candidate_id, primary in candidate_primary.items()
        }

        for count_number in sorted(seat_rounds.loc[seat_rounds["CountNumber"].gt(0), "CountNumber"].unique()):
            count_rows = seat_rounds[seat_rounds["CountNumber"].eq(count_number)]
            eliminated = count_rows[count_rows["IsExcludedThisCount"]].iloc[0]
            eliminated_id = int(eliminated["CandidateID"])
            eliminated_tally = float(eliminated["PreferenceCountBefore"])
            provenance = holdings[eliminated_id]
            if abs(sum(provenance.values()) - eliminated_tally) > 1e-6:
                raise ValueError(
                    f"Provenance does not reconcile before {seat_key} count {count_number}"
                )

            recipients = count_rows[count_rows["TransferCount"].gt(0)].copy()
            recipients["RoundShare"] = recipients["TransferCount"] / eliminated_tally
            if abs(float(recipients["RoundShare"].sum()) - 1.0) > 1e-9:
                raise ValueError(
                    f"Recipient shares do not sum to one in {seat_key} count {count_number}"
                )

            if bool(eliminated["CategoryExitThisCount"]):
                direct_by_category = recipients.groupby("ModelCategory")["TransferCount"].sum()
                metadata = _base_metadata(
                    seat_categories,
                    base,
                    eliminated["ModelCategory"],
                    eliminated["AliveModelCategoriesAfter"],
                )
                for recipient_category, transfer_votes in direct_by_category.items():
                    records.append(
                        {
                            **metadata,
                            "Method": DIRECT_METHOD,
                            "VoteBasis": "LAST_SURVIVOR_TALLY_AT_CATEGORY_EXIT",
                            "EvidenceVotes": int(eliminated_tally),
                            "RecipientModelCategory": recipient_category,
                            "AllocatedVotes": float(transfer_votes),
                            "Share": float(transfer_votes / eliminated_tally),
                            "IsApproximation": False,
                        }
                    )

            for _, recipient in recipients.iterrows():
                recipient_id = int(recipient["CandidateID"])
                share = float(recipient["RoundShare"])
                destination = holdings[recipient_id]
                for origin_id, amount in provenance.items():
                    destination[origin_id] = destination.get(origin_id, 0.0) + amount * share
            holdings[eliminated_id] = {}

            if bool(eliminated["CategoryExitThisCount"]):
                eliminated_category = eliminated["ModelCategory"]
                origin_ids = [
                    candidate_id
                    for candidate_id, category in candidate_category.items()
                    if category == eliminated_category
                ]
                allocated = defaultdict(float)
                for holder_id, holder_provenance in holdings.items():
                    destination_category = candidate_category[holder_id]
                    for origin_id in origin_ids:
                        allocated[destination_category] += holder_provenance.get(origin_id, 0.0)

                category_primary = sum(candidate_primary[origin_id] for origin_id in origin_ids)
                if abs(sum(allocated.values()) - category_primary) > 1e-6:
                    raise ValueError(
                        f"Category-origin votes do not reconcile in {seat_key}: {eliminated_category}"
                    )
                allocated = defaultdict(
                    float,
                    {
                        category: amount
                        for category, amount in allocated.items()
                        if amount > 1e-9
                    },
                )
                alive_categories = set(
                    str(eliminated["AliveModelCategoriesAfter"]).split(">")
                )
                if not set(allocated).issubset(alive_categories):
                    raise ValueError(
                        f"Pass-through destinations are not alive in {seat_key}: {eliminated_category}"
                    )

                metadata = _base_metadata(
                    seat_categories,
                    base,
                    eliminated_category,
                    eliminated["AliveModelCategoriesAfter"],
                )
                for recipient_category, allocated_votes in allocated.items():
                    if allocated_votes <= 1e-9:
                        continue
                    records.append(
                        {
                            **metadata,
                            "Method": PASS_THROUGH_METHOD,
                            "VoteBasis": "ALL_CATEGORY_PRIMARY_VOTES_TRACED_PROPORTIONALLY",
                            "EvidenceVotes": int(category_primary),
                            "RecipientModelCategory": recipient_category,
                            "AllocatedVotes": float(allocated_votes),
                            "Share": float(allocated_votes / category_primary),
                            "IsApproximation": True,
                        }
                    )

        total_holdings = sum(
            amount
            for holder in holdings.values()
            for amount in holder.values()
        )
        if abs(total_holdings - sum(candidate_primary.values())) > 1e-6:
            raise ValueError(f"Final provenance does not reconcile in {seat_key}")

    flows = pd.DataFrame(records).sort_values(
        ["State", "Electorate", "FinishPosition", "Method", "RecipientModelCategory"]
    )
    key_columns = [
        "State",
        "DivisionID",
        "Electorate",
        "EliminatedModelCategory",
        "FinishPosition",
        "CategoryExitCount",
        "AliveModelCategoriesAfter",
        "RecipientModelCategory",
    ]
    comparison = (
        flows.pivot_table(index=key_columns, columns="Method", values="Share", fill_value=0.0)
        .reset_index()
        .rename_axis(columns=None)
    )
    comparison = comparison.rename(
        columns={
            DIRECT_METHOD: "ObservedExitShare",
            PASS_THROUGH_METHOD: "PassThroughShare",
        }
    )
    comparison["ObservedExitShare"] = comparison.get("ObservedExitShare", 0.0)
    comparison["PassThroughShare"] = comparison.get("PassThroughShare", 0.0)
    comparison["ShareDelta"] = (
        comparison["PassThroughShare"] - comparison["ObservedExitShare"]
    )
    comparison["AbsoluteShareDelta"] = comparison["ShareDelta"].abs()

    scenario_columns = key_columns[:-1]
    impact_records = []
    for scenario_key, group in comparison.groupby(scenario_columns, sort=False):
        observed = group.set_index("RecipientModelCategory")["ObservedExitShare"]
        passed = group.set_index("RecipientModelCategory")["PassThroughShare"]
        direct_winner = observed.idxmax()
        pass_winner = passed.idxmax()
        source = flows[
            flows[scenario_columns].eq(pd.Series(scenario_key, index=scenario_columns)).all(axis=1)
        ].iloc[0]
        impact_records.append(
            {
                **dict(zip(scenario_columns, scenario_key)),
                "CandidateCount": int(source["CandidateCount"]),
                "InternalCandidateExclusions": int(source["InternalCandidateExclusions"]),
                "LastSurvivorCandidate": source["LastSurvivorCandidate"],
                "LastSurvivorSubtype": source["LastSurvivorSubtype"],
                "LastSurvivorIdeologyFamily": source["LastSurvivorIdeologyFamily"],
                "LastSurvivorPrimaryCoverage": float(source["LastSurvivorPrimaryCoverage"]),
                "TotalVariationDistance": float(group["AbsoluteShareDelta"].sum() / 2.0),
                "MaximumRecipientDelta": float(group["AbsoluteShareDelta"].max()),
                "ObservedDominantRecipient": direct_winner,
                "PassThroughDominantRecipient": pass_winner,
                "DominantRecipientChanged": direct_winner != pass_winner,
            }
        )
    impact = pd.DataFrame(impact_records).sort_values(
        ["TotalVariationDistance", "MaximumRecipientDelta"], ascending=False
    )

    summary = pd.DataFrame(
        [
            ("Category-exit scenarios", len(impact)),
            ("Single-candidate category exits", int(impact["CandidateCount"].eq(1).sum())),
            ("Multi-candidate category exits", int(impact["CandidateCount"].gt(1).sum())),
            (
                "Scenarios with dominant recipient changed",
                int(impact["DominantRecipientChanged"].sum()),
            ),
            (
                "Scenarios with total variation >= 5pp",
                int(impact["TotalVariationDistance"].ge(0.05).sum()),
            ),
            (
                "Scenarios with total variation >= 10pp",
                int(impact["TotalVariationDistance"].ge(0.10).sum()),
            ),
            ("Maximum total variation", float(impact["TotalVariationDistance"].max())),
        ],
        columns=["Metric", "Value"],
    )
    return flows, comparison, impact, summary


def build_category_flow_diagnostic(impact: pd.DataFrame) -> pd.DataFrame:
    diagnostic = impact[impact["CandidateCount"].gt(1)].copy()
    diagnostic["DefaultMethod"] = DIRECT_METHOD
    diagnostic["DefaultEvidenceMultiplier"] = diagnostic["LastSurvivorPrimaryCoverage"]
    diagnostic["ReviewPriority"] = "LOW"
    diagnostic.loc[
        diagnostic["TotalVariationDistance"].ge(0.05), "ReviewPriority"
    ] = "MEDIUM"
    diagnostic.loc[
        diagnostic["TotalVariationDistance"].ge(0.10), "ReviewPriority"
    ] = "HIGH"
    diagnostic.loc[
        diagnostic["DominantRecipientChanged"]
        | diagnostic["TotalVariationDistance"].ge(0.15),
        "ReviewPriority",
    ] = "CRITICAL"
    columns = [
        "ReviewPriority",
        "State",
        "DivisionID",
        "Electorate",
        "EliminatedModelCategory",
        "FinishPosition",
        "AliveModelCategoriesAfter",
        "CandidateCount",
        "InternalCandidateExclusions",
        "LastSurvivorCandidate",
        "LastSurvivorSubtype",
        "LastSurvivorIdeologyFamily",
        "LastSurvivorPrimaryCoverage",
        "DefaultEvidenceMultiplier",
        "TotalVariationDistance",
        "MaximumRecipientDelta",
        "ObservedDominantRecipient",
        "PassThroughDominantRecipient",
        "DominantRecipientChanged",
        "DefaultMethod",
    ]
    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    diagnostic["_priority"] = diagnostic["ReviewPriority"].map(priority_order)
    return diagnostic.sort_values(
        ["_priority", "TotalVariationDistance"], ascending=[True, False]
    )[columns]


def build_category_flow_overrides(
    impact: pd.DataFrame,
    existing_path: Path = OVERRIDES_OUTPUT,
) -> pd.DataFrame:
    diagnostic = build_category_flow_diagnostic(impact)
    key_columns = [
        "State",
        "DivisionID",
        "Electorate",
        "EliminatedModelCategory",
        "AliveModelCategoriesAfter",
    ]
    overrides = diagnostic[
        key_columns
        + [
            "CandidateCount",
            "LastSurvivorCandidate",
            "LastSurvivorPrimaryCoverage",
            "DefaultEvidenceMultiplier",
            "TotalVariationDistance",
            "ReviewPriority",
        ]
    ].copy()
    overrides["UseOverride"] = "FALSE"
    overrides["EvidenceMultiplierOverride"] = ""
    overrides["MethodOverride"] = ""
    overrides["AnalystNotes"] = ""

    editable = [
        "UseOverride",
        "EvidenceMultiplierOverride",
        "MethodOverride",
        "AnalystNotes",
    ]
    if existing_path.exists():
        existing = pd.read_csv(existing_path, dtype=str).fillna("")
        if set(key_columns + editable).issubset(existing.columns):
            existing = existing[key_columns + editable].drop_duplicates(key_columns, keep="last")
            overrides = overrides.drop(columns=editable).merge(
                existing,
                on=key_columns,
                how="left",
                validate="one_to_one",
            )
            overrides["UseOverride"] = overrides["UseOverride"].replace("", "FALSE")
            for column in editable:
                overrides[column] = overrides[column].fillna("")
    return overrides


def write_outputs(
    flows: pd.DataFrame,
    comparison: pd.DataFrame,
    impact: pd.DataFrame,
    summary: pd.DataFrame,
) -> None:
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    COMPARISON_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    flows.to_csv(FLOW_OUTPUT, index=False)
    comparison.to_csv(COMPARISON_OUTPUT, index=False)
    impact.to_csv(IMPACT_OUTPUT, index=False)
    summary.to_csv(SUMMARY_OUTPUT, index=False)
    build_category_flow_diagnostic(impact).to_csv(DIAGNOSTIC_OUTPUT, index=False)
    build_category_flow_overrides(impact).to_csv(OVERRIDES_OUTPUT, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile and compare direct and pass-through category flows."
    )
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--classification", type=Path, default=CLASSIFICATION_FILE)
    args = parser.parse_args()

    outputs = compile_shadow_category_flows(args.source_dir, args.classification)
    write_outputs(*outputs)
    print(outputs[3].to_string(index=False))


if __name__ == "__main__":
    main()
