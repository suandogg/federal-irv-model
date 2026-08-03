from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
DEFAULT_SOURCE_DIR = Path("/Users/callumrees/Desktop/federal_irv_model")
EVENT_ID = 31496
ELECTION_YEAR = 2025

CANDIDATES_FILE = f"HouseCandidatesDownload-{EVENT_ID}.csv"
FIRST_PREFS_FILE = f"HouseFirstPrefsByCandidateByVoteTypeDownload-{EVENT_ID}.csv"
FLOW_REPORT_FILE = "FED2025_PreferenceFlowReport.pdf"
OUTPUT_FILE = RAW_DIR / "CANDIDATE_CLASSIFICATION.csv"

COALITION_CODES = {"LP", "LIB", "NP", "NAT", "LNP", "CLP"}
ALP_CODES = {"ALP"}
GRN_CODES = {"GRN", "GVIC"}

PDF_DIVISION_HEADING = re.compile(r"^(.+?) \(([A-Z]{2,3})\)$")
PDF_TWO_PARTY_HEADING = re.compile(r"^(.+?) \(Two-Party\)$")
PDF_TABLE_HEADER = re.compile(
    r"^Ball Don- Formal to ([A-Z-]+) \((\d+)\) "
    r"to ([A-Z-]+) \((\d+)\)$"
)
PDF_FLOW_ROW = re.compile(
    r"^(\d+)\s+(.+?) \(([^)]+)\)\s+"
    r"(?:(ALP|LIB|LNP|NAT|CLP|GRN|IND)\s+)?"
    r"([\d,]+)\s+([\d.]+)\s+"
    r"([\d,]+)\s+([\d.]+)\s+"
    r"([\d,]+)\s+([\d.]+)$"
)

USER_EDITABLE_COLUMNS = [
    "ModelCategory",
    "CandidateSubtype",
    "IdeologyFamily",
    "ClassificationRationale",
    "ReviewStatus",
    "AnalystNotes",
]


def _read_aec_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, skiprows=1)


