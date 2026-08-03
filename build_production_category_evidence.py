from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from SRC.evidence import normalise_distribution
from SRC.loaders import division_key, load_category_flow_overrides
from build_shadow_category_flows import (
    DIRECT_METHOD,
    FLOW_OUTPUT,
    PASS_THROUGH_METHOD,
)


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
SEAT_FLOW_OUTPUT = RAW_DIR / "CATEGORY_PREF_FLOWS_LONG.csv"
SCENARIO_OUTPUT = RAW_DIR / "CATEGORY_SCENARIO_STATS.csv"


def _alive_key(value: str) -> str:
    parties = {
        party.strip().upper()
        for party in str(value or "").replace(">", "+").replace("|", "+").split("+")
        if party.strip()
    }
    return "+".join(sorted(parties))


def build_production_category_evidence(
    shadow_path: Path = FLOW_OUTPUT,
    default_method: str = PASS_THROUGH_METHOD,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    default_method = str(default_method or PASS_THROUGH_METHOD).strip().upper()
    if default_method not in {DIRECT_METHOD, PASS_THROUGH_METHOD}:
        raise ValueError(f"Unsupported default category-flow method: {default_method}")
    flows = pd.read_csv(shadow_path)
    overrides = load_category_flow_overrides()
    key_columns = [
        "State",
        "DivisionID",
        "Electorate",
        "EliminatedModelCategory",
        "AliveModelCategoriesAfter",
    ]
    records = []

    for key, scenario_rows in flows.groupby(key_columns, sort=False):
        metadata = dict(zip(key_columns, key))
        seat_key = division_key(metadata["Electorate"])
        eliminated = metadata["EliminatedModelCategory"]
        alive_original = str(metadata["AliveModelCategoriesAfter"]).strip().upper()
        override = overrides.get((seat_key, eliminated, alive_original), {})
        selected_method = str(override.get("method") or default_method).upper()
        if selected_method not in {DIRECT_METHOD, PASS_THROUGH_METHOD}:
            selected_method = DIRECT_METHOD
        selected = scenario_rows[scenario_rows["Method"].eq(selected_method)]
        if selected.empty:
            raise ValueError(f"No {selected_method} rows for {key}")

        reference = selected.iloc[0]
        alive = _alive_key(alive_original)
        alive_parties = alive.split("+")
        shares = normalise_distribution(
            {
                row["RecipientModelCategory"]: float(row["Share"])
                for _, row in selected.iterrows()
            },
            alive_parties,
        )
        # Pass-through traces the full combined category primary, so it has
        # complete category coverage. Coverage downweighting only applies to
        # the direct last-survivor method, which observes a subset when a
        # category contains multiple candidates.
        default_multiplier = (
            1.0
            if selected_method == PASS_THROUGH_METHOD
            else float(reference["DefaultEvidenceMultiplier"])
        )
        effective_multiplier = override.get("evidence_multiplier")
        if effective_multiplier is None:
            effective_multiplier = default_multiplier
        effective_multiplier = max(0.0, min(1.0, float(effective_multiplier)))

        allocated_by_recipient = {
            row["RecipientModelCategory"]: float(row["AllocatedVotes"])
            for _, row in selected.iterrows()
        }
        evidence_votes = float(reference["EvidenceVotes"])
        for recipient in alive_parties:
            records.append(
                {
                    "Seat": metadata["Electorate"],
                    "State": metadata["State"],
                    "DivisionID": int(metadata["DivisionID"]),
                    "Eliminated": eliminated,
                    "AliveSet": alive,
                    "Recipient": recipient,
                    "Votes": allocated_by_recipient.get(
                        recipient,
                        shares[recipient] * evidence_votes,
                    ),
                    "ScenarioTotal": evidence_votes,
                    "Share": shares[recipient],
                    "Method": selected_method,
                    "VoteBasis": reference["VoteBasis"],
                    "CandidateCount": int(reference["CandidateCount"]),
                    "LastSurvivorCandidate": reference["LastSurvivorCandidate"],
                    "LastSurvivorSubtype": reference["LastSurvivorSubtype"],
                    "LastSurvivorIdeologyFamily": reference["LastSurvivorIdeologyFamily"],
                    "LastSurvivorPrimaryCoverage": float(
                        reference["LastSurvivorPrimaryCoverage"]
                    ),
                    "DefaultEvidenceMultiplier": default_multiplier,
                    "EffectiveEvidenceMultiplier": effective_multiplier,
                    "OverrideApplied": bool(override),
                    "Source": "AEC_CANDIDATE_ROUNDS_CATEGORY_EXIT",
                }
            )

    seat_flows = pd.DataFrame(records).sort_values(
        ["State", "Seat", "Eliminated", "AliveSet", "Recipient"]
    )

    scenario_records = []
    for (eliminated, alive), group in seat_flows.groupby(
        ["Eliminated", "AliveSet"], sort=False
    ):
        alive_parties = alive.split("+")
        by_seat = group.pivot_table(
            index="Seat",
            columns="Recipient",
            values="Share",
            fill_value=0.0,
        ).reindex(columns=alive_parties, fill_value=0.0)
        means = by_seat.mean(axis=0)
        variances = by_seat.var(axis=0, ddof=1).fillna(0.0)
        seats = len(by_seat)
        votes_by_recipient = group.groupby("Recipient")["Votes"].sum()
        scenario_total = group.groupby("Seat")["ScenarioTotal"].first().sum()
        for recipient in alive_parties:
            scenario_records.append(
                {
                    "Eliminated": eliminated,
                    "AliveSet": alive,
                    "Recipient": recipient,
                    "Votes": float(votes_by_recipient.get(recipient, 0.0)),
                    "ScenarioTotal": float(scenario_total),
                    "Share": float(means.get(recipient, 0.0)),
                    "Seats": seats,
                    "SeatObservations": seats,
                    "BetweenSeatVariance": float(variances.get(recipient, 0.0)),
                    "PoolingWeight": "EQUAL_SEAT",
                    "Source": "CATEGORY_PREF_FLOWS_LONG",
                }
            )
    scenario_stats = pd.DataFrame(scenario_records).sort_values(
        ["Eliminated", "AliveSet", "Recipient"]
    )
    return seat_flows, scenario_stats


def write_outputs(
    seat_flows: pd.DataFrame,
    scenario_stats: pd.DataFrame,
) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    seat_flows.to_csv(SEAT_FLOW_OUTPUT, index=False)
    scenario_stats.to_csv(SCENARIO_OUTPUT, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build canonical production category-flow evidence."
    )
    parser.add_argument("--shadow-flows", type=Path, default=FLOW_OUTPUT)
    parser.add_argument(
        "--default-method",
        choices=[DIRECT_METHOD, PASS_THROUGH_METHOD],
        default=PASS_THROUGH_METHOD,
    )
    args = parser.parse_args()
    outputs = build_production_category_evidence(
        args.shadow_flows,
        default_method=args.default_method,
    )
    write_outputs(*outputs)
    print(f"Seat flow rows: {len(outputs[0])}")
    print(f"Scenario statistic rows: {len(outputs[1])}")


if __name__ == "__main__":
    main()
