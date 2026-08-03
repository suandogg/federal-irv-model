from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE_DIR = Path("/Users/callumrees/Desktop/federal_irv_model")
EVENT_ID = 31496
DOP_FILE = f"HouseDopByDivisionDownload-{EVENT_ID}.csv"
CLASSIFICATION_FILE = ROOT / "data" / "raw" / "CANDIDATE_CLASSIFICATION.csv"
DERIVED_DIR = ROOT / "data" / "derived"
ROUNDS_OUTPUT = DERIVED_DIR / "AEC_CANDIDATE_ROUNDS_LONG.csv"
TRANSFERS_OUTPUT = DERIVED_DIR / "AEC_CANDIDATE_TRANSFERS_LONG.csv"
CATEGORY_OUTPUT = DERIVED_DIR / "AEC_CATEGORY_EXIT_AUDIT.csv"
SUMMARY_OUTPUT = ROOT / "reports" / "candidate_round_audit_summary.csv"

CATEGORY_ORDER = ["ALP", "LNP", "GRN", "ON", "IND", "OTH"]


def _ordered_categories(values) -> str:
    present = {str(value).strip().upper() for value in values if str(value).strip()}
    ordered = [category for category in CATEGORY_ORDER if category in present]
    ordered.extend(sorted(present - set(CATEGORY_ORDER)))
    return ">".join(ordered)


def _read_dop(path: Path) -> pd.DataFrame:
    dop = pd.read_csv(path, skiprows=1)
    required = {
        "StateAb",
        "DivisionID",
        "DivisionNm",
        "CountNumber",
        "BallotPosition",
        "CandidateID",
        "Surname",
        "GivenNm",
        "PartyAb",
        "PartyNm",
        "Elected",
        "HistoricElected",
        "CalculationType",
        "CalculationValue",
    }
    missing = required - set(dop.columns)
    if missing:
        raise ValueError(f"AEC distribution file is missing columns: {sorted(missing)}")

    dop = dop[dop["CalculationType"].isin(["Preference Count", "Transfer Count"])].copy()
    dop["CalculationValue"] = pd.to_numeric(dop["CalculationValue"], errors="raise")
    index_columns = [
        "StateAb",
        "DivisionID",
        "DivisionNm",
        "CountNumber",
        "BallotPosition",
        "CandidateID",
        "Surname",
        "GivenNm",
        "PartyAb",
        "PartyNm",
        "Elected",
        "HistoricElected",
    ]
    wide = (
        dop.pivot(index=index_columns, columns="CalculationType", values="CalculationValue")
        .reset_index()
        .rename_axis(columns=None)
    )
    if wide[["Preference Count", "Transfer Count"]].isna().any().any():
        raise ValueError("AEC distribution rows did not form complete count/transfer pairs")
    return wide


def _load_classification(path: Path) -> pd.DataFrame:
    classification = pd.read_csv(path)
    required = {
        "State",
        "DivisionID",
        "Electorate",
        "CandidateID",
        "CandidateName",
        "PrimaryVotes",
        "ModelCategory",
        "CandidateSubtype",
        "IdeologyFamily",
    }
    missing = required - set(classification.columns)
    if missing:
        raise ValueError(f"Candidate classification is missing columns: {sorted(missing)}")
    if classification["CandidateID"].duplicated().any():
        raise ValueError("Candidate classification contains duplicate CandidateID values")
    return classification


def _validate_counts(rounds: pd.DataFrame) -> None:
    base = rounds[rounds["CountNumber"].eq(0)]
    if not base["TransferCount"].eq(0).all():
        raise ValueError("AEC count zero contains non-zero transfers")

    exclusion_rounds = rounds[rounds["CountNumber"].gt(0)]
    grouped = exclusion_rounds.groupby(
        ["State", "DivisionID", "Electorate", "CountNumber"],
        sort=False,
    )
    negative_counts = grouped["IsExcludedThisCount"].sum()
    if not negative_counts.eq(1).all():
        bad = negative_counts[~negative_counts.eq(1)].head().to_dict()
        raise ValueError(f"Each AEC exclusion count must exclude one candidate: {bad}")
    transfer_sums = grouped["TransferCount"].sum()
    if not transfer_sums.eq(0).all():
        bad = transfer_sums[~transfer_sums.eq(0)].head().to_dict()
        raise ValueError(f"AEC transfers do not reconcile within counts: {bad}")

    excluded = rounds[rounds["IsExcludedThisCount"]]
    if not excluded["PreferenceCountAfter"].eq(0).all():
        raise ValueError("An excluded candidate retained preferences after exclusion")
    if not excluded["TransferCount"].abs().eq(excluded["PreferenceCountBefore"]).all():
        raise ValueError("Excluded tallies do not reconcile to their negative transfers")