def _normalise_party_code(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().upper()


def suggested_classification(
    party_code: str,
    primary_share: float,
) -> tuple[str, str, str, str]:
    code = _normalise_party_code(party_code)
    if code in ALP_CODES:
        return "ALP", "ALP", "Official Labor affiliation.", "Auto-classified"
    if code in COALITION_CODES:
        subtype = {
            "LP": "LIB",
            "LIB": "LIB",
            "NP": "NAT",
            "NAT": "NAT",
            "LNP": "LNP",
            "CLP": "CLP",
        }[code]
        return "LNP", subtype, "Official Coalition affiliation.", "Auto-classified"
    if code in GRN_CODES:
        return "GRN", "GRN", "Official Greens affiliation.", "Auto-classified"
    if code == "ON":
        return "ON", "ON", "Official One Nation affiliation.", "Auto-classified"
    if code == "IND":
        if float(primary_share or 0.0) >= 0.05:
            return (
                "IND",
                "IND_PROMINENT",
                "Official independent with at least 5% of formal first preferences.",
                "Needs subjective review",
            )
        return (
            "OTH",
            "IND_MINOR",
            "Official independent below 5% of formal first preferences.",
            "Needs subjective review",
        )

    subtype = f"OTH_{code}" if code else "OTH_UNAFFILIATED"
    return (
        "OTH",
        subtype,
        "Minor-party or unaffiliated candidate; ideology requires review.",
        "Needs subjective review",
    )


def parse_preference_flow_report(path: Path) -> pd.DataFrame:
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError(
            "pdfplumber is required to parse FED2025_PreferenceFlowReport.pdf"
        ) from exc

    rows = []
    current: dict = {}
    state_by_division: dict[str, str] = {}

    with pdfplumber.open(path) as document:
        for page_number, page in enumerate(document.pages[1:], start=2):
            for raw_line in (page.extract_text() or "").splitlines():
                line = " ".join(raw_line.split())
                division_match = PDF_DIVISION_HEADING.match(line)
                if division_match:
                    division = division_match.group(1)
                    state = division_match.group(2)
                    state_by_division[division] = state
                    current = {
                        "Electorate": division,
                        "State": state,
                        "IsTwoPartyTable": False,
                        "SourceFlowPage": page_number,
                    }
                    continue

                two_party_match = PDF_TWO_PARTY_HEADING.match(line)
                if two_party_match:
                    division = two_party_match.group(1)
                    current = {
                        "Electorate": division,
                        "State": state_by_division.get(division, ""),
                        "IsTwoPartyTable": True,
                        "SourceFlowPage": page_number,
                    }
                    continue

                header_match = PDF_TABLE_HEADER.match(line)
                if header_match and current:
                    current.update(
                        {
                            "FinalA": header_match.group(1),
                            "FinalAPosition": int(header_match.group(2)),
                            "FinalB": header_match.group(3),
                            "FinalBPosition": int(header_match.group(4)),
                        }
                    )
                    continue

                row_match = PDF_FLOW_ROW.match(line)
                if not row_match or "FinalA" not in current:
                    continue
                rows.append(
                    {
                        **current,
                        "BallotPosition": int(row_match.group(1)),
                        "PdfSurname": row_match.group(2),
                        "PdfPartyCode": row_match.group(3),
                        "DonkeyFavouredParty": row_match.group(4) or "",
                        "FlowVotes": int(row_match.group(5).replace(",", "")),
                        "PrimaryPercentReported": float(row_match.group(6)),
                        "ToAVotes": int(row_match.group(7).replace(",", "")),
                        "ToAPercent": float(row_match.group(8)) / 100.0,
                        "ToBVotes": int(row_match.group(9).replace(",", "")),
                        "ToBPercent": float(row_match.group(10)) / 100.0,
                    }
                )

    flows = pd.DataFrame(rows)
    if flows.empty:
        raise ValueError("No candidate flow rows were parsed from the report")

    pair_is_tpp = flows.apply(
        lambda row: (
            row["IsTwoPartyTable"]
            or (
                bool({row["FinalA"], row["FinalB"]} & {"ALP"})
                and bool({row["FinalA"], row["FinalB"]} & {"LIB", "LNP", "NAT", "CLP"})
            )
        ),
        axis=1,
    )
    flows["FlowType"] = pair_is_tpp.map({True: "TPP", False: "TCP"})
    return flows


def _flow_columns(
    candidates: pd.DataFrame,
    flows: pd.DataFrame,
) -> pd.DataFrame:
    joined = flows.merge(
        candidates[
            [
                "DivisionNm",
                "BallotPosition",
                "CandidateID",
                "Surname",
                "TotalVotes",
            ]
        ],
        left_on=["Electorate", "BallotPosition"],
        right_on=["DivisionNm", "BallotPosition"],
        how="left",
        validate="many_to_one",
    )
    if joined["CandidateID"].isna().any():
        raise ValueError("Some PDF flow rows could not be matched to an AEC candidate")
    if not joined["FlowVotes"].eq(joined["TotalVotes"]).all():
        raise ValueError("PDF formal votes did not reconcile to AEC first preferences")
    if not joined["PdfSurname"].str.upper().eq(joined["Surname"].str.upper()).all():
        raise ValueError("PDF surnames did not reconcile to AEC candidate names")
    if joined.duplicated(["CandidateID", "FlowType"]).any():
        raise ValueError("A candidate has duplicate flow rows of the same type")

    records = []
    for _, row in joined.iterrows():
        record = {"CandidateID": int(row["CandidateID"])}
        if row["FlowType"] == "TPP":
            if row["FinalA"] == "ALP":
                alp_share = row["ToAPercent"]
                coalition_share = row["ToBPercent"]
            else:
                alp_share = row["ToBPercent"]
                coalition_share = row["ToAPercent"]
            record.update(
                {
                    "TPPToALP": alp_share,
                    "TPPToCoalition": coalition_share,
                    "TPPFlowVotes": int(row["FlowVotes"]),
                    "TPPDonkeyFavouredParty": row["DonkeyFavouredParty"],
                    "TPPFlowProfile": (
                        "Strong ALP flow"
                        if alp_share > 0.70
                        else "ALP-leaning"
                        if alp_share >= 0.55
                        else "Neutral"
                        if alp_share >= 0.45
                        else "Coalition-leaning"
                        if alp_share >= 0.30
                        else "Strong Coalition flow"
                    ),
                    "TPPSourcePage": int(row["SourceFlowPage"]),
                }
            )
        else:
            record.update(
                {
                    "TCPFinalA": row["FinalA"],
                    "TCPFinalB": row["FinalB"],
                    "TCPToA": row["ToAPercent"],
                    "TCPToB": row["ToBPercent"],
                    "TCPFlowVotes": int(row["FlowVotes"]),
                    "TCPDonkeyFavouredParty": row["DonkeyFavouredParty"],
                    "TCPSourcePage": int(row["SourceFlowPage"]),
                }
            )
        records.append(record)

    if not records:
        return pd.DataFrame(columns=["CandidateID"])
    wide = pd.DataFrame(records).groupby("CandidateID", as_index=False).first()
    return wide


def build_candidate_classification(source_dir: Path) -> pd.DataFrame:
    candidates = _read_aec_csv(source_dir / CANDIDATES_FILE)
    first_prefs = _read_aec_csv(source_dir / FIRST_PREFS_FILE)
    first_prefs = first_prefs[first_prefs["CandidateID"].ne(999)].copy()
    flows = parse_preference_flow_report(source_dir / FLOW_REPORT_FILE)

    candidate_fields = candidates.merge(
        first_prefs[
            ["CandidateID", "BallotPosition", "TotalVotes"]
        ],
        on="CandidateID",
        how="left",
        validate="one_to_one",
    )
    formal_by_division = candidate_fields.groupby("DivisionID")["TotalVotes"].transform("sum")
    candidate_fields["PrimaryShare"] = (
        candidate_fields["TotalVotes"] / formal_by_division.where(formal_by_division > 0)
    )
    candidate_fields = candidate_fields.merge(
        _flow_columns(candidate_fields, flows),
        on="CandidateID",
        how="left",
        validate="one_to_one",
    )

    suggestions = candidate_fields.apply(
        lambda row: suggested_classification(row["PartyAb"], row["PrimaryShare"]),
        axis=1,
    )
    candidate_fields["SuggestedModelCategory"] = [value[0] for value in suggestions]
    candidate_fields["SuggestedCandidateSubtype"] = [value[1] for value in suggestions]
    candidate_fields["SuggestedRationale"] = [value[2] for value in suggestions]
    candidate_fields["SuggestedReviewStatus"] = [value[3] for value in suggestions]

    candidate_fields["CandidateName"] = (
        candidate_fields["GivenNm"].astype(str).str.strip()
        + " "
        + candidate_fields["Surname"].astype(str).str.strip().str.title()
    )
    output = pd.DataFrame(
        {
            "Election": ELECTION_YEAR,
            "State": candidate_fields["StateAb"],
            "DivisionID": candidate_fields["DivisionID"],
            "Electorate": candidate_fields["DivisionNm"],
            "CandidateID": candidate_fields["CandidateID"],
            "BallotPosition": candidate_fields["BallotPosition"],
            "CandidateName": candidate_fields["CandidateName"],
            "OfficialPartyCode": candidate_fields["PartyAb"].fillna(""),
            "OfficialPartyName": candidate_fields["PartyNm"].fillna("Unaffiliated"),
            "PrimaryVotes": candidate_fields["TotalVotes"],
            "PrimaryShare": candidate_fields["PrimaryShare"],
            "Elected": candidate_fields["Elected"],
            "HistoricElected": candidate_fields["HistoricElected"],
            "SuggestedModelCategory": candidate_fields["SuggestedModelCategory"],
            "SuggestedCandidateSubtype": candidate_fields["SuggestedCandidateSubtype"],
            "ModelCategory": candidate_fields["SuggestedModelCategory"],
            "CandidateSubtype": candidate_fields["SuggestedCandidateSubtype"],
            "IdeologyFamily": "",
            "ClassificationRationale": candidate_fields["SuggestedRationale"],
            "ReviewStatus": candidate_fields["SuggestedReviewStatus"],
            "TPPToALP": candidate_fields.get("TPPToALP"),
            "TPPToCoalition": candidate_fields.get("TPPToCoalition"),
            "TPPFlowVotes": candidate_fields.get("TPPFlowVotes"),
            "TPPFlowProfile": candidate_fields.get("TPPFlowProfile"),
            "TPPDonkeyFavouredParty": candidate_fields.get("TPPDonkeyFavouredParty"),
            "TPPSourcePage": candidate_fields.get("TPPSourcePage"),
            "TCPFinalA": candidate_fields.get("TCPFinalA"),
            "TCPFinalB": candidate_fields.get("TCPFinalB"),
            "TCPToA": candidate_fields.get("TCPToA"),
            "TCPToB": candidate_fields.get("TCPToB"),
            "TCPFlowVotes": candidate_fields.get("TCPFlowVotes"),
            "TCPDonkeyFavouredParty": candidate_fields.get("TCPDonkeyFavouredParty"),
            "TCPSourcePage": candidate_fields.get("TCPSourcePage"),
            "AnalystNotes": "",
        }
    )

    if OUTPUT_FILE.exists():
        existing = pd.read_csv(OUTPUT_FILE)
        preserve = ["CandidateID", *USER_EDITABLE_COLUMNS]
        if set(preserve).issubset(existing.columns):
            existing = existing[preserve].copy()
            output = output.drop(columns=USER_EDITABLE_COLUMNS).merge(
                existing,
                on="CandidateID",
                how="left",
                validate="one_to_one",
            )
            defaults = {
                "ModelCategory": candidate_fields["SuggestedModelCategory"].values,
                "CandidateSubtype": candidate_fields["SuggestedCandidateSubtype"].values,
                "IdeologyFamily": "",
                "ClassificationRationale": candidate_fields["SuggestedRationale"].values,
                "ReviewStatus": candidate_fields["SuggestedReviewStatus"].values,
                "AnalystNotes": "",
            }
            for column, default in defaults.items():
                output[column] = output[column].fillna(
                    pd.Series(default, index=output.index)
                    if not isinstance(default, str)
                    else default
                )

    desired_order = [
        "Election", "State", "DivisionID", "Electorate", "CandidateID",
        "BallotPosition", "CandidateName", "OfficialPartyCode", "OfficialPartyName",
        "PrimaryVotes", "PrimaryShare", "Elected", "HistoricElected",
        "SuggestedModelCategory", "SuggestedCandidateSubtype", "ModelCategory",
        "CandidateSubtype", "IdeologyFamily", "ClassificationRationale", "ReviewStatus",
        "TPPToALP", "TPPToCoalition", "TPPFlowVotes", "TPPFlowProfile",
        "TPPDonkeyFavouredParty", "TPPSourcePage", "TCPFinalA", "TCPFinalB",
        "TCPToA", "TCPToB", "TCPFlowVotes", "TCPDonkeyFavouredParty",
        "TCPSourcePage", "AnalystNotes",
    ]
    return output[desired_order].sort_values(
        ["State", "Electorate", "BallotPosition"]
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the 2025 candidate classification and preference-flow input."
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help="Directory containing the three AEC files and preference-flow PDF.",
    )
    args = parser.parse_args()
    output = build_candidate_classification(args.source_dir)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    output.to_csv(OUTPUT_FILE, index=False)
    print(f"Wrote {len(output)} candidates to {OUTPUT_FILE}")
    print(output["ModelCategory"].value_counts().sort_index().to_string())
    print(output["ReviewStatus"].value_counts().to_string())


if __name__ == "__main__":
    main()