def build_candidate_round_audit(
    source_dir: Path = DEFAULT_SOURCE_DIR,
    classification_path: Path = CLASSIFICATION_FILE,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dop = _read_dop(source_dir / DOP_FILE)
    classification = _load_classification(classification_path)

    class_columns = [
        "CandidateID",
        "State",
        "DivisionID",
        "Electorate",
        "CandidateName",
        "PrimaryVotes",
        "ModelCategory",
        "CandidateSubtype",
        "IdeologyFamily",
    ]
    rounds = dop.merge(
        classification[class_columns],
        on="CandidateID",
        how="left",
        validate="many_to_one",
        suffixes=("AEC", "Class"),
    )
    if rounds["ModelCategory"].isna().any():
        missing = rounds.loc[rounds["ModelCategory"].isna(), "CandidateID"].unique()[:10]
        raise ValueError(f"AEC candidates missing from classification: {missing.tolist()}")
    if not rounds["StateAb"].eq(rounds["State"]).all():
        raise ValueError("AEC state values do not reconcile to candidate classification")
    if not rounds["DivisionNm"].eq(rounds["Electorate"]).all():
        raise ValueError("AEC division names do not reconcile to candidate classification")
    if not rounds["DivisionIDAEC"].eq(rounds["DivisionIDClass"]).all():
        raise ValueError("AEC division IDs do not reconcile to candidate classification")

    rounds = rounds.rename(
        columns={
            "DivisionIDAEC": "DivisionID",
            "PartyAb": "OfficialPartyCode",
            "PartyNm": "OfficialPartyName",
            "Elected": "AEC_Elected",
            "HistoricElected": "AEC_HistoricElected",
            "Preference Count": "PreferenceCountAfter",
            "Transfer Count": "TransferCount",
        }
    ).drop(columns=["StateAb", "DivisionNm", "DivisionIDClass"])
    for column in [
        "DivisionID",
        "CountNumber",
        "BallotPosition",
        "CandidateID",
        "PrimaryVotes",
        "PreferenceCountAfter",
        "TransferCount",
    ]:
        rounds[column] = pd.to_numeric(rounds[column], errors="raise").astype(int)

    rounds["PreferenceCountBefore"] = rounds["PreferenceCountAfter"] - rounds["TransferCount"]
    rounds["IsExcludedThisCount"] = rounds["TransferCount"].lt(0)
    rounds["IsContinuingBefore"] = rounds["PreferenceCountBefore"].gt(0)
    rounds["IsContinuingAfter"] = rounds["PreferenceCountAfter"].gt(0)

    seat_count_columns = ["State", "DivisionID", "Electorate", "CountNumber"]
    round_metadata = []
    for key, group in rounds.groupby(seat_count_columns, sort=False):
        before = group[group["IsContinuingBefore"]]
        after = group[group["IsContinuingAfter"]]
        excluded = group[group["IsExcludedThisCount"]]
        record = dict(zip(seat_count_columns, key))
        record.update(
            {
                "AliveCandidateIDsBefore": ">".join(map(str, sorted(before["CandidateID"]))),
                "AliveCandidateIDsAfter": ">".join(map(str, sorted(after["CandidateID"]))),
                "AliveModelCategoriesBefore": _ordered_categories(before["ModelCategory"]),
                "AliveModelCategoriesAfter": _ordered_categories(after["ModelCategory"]),
                "AliveCandidateCountBefore": len(before),
                "AliveCandidateCountAfter": len(after),
                "AliveCategoryCountBefore": before["ModelCategory"].nunique(),
                "AliveCategoryCountAfter": after["ModelCategory"].nunique(),
                "ExcludedCandidateID": (
                    int(excluded.iloc[0]["CandidateID"]) if len(excluded) else pd.NA
                ),
            }
        )
        round_metadata.append(record)
    rounds = rounds.merge(pd.DataFrame(round_metadata), on=seat_count_columns, validate="many_to_one")

    same_category_after = []
    for _, row in rounds.iterrows():
        if not row["IsExcludedThisCount"]:
            same_category_after.append(0)
            continue
        peers = rounds[
            rounds[seat_count_columns].eq(row[seat_count_columns]).all(axis=1)
            & rounds["ModelCategory"].eq(row["ModelCategory"])
            & rounds["IsContinuingAfter"]
        ]
        same_category_after.append(len(peers))
    rounds["SameCategoryCandidatesAliveAfter"] = same_category_after
    rounds["InternalCategoryExclusion"] = (
        rounds["IsExcludedThisCount"]
        & rounds["SameCategoryCandidatesAliveAfter"].gt(0)
    )
    rounds["CategoryExitThisCount"] = (
        rounds["IsExcludedThisCount"]
        & rounds["SameCategoryCandidatesAliveAfter"].eq(0)
    )

    _validate_counts(rounds)

    category_records = []
    seat_columns = ["State", "DivisionID", "Electorate"]
    for seat_key, seat_group in rounds.groupby(seat_columns, sort=False):
        base = seat_group[seat_group["CountNumber"].eq(0)]
        last_count = seat_group["CountNumber"].max()
        final = seat_group[
            seat_group["CountNumber"].eq(last_count) & seat_group["IsContinuingAfter"]
        ]
        if len(final) != 2:
            raise ValueError(f"AEC count did not finish with two candidates in {seat_key}")
        if final["ModelCategory"].nunique() != 2:
            raise ValueError(f"Both AEC finalists map to one model category in {seat_key}")

        winner = final[final["AEC_Elected"].eq("Y")]
        if len(winner) != 1:
            raise ValueError(f"AEC final count has no unique elected candidate in {seat_key}")
        winner_id = int(winner.iloc[0]["CandidateID"])

        for category, category_group in seat_group.groupby("ModelCategory", sort=False):
            category_base = base[base["ModelCategory"].eq(category)]
            exits = category_group[category_group["CategoryExitThisCount"]]
            if len(exits) > 1:
                raise ValueError(f"A model category exits more than once in {seat_key}: {category}")
            if len(exits) == 1:
                last_survivor = exits.iloc[0]
                exit_count = int(last_survivor["CountNumber"])
                finish_position = int(last_survivor["AliveCategoryCountAfter"]) + 1
            else:
                category_final = final[final["ModelCategory"].eq(category)]
                if len(category_final) != 1:
                    raise ValueError(f"Final category has no unique survivor in {seat_key}: {category}")
                last_survivor = category_final.iloc[0]
                exit_count = pd.NA
                finish_position = 1 if int(last_survivor["CandidateID"]) == winner_id else 2

            category_records.append(
                {
                    **dict(zip(seat_columns, seat_key)),
                    "ModelCategory": category,
                    "CandidateCount": int(category_base["CandidateID"].nunique()),
                    "PrimaryVotes": int(category_base["PrimaryVotes"].sum()),
                    "FinishPosition": finish_position,
                    "CategoryExitCount": exit_count,
                    "LastSurvivingCandidateID": int(last_survivor["CandidateID"]),
                    "LastSurvivingCandidate": last_survivor["CandidateName"],
                    "LastSurvivingSubtype": last_survivor["CandidateSubtype"],
                    "LastSurvivingIdeologyFamily": last_survivor["IdeologyFamily"],
                    "InternalCandidateExclusions": int(
                        category_group["InternalCategoryExclusion"].sum()
                    ),
                }
            )
    categories = pd.DataFrame(category_records)
    seat_primary_totals = categories.groupby(seat_columns)["PrimaryVotes"].transform("sum")
    categories["PrimaryShare"] = categories["PrimaryVotes"] / seat_primary_totals

    rounds = rounds.merge(
        categories[
            seat_columns
            + [
                "ModelCategory",
                "FinishPosition",
                "CategoryExitCount",
                "LastSurvivingCandidateID",
            ]
        ],
        on=seat_columns + ["ModelCategory"],
        how="left",
        validate="many_to_one",
    )

    transfer_records = []
    for key, group in rounds[rounds["CountNumber"].gt(0)].groupby(seat_count_columns, sort=False):
        excluded = group[group["IsExcludedThisCount"]].iloc[0]
        recipients = group[group["TransferCount"].gt(0)]
        excluded_tally = int(excluded["PreferenceCountBefore"])
        for _, recipient in recipients.iterrows():
            transfer_records.append(
                {
                    **dict(zip(seat_count_columns, key)),
                    "EliminatedCandidateID": int(excluded["CandidateID"]),
                    "EliminatedCandidate": excluded["CandidateName"],
                    "EliminatedModelCategory": excluded["ModelCategory"],
                    "EliminatedCandidateSubtype": excluded["CandidateSubtype"],
                    "EliminatedIdeologyFamily": excluded["IdeologyFamily"],
                    "EliminatedTally": excluded_tally,
                    "InternalCategoryExclusion": bool(excluded["InternalCategoryExclusion"]),
                    "CategoryExitThisCount": bool(excluded["CategoryExitThisCount"]),
                    "RecipientCandidateID": int(recipient["CandidateID"]),
                    "RecipientCandidate": recipient["CandidateName"],
                    "RecipientModelCategory": recipient["ModelCategory"],
                    "RecipientCandidateSubtype": recipient["CandidateSubtype"],
                    "RecipientIdeologyFamily": recipient["IdeologyFamily"],
                    "TransferVotes": int(recipient["TransferCount"]),
                    "TransferShare": float(recipient["TransferCount"] / excluded_tally),
                    "SameCategoryTransfer": bool(
                        excluded["ModelCategory"] == recipient["ModelCategory"]
                    ),
                    "AliveModelCategoriesAfter": excluded["AliveModelCategoriesAfter"],
                }
            )
    transfers = pd.DataFrame(transfer_records)

    summary = pd.DataFrame(
        [
            ("Seats", rounds[["State", "DivisionID"]].drop_duplicates().shape[0]),
            ("Candidates", rounds["CandidateID"].nunique()),
            ("AEC exclusion rounds", int(rounds["IsExcludedThisCount"].sum())),
            ("Internal same-category exclusions", int(rounds["InternalCategoryExclusion"].sum())),
            ("Category exits", int(rounds["CategoryExitThisCount"].sum())),
            (
                "Seats with duplicate model categories",
                int(categories["CandidateCount"].gt(1).groupby(
                    [categories["State"], categories["DivisionID"]]
                ).any().sum()),
            ),
            ("Transfer edges", len(transfers)),
        ],
        columns=["Metric", "Value"],
    )

    round_columns = [
        "State",
        "DivisionID",
        "Electorate",
        "CountNumber",
        "CandidateID",
        "BallotPosition",
        "CandidateName",
        "OfficialPartyCode",
        "OfficialPartyName",
        "ModelCategory",
        "CandidateSubtype",
        "IdeologyFamily",
        "PrimaryVotes",
        "PreferenceCountBefore",
        "TransferCount",
        "PreferenceCountAfter",
        "IsExcludedThisCount",
        "InternalCategoryExclusion",
        "CategoryExitThisCount",
        "SameCategoryCandidatesAliveAfter",
        "IsContinuingBefore",
        "IsContinuingAfter",
        "AliveCandidateCountBefore",
        "AliveCandidateCountAfter",
        "AliveCategoryCountBefore",
        "AliveCategoryCountAfter",
        "AliveCandidateIDsBefore",
        "AliveCandidateIDsAfter",
        "AliveModelCategoriesBefore",
        "AliveModelCategoriesAfter",
        "FinishPosition",
        "CategoryExitCount",
        "LastSurvivingCandidateID",
        "AEC_Elected",
        "AEC_HistoricElected",
    ]
    rounds = rounds[round_columns].sort_values(
        ["State", "Electorate", "CountNumber", "BallotPosition"]
    )
    transfers = transfers.sort_values(
        ["State", "Electorate", "CountNumber", "RecipientCandidateID"]
    )
    categories = categories.sort_values(["State", "Electorate", "FinishPosition"])
    return rounds, transfers, categories, summary


def write_outputs(
    rounds: pd.DataFrame,
    transfers: pd.DataFrame,
    categories: pd.DataFrame,
    summary: pd.DataFrame,
) -> None:
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    rounds.to_csv(ROUNDS_OUTPUT, index=False)
    transfers.to_csv(TRANSFERS_OUTPUT, index=False)
    categories.to_csv(CATEGORY_OUTPUT, index=False)
    summary.to_csv(SUMMARY_OUTPUT, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile exact AEC candidate rounds and model-category exit metadata."
    )
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--classification", type=Path, default=CLASSIFICATION_FILE)
    args = parser.parse_args()

    outputs = build_candidate_round_audit(args.source_dir, args.classification)
    write_outputs(*outputs)
    print(outputs[3].to_string(index=False))


if __name__ == "__main__":
    main()
