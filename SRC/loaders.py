from __future__ import annotations

import re
import csv
from pathlib import Path

import pandas as pd

from .constants import PARTIES, STATE_ORDER


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"


def _read_csv(name: str, **kwargs) -> pd.DataFrame:
    return pd.read_csv(RAW_DIR / name, **kwargs)


def _to_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        if isinstance(value, str):
            text = value.strip().replace(",", "")
            if not text:
                return default
            if text.endswith("%"):
                return float(text[:-1].strip()) / 100.0
            return float(text)
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_percent_points(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        if isinstance(value, str):
            text = value.strip().replace(",", "")
            if not text:
                return default
            if text.endswith("%"):
                return float(text[:-1].strip())
            return float(text)
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalise_division(value: str) -> str:
    text = str(value or "").replace("\n", " ").strip()
    text = re.sub(r"\s*\([A-Z]{2,3}\)\s*$", "", text).strip()
    return text.rstrip("*").strip()


def division_key(value: str) -> str:
    return re.sub(r"\s+", " ", _normalise_division(value)).upper()


def load_seat_metadata() -> pd.DataFrame:
    df = _read_csv("SEAT_METADATA.csv")
    df = df.rename(
        columns={
            "Division": "division",
            "Classification": "classification",
            "ALP primary": "ALP",
            "LNP primary": "LNP",
            "GRN primary": "GRN",
            "ON primary": "ON",
            "IND primary": "IND",
            "OTH primary": "OTH",
        }
    )

    df = df[df["division"].notna()].copy()
    df["division"] = df["division"].map(_normalise_division)
    df["canonical_division"] = df["division"]
    df["division_key"] = df["division"].map(division_key)

    classification = load_seat_helper()
    df = df.merge(
        classification[
            [
                "division_key",
                "display_name",
                "state",
                "classification_helper",
                "status",
                "held_party",
                "held_by",
                "current_mp",
                "current_margin",
                "ind_candidate_status",
                "ind_swing_responsiveness",
                "notes",
            ]
        ],
        on="division_key",
        how="left",
    )
    df["display_name"] = df["display_name"].fillna(df["division"])
    df["status"] = df["status"].fillna("Active")
    df = df[df["status"].str.upper().ne("ABOLISHED")].copy()
    df["classification"] = df["classification_helper"].fillna(df["classification"])
    df = df.drop(columns=["classification_helper"])
    df["division"] = df["display_name"]

    for party in PARTIES:
        df[party] = df[party].map(_to_float)

    row_totals = df[PARTIES].sum(axis=1)
    for party in PARTIES:
        df[party] = df[party] / row_totals.where(row_totals > 0, 1)

    return df


def _normalise_held_party(value: str) -> str:
    text = str(value or "").strip().upper()
    mapping = {
        "LABOR": "ALP",
        "AUSTRALIAN LABOR PARTY": "ALP",
        "LIBERAL": "LNP",
        "NATIONAL": "LNP",
        "LIBERAL NATIONAL": "LNP",
        "LIBERAL-NATIONAL": "LNP",
        "COALITION": "LNP",
        "GREENS": "GRN",
        "GREEN": "GRN",
        "ONE NATION": "ON",
        "INDEPENDENT": "IND",
        "OTHER": "OTH",
    }
    return mapping.get(text, text if text in PARTIES else "")


def load_classification() -> pd.DataFrame:
    df = _read_csv("Classification.csv")
    df = df.rename(
        columns={
            "Division": "division",
            "State": "state",
            "Held party": "held_party",
        }
    )
    df = df[df["division"].notna()].copy()
    df["division"] = df["division"].map(_normalise_division)
    df["division_key"] = df["division"].map(division_key)
    df["state"] = df["state"].astype(str).str.strip().str.upper()
    df["held_by"] = df["held_party"].map(_normalise_held_party)
    return df


def load_seat_helper() -> pd.DataFrame:
    path = RAW_DIR / "SEAT_HELPER.csv"
    if not path.exists():
        fallback = load_classification()
        fallback["display_name"] = fallback["division"]
        fallback["classification_helper"] = fallback["classification"]
        fallback["status"] = "Active"
        fallback["current_mp"] = ""
        fallback["current_margin"] = ""
        fallback["ind_candidate_status"] = ""
        fallback["ind_swing_responsiveness"] = float("nan")
        fallback["notes"] = ""
        return fallback

    df = pd.read_csv(path)
    df = df.rename(
        columns={
            "Division": "division",
            "Display Name": "display_name",
            "State": "state",
            "Classification": "classification_helper",
            "Status": "status",
            "Held party": "held_party",
            "Current MP": "current_mp",
            "Current margin": "current_margin",
            "IND candidate status": "ind_candidate_status",
            "IND swing responsiveness": "ind_swing_responsiveness",
            "Notes": "notes",
        }
    )
    df = df[df["division"].notna()].copy()
    df["division"] = df["division"].map(_normalise_division)
    df["division_key"] = df["division"].map(division_key)

    def text_col(column: str, default: str = "") -> pd.Series:
        if column in df.columns:
            return df[column].fillna("").astype(str).str.strip()
        return pd.Series(default, index=df.index, dtype="object")

    df["display_name"] = text_col("display_name")
    df.loc[df["display_name"].eq(""), "display_name"] = df.loc[df["display_name"].eq(""), "division"]
    df["display_name"] = df["display_name"].map(_normalise_division)
    df["state"] = text_col("state").str.upper()
    df["classification_helper"] = text_col("classification_helper")
    df["status"] = text_col("status", "Active")
    df.loc[df["status"].eq(""), "status"] = "Active"
    df["status"] = df["status"].str.title()
    df["held_party"] = text_col("held_party")
    df["held_by"] = df["held_party"].map(_normalise_held_party)
    df["current_mp"] = text_col("current_mp")
    df["current_margin"] = text_col("current_margin")
    df["ind_candidate_status"] = text_col("ind_candidate_status")
    if "ind_swing_responsiveness" in df.columns:
        df["ind_swing_responsiveness"] = df["ind_swing_responsiveness"].map(
            lambda value: _to_float(value, default=float("nan"))
        )
    else:
        df["ind_swing_responsiveness"] = float("nan")
    df["notes"] = text_col("notes")

    return df[
        [
            "division",
            "division_key",
            "display_name",
            "state",
            "classification_helper",
            "status",
            "held_party",
            "held_by",
            "current_mp",
            "current_margin",
            "ind_candidate_status",
            "ind_swing_responsiveness",
            "notes",
        ]
    ]


def load_projected_2cp() -> pd.DataFrame:
    df = _read_csv("Proj_2CP.csv")
    first_col = df.columns[0]
    df = df.rename(columns={first_col: "division"})
    df = df[df["division"].notna()].copy()
    df["division"] = df["division"].map(_normalise_division)

    for party in PARTIES:
        if party in df.columns:
            df[party] = df[party].map(_to_float)

    return df[["division", *[p for p in PARTIES if p in df.columns]]]


def load_baseline_primary_by_state() -> dict[str, dict[str, float]]:
    path = RAW_DIR / "BASELINE_PRIMARY_BY_STATE.csv"
    if not path.exists():
        return {}

    df = pd.read_csv(path)
    if "State" not in df.columns:
        return {}

    out = {}
    for _, row in df.iterrows():
        state = str(row.get("State") or "").strip()
        if not state:
            continue
        key = "National" if state.upper() == "NATIONAL" else state.upper()
        values = {}
        for party in PARTIES:
            values[party] = _to_percent_points(row.get(f"{party}_primary", row.get(party)))
            for stage in ["3CP", "2CP", "2PP"]:
                col = f"{party}_{stage}"
                if col in df.columns:
                    values[col] = _to_percent_points(row.get(col))
        out[key] = values
    return out


def load_baseline_seats_by_state() -> dict[str, dict[str, int]]:
    path = RAW_DIR / "BASELINE_SEATS_BY_STATE.csv"
    if not path.exists():
        return {}

    df = pd.read_csv(path)
    if "State" not in df.columns:
        return {}

    out = {}
    for _, row in df.iterrows():
        state = str(row.get("State") or "").strip()
        if not state:
            continue
        key = "National" if state.upper() == "NATIONAL" else state.upper()
        out[key] = {
            party: int(round(_to_float(row.get(f"{party}_seats", row.get(party)), default=0.0)))
            for party in PARTIES
        }
    return out


def load_baseline_results_by_seat() -> pd.DataFrame:
    path = RAW_DIR / "BASELINE_RESULTS_BY_SEAT.csv"
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path)
    if "Division" not in df.columns:
        return pd.DataFrame()

    df = df.rename(columns={"Division": "division", "State": "state"})
    df["division"] = df["division"].map(_normalise_division)
    df["division_key"] = df["division"].map(division_key)

    for stage in ["primary", "3CP", "2CP", "2PP"]:
        for party in PARTIES:
            col = f"{party}_{stage}"
            if col in df.columns:
                df[col] = df[col].map(_to_percent_points)

    return df


def _load_keyed_primary_pvi(path: Path) -> pd.DataFrame:
    """Load party PVI columns from a wide calculation sheet by electorate name.

    The Google Sheet calculation tabs are not sorted in the same order as the
    presentation tabs, so these values must never be joined by row position.
    """
    if not path.exists():
        return pd.DataFrame()

    with path.open(newline="") as handle:
        rows = list(csv.reader(handle))

    header_idx = next(
        (
            idx
            for idx, row in enumerate(rows)
            if row
            and (
                str(row[0]).strip().upper() == "DIVISION"
                or sum(str(value).strip().upper() == "PRIMARY PVI" for value in row)
                >= len(PARTIES)
            )
        ),
        None,
    )
    if header_idx is None or header_idx == 0:
        return pd.DataFrame()

    party_row = rows[header_idx - 1]
    header_row = rows[header_idx]
    pvi_columns: dict[str, int] = {}
    active_party = ""
    for col_idx in range(max(len(party_row), len(header_row))):
        party_label = str(party_row[col_idx] if col_idx < len(party_row) else "").strip().upper()
        if party_label in PARTIES:
            active_party = party_label
        header_label = str(header_row[col_idx] if col_idx < len(header_row) else "").strip().upper()
        if active_party and header_label == "PRIMARY PVI":
            pvi_columns[active_party] = col_idx

    if set(pvi_columns) != set(PARTIES):
        return pd.DataFrame()

    records = []
    for row in rows[header_idx + 1 :]:
        division = _normalise_division(row[0] if row else "")
        if not division:
            continue
        record = {"division": division, "division_key": division_key(division)}
        for party, col_idx in pvi_columns.items():
            value = row[col_idx] if col_idx < len(row) else ""
            record[party] = _to_float(value, default=float("nan"))
        records.append(record)

    return pd.DataFrame(records).drop_duplicates("division_key", keep="first")


def load_partisan_vote_index(params: dict | None = None) -> pd.DataFrame:
    path = RAW_DIR / "PARTISAN_VOTE_INDEX.csv"
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path)
    if "Division" not in df.columns:
        return pd.DataFrame()

    df = df.rename(columns={"Division": "division", "State": "state"})
    df["division"] = df["division"].map(_normalise_division)
    df["division_key"] = df["division"].map(division_key)

    use_logit = ((params or {}).get("primary_model", {})).get("use_logit", {})

    records = []
    for _, row in df.iterrows():
        key = row["division_key"]
        record = {
            "division": row["division"],
            "division_key": key,
            "state": row["state"],
        }
        for party in PARTIES:
            # Every electorate-primary input lives in this one editable tab.
            # Logit-modelled parties use an explicitly labelled column; the
            # party-code fallback preserves frozen legacy snapshots.
            source_column = (
                f"{party}_LOGIT_PVI"
                if bool(use_logit.get(party, False))
                and f"{party}_LOGIT_PVI" in df.columns
                else party
            )
            value = _to_float(row.get(source_column, float("nan")), default=float("nan"))
            record[party] = 0.0 if pd.isna(value) else float(value)
        records.append(record)

    corrected = pd.DataFrame(records)
    if corrected.empty:
        return df[["division", "division_key", *[party for party in PARTIES if party in df.columns]]]
    return corrected[["division", "division_key", "state", *PARTIES]]


def load_district_2cp_swing() -> pd.DataFrame:
    path = RAW_DIR / "PRIMARY_ELECTION_MODEL.csv"
    if not path.exists():
        return pd.DataFrame()

    rows = {}
    with path.open(newline="") as handle:
        reader = csv.reader(handle)
        for row in reader:
            for idx, cell in enumerate(row):
                if idx + 16 >= len(row):
                    continue

                division = _normalise_division(cell)
                if not division or division.upper() == "DIVISION":
                    continue

                swing = _to_float(row[idx + 16], default=None)
                if swing is None:
                    continue

                try:
                    alp_2cp = float(row[idx + 14] or 0)
                    other_2cp = float(row[idx + 15] or 0)
                except (TypeError, ValueError):
                    continue

                if alp_2cp <= 0 and other_2cp <= 0:
                    continue

                key = division_key(division)
                rows.setdefault(
                    key,
                    {
                        "division_key": key,
                        "district_2cp_swing": swing * 100,
                    },
                )

    return pd.DataFrame(rows.values())


def load_params() -> dict:
    param_df = _read_csv("PARAMS.csv", header=None)
    scalars = {}

    for _, row in param_df.iterrows():
        key = str(row.iloc[0] or "").strip().upper()
        if not key:
            continue
        value = _to_float(row.iloc[1], default=None)
        if value is not None:
            scalars[key] = value

    return {
        "scalars": scalars,
        "primary_model": load_primary_model_params(param_df),
        "baselines": {
            "LNP_TO_ON": {
                "NSW": 0.743,
                "QLD": 0.733,
                "VIC": 0.699,
                "WA": 0.692,
                "SA": 0.685,
                "NT": 0.666,
                "TAS": 0.592,
                "NAT": 0.716,
            },
            "LNP_TO_ON_BY_SEAT": load_lnp_to_on_by_seat(),
        },
        "POSTERIOR_SCENARIOS": load_posterior_scenarios(),
        "POSTERIOR_SCENARIO_EVIDENCE": load_posterior_scenario_evidence(),
        "POSTERIOR_SCENARIO_EVIDENCE_BY_CLASS": load_posterior_scenario_evidence_by_class(),
        "SEAT_SHRINKAGE_K_BY_DIVISION": load_seat_shrinkage_overrides(),
        "CATEGORY_FLOW_OVERRIDES": load_category_flow_overrides(),
        "siphon": load_siphon(),
        "ideology": load_ideology(),
    }


def load_candidate_classification() -> pd.DataFrame:
    path = RAW_DIR / "CANDIDATE_CLASSIFICATION.csv"
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path)
    required = {
        "CandidateID",
        "Electorate",
        "ModelCategory",
        "CandidateSubtype",
    }
    if not required.issubset(df.columns):
        return pd.DataFrame()

    df = df.copy()
    for column in [
        "PrimaryShare",
        "TPPToALP",
        "TPPToCoalition",
        "TCPToA",
        "TCPToB",
    ]:
        if column in df.columns:
            df[column] = df[column].map(lambda value: _to_float(value, default=None))
    for column in ["ModelCategory", "CandidateSubtype", "IdeologyFamily", "ReviewStatus"]:
        if column in df.columns:
            df[column] = df[column].fillna("").astype(str).str.strip().str.upper()
    return df


def load_seat_shrinkage_overrides() -> dict[str, float]:
    path = RAW_DIR / "SEAT_SHRINKAGE_OVERRIDES.csv"
    if not path.exists():
        return {}

    df = pd.read_csv(path)
    required = {"Division", "UseOverride", "SeatShrinkageK"}
    if not required.issubset(df.columns):
        return {}

    out = {}
    for _, row in df.iterrows():
        enabled = str(row.get("UseOverride") or "").strip().upper()
        if enabled not in {"TRUE", "YES", "Y", "1"}:
            continue
        value = _to_float(row.get("SeatShrinkageK"), default=None)
        if value is None or value < 0:
            continue
        key = division_key(row.get("Division"))
        if key:
            out[key] = float(value)
    return out


def load_category_flow_overrides() -> dict[tuple[str, str, str], dict]:
    path = RAW_DIR / "CATEGORY_FLOW_OVERRIDES.csv"
    if not path.exists():
        return {}

    df = pd.read_csv(path)
    required = {
        "Electorate",
        "EliminatedModelCategory",
        "AliveModelCategoriesAfter",
        "UseOverride",
        "EvidenceMultiplierOverride",
        "MethodOverride",
    }
    if not required.issubset(df.columns):
        return {}

    allowed_methods = {
        "",
        "OBSERVED_LAST_SURVIVOR_EXIT",
        "PROPORTIONAL_PRIMARY_ORIGIN_PASS_THROUGH",
    }
    out = {}
    for _, row in df.iterrows():
        enabled = str(row.get("UseOverride") or "").strip().upper()
        if enabled not in {"TRUE", "YES", "Y", "1"}:
            continue
        multiplier = _to_float(row.get("EvidenceMultiplierOverride"), default=None)
        method = str(row.get("MethodOverride") or "").strip().upper()
        if multiplier is not None and not 0 <= multiplier <= 1:
            continue
        if method not in allowed_methods:
            continue
        key = (
            division_key(row.get("Electorate")),
            str(row.get("EliminatedModelCategory") or "").strip().upper(),
            str(row.get("AliveModelCategoriesAfter") or "").strip().upper(),
        )
        if not all(key) or (multiplier is None and not method):
            continue
        out[key] = {
            "evidence_multiplier": multiplier,
            "method": method or None,
        }
    return out


def load_primary_model_params(param_df: pd.DataFrame) -> dict:
    out = {
        "a": {party: 1.0 for party in PARTIES},
        "use_logit": {party: False for party in PARTIES},
    }

    for row_idx in range(param_df.shape[0]):
        for col_idx in range(max(param_df.shape[1] - 1, 0)):
            left = str(param_df.iat[row_idx, col_idx] or "").strip().upper()
            right = str(param_df.iat[row_idx, col_idx + 1] or "").strip().upper()
            if left != "PARTY":
                continue

            if right == "A":
                for value_idx in range(row_idx + 1, param_df.shape[0]):
                    party = str(param_df.iat[value_idx, col_idx] or "").strip().upper()
                    if party not in PARTIES:
                        break
                    out["a"][party] = _to_float(param_df.iat[value_idx, col_idx + 1], default=out["a"][party])

            if right == "USELOGIT":
                for value_idx in range(row_idx + 1, param_df.shape[0]):
                    party = str(param_df.iat[value_idx, col_idx] or "").strip().upper()
                    if party not in PARTIES:
                        break
                    raw = str(param_df.iat[value_idx, col_idx + 1] or "").strip().upper()
                    out["use_logit"][party] = raw in {"TRUE", "YES", "1", "Y"}

    return out


def load_lnp_to_on_by_seat() -> dict[str, float]:
    return load_primary_2cp_lnp_to_on()


def load_primary_2cp_lnp_to_on() -> dict[str, float]:
    path = RAW_DIR / "PRIMARY_2CP.csv"
    if not path.exists():
        return {}

    header_row = 0
    with path.open(newline="") as handle:
        for i, line in enumerate(handle):
            if line.upper().startswith("SEAT,FINALA,FINALB,PARTY,"):
                header_row = i
                break

    df = pd.read_csv(path, header=header_row)
    required = {"Seat", "FinalA", "FinalB", "Party", "ShareToA", "ShareToB"}
    if not required.issubset(df.columns):
        return {}

    out = {}
    for _, row in df.iterrows():
        seat = str(row.get("Seat") or "").strip()
        if not seat:
            continue

        final_a = str(row.get("FinalA") or "").strip().upper()
        final_b = str(row.get("FinalB") or "").strip().upper()
        party = str(row.get("Party") or "").strip().upper()
        if party != "ON" or {final_a, final_b} != {"ALP", "LNP"}:
            continue

        share_a = _to_float(row.get("ShareToA"), default=None)
        share_b = _to_float(row.get("ShareToB"), default=None)
        if share_a is None or share_b is None:
            continue

        if final_a == "LNP":
            lnp_to_on = share_a
        else:
            lnp_to_on = share_b

        if 0 <= lnp_to_on <= 1:
            out[division_key(seat)] = lnp_to_on

    return out


def load_ideology() -> dict[str, dict[str, float]]:
    df = _read_csv("IDEOLOGY.csv")
    out = {}

    for _, row in df.iterrows():
        elim = str(row.iloc[0] or "").strip().upper()
        if elim not in PARTIES:
            continue
        out[elim] = {
            party: _to_float(row.get(party))
            for party in PARTIES
            if _to_float(row.get(party)) > 0
        }

    return out


def load_siphon() -> dict[str, dict[str, float]]:
    df = _read_csv("SIPHON.csv")
    out = {}

    for _, row in df.iterrows():
        entrant = str(row.get("ENTRANT") or "").strip().upper()
        if not entrant:
            continue
        out[entrant] = {party: _to_float(row.get(party)) for party in PARTIES}

    return out


def _normalise_alive_set(value: str) -> str:
    parts = [
        p.strip().upper()
        for p in re.split(r"[+,|/]", str(value or ""))
        if p.strip()
    ]
    return "+".join(sorted(parts))


def load_posterior_scenarios() -> dict[str, dict[str, float]]:
    evidence = load_posterior_scenario_evidence()
    return {
        key: value["shares"]
        for key, value in evidence.items()
        if value.get("shares")
    }


def load_posterior_scenario_evidence() -> dict[str, dict]:
    source_file = (
        "CATEGORY_SCENARIO_STATS.csv"
        if (RAW_DIR / "CATEGORY_SCENARIO_STATS.csv").exists()
        else "SCENARIO_STATS.csv"
    )
    df = _read_csv(source_file)
    out: dict[str, dict] = {}

    for _, row in df.iterrows():
        elim = str(row.get("Eliminated") or "").strip().upper()
        recipient = str(row.get("Recipient") or "").strip().upper()
        alive = _normalise_alive_set(row.get("AliveSet"))
        share = _to_float(row.get("Share"))
        votes = _to_float(row.get("Votes"))
        scenario_total = _to_float(row.get("ScenarioTotal"))
        seats = _to_float(row.get("Seats"))

        if elim not in PARTIES or recipient not in PARTIES or not alive or share <= 0:
            continue

        key = f"{elim}|{alive}"
        scenario = out.setdefault(
            key,
            {
                "eliminated": elim,
                "alive_set": alive,
                "shares": {},
                "recipient_votes": {},
                "scenario_total": 0.0,
                "seats": 0,
                "source": source_file.removesuffix(".csv"),
            },
        )
        scenario["shares"][recipient] = share
        scenario["recipient_votes"][recipient] = votes
        scenario["scenario_total"] = max(scenario["scenario_total"], scenario_total)
        scenario["seats"] = max(scenario["seats"], int(round(seats)))

    seat_evidence = load_seat_preference_evidence()
    if seat_evidence.empty:
        return out

    seat_scenario_recipient_votes: dict[tuple[str, str, str], dict[str, float]] = {}
    for _, row in seat_evidence.iterrows():
        seat = str(row.get("Seat") or "").strip()
        elim = _normalise_party(row.get("Eliminated"))
        alive = _normalise_alive_set(row.get("AliveSet"))
        recipient = _normalise_party(row.get("Recipient"))
        votes = _to_float(row.get("Votes"))
        if not seat or not alive or votes <= 0:
            continue
        key = (seat, elim, alive)
        seat_scenario_recipient_votes.setdefault(key, {})[recipient] = votes

    observations: dict[str, list[dict[str, float]]] = {}
    for (_, elim, alive), recipient_votes in seat_scenario_recipient_votes.items():
        total = sum(recipient_votes.values())
        if total <= 0:
            continue
        observations.setdefault(f"{elim}|{alive}", []).append(
            {
                party: recipient_votes.get(party, 0.0) / total
                for party in alive.split("+")
            }
        )

    for key, seat_rows in observations.items():
        if key not in out or not seat_rows:
            continue
        parties = out[key]["alive_set"].split("+")
        means = {
            party: sum(row.get(party, 0.0) for row in seat_rows) / len(seat_rows)
            for party in parties
        }
        variances = {}
        for party in parties:
            if len(seat_rows) <= 1:
                variances[party] = 0.0
                continue
            mean = means[party]
            variances[party] = sum(
                (row.get(party, 0.0) - mean) ** 2 for row in seat_rows
            ) / (len(seat_rows) - 1)

        out[key]["equal_seat_mean_shares"] = means
        out[key]["between_seat_variance"] = variances
        out[key]["seat_observations"] = len(seat_rows)

    return out


def load_posterior_scenario_evidence_by_class() -> dict[str, dict[str, dict]]:
    evidence = load_seat_preference_evidence()
    seats = load_seat_metadata()
    if evidence.empty or seats.empty:
        return {}

    class_by_key = seats.set_index("division_key")["classification"].to_dict()
    grouped_votes: dict[
        tuple[str, str, str, str], dict[str, float]
    ] = {}

    for _, row in evidence.iterrows():
        seat = str(row.get("Seat") or "").strip()
        seat_key = division_key(seat)
        seat_class = str(class_by_key.get(seat_key) or "").strip()
        eliminated = _normalise_party(row.get("Eliminated"))
        alive = _normalise_alive_set(row.get("AliveSet"))
        recipient = _normalise_party(row.get("Recipient"))
        votes = _to_float(row.get("Votes"))
        if not seat_class or not alive or votes <= 0:
            continue
        key = (seat_class, seat_key, eliminated, alive)
        grouped_votes.setdefault(key, {})[recipient] = votes

    observations: dict[tuple[str, str], list[dict[str, float]]] = {}
    for (seat_class, _, eliminated, alive), recipient_votes in grouped_votes.items():
        total = sum(recipient_votes.values())
        if total <= 0:
            continue
        observations.setdefault((seat_class, f"{eliminated}|{alive}"), []).append(
            {
                party: recipient_votes.get(party, 0.0) / total
                for party in alive.split("+")
            }
        )

    out: dict[str, dict[str, dict]] = {}
    for (seat_class, scenario_key), rows in observations.items():
        alive = scenario_key.split("|", 1)[1].split("+")
        means = {
            party: sum(row.get(party, 0.0) for row in rows) / len(rows)
            for party in alive
        }
        variance = {}
        for party in alive:
            if len(rows) <= 1:
                variance[party] = 0.0
            else:
                mean = means[party]
                variance[party] = sum(
                    (row.get(party, 0.0) - mean) ** 2 for row in rows
                ) / (len(rows) - 1)
        out.setdefault(seat_class, {})[scenario_key] = {
            "equal_seat_mean_shares": means,
            "between_seat_variance": variance,
            "seat_observations": len(rows),
            "seats": len(rows),
            "source": "seat_class",
        }
    return out


def load_preference_matrices() -> dict[str, dict]:
    matrices = {}

    for state in STATE_ORDER:
        path = RAW_DIR / f"PREF_MATRIX_{state}.csv"
        if not path.exists():
            continue

        df = pd.read_csv(path, header=None, keep_default_na=False)
        rows = df.values.tolist()
        r = 0

        while r < len(rows):
            seat_cell = str(rows[r][0] if len(rows[r]) else "").strip()
            marker = str(rows[r][1] if len(rows[r]) > 1 else "").strip().upper()

            if seat_cell and marker == "RAW" and r + 8 < len(rows):
                division = _normalise_division(seat_cell)
                matrix = {}

                for offset, party in enumerate(PARTIES, start=3):
                    row = rows[r + offset]
                    row_party = str(row[0]).strip().upper()
                    if row_party not in PARTIES:
                        continue
                    matrix[row_party] = {
                        target: _to_float(row[i])
                        for i, target in enumerate(PARTIES, start=1)
                    }

                matrices[division_key(division)] = {
                    "division": division,
                    "state": state,
                    "matrix": matrix,
                    "seat_flows": {},
                    "seat_flow_evidence": {},
                }
                r += 8
            else:
                r += 1

    seat_flows = load_seat_preference_flows()
    seat_flow_evidence = load_seat_preference_flow_evidence()
    for div_key, flows in seat_flows.items():
        if div_key in matrices:
            matrices[div_key]["seat_flows"] = flows
            matrices[div_key]["seat_flow_evidence"] = seat_flow_evidence.get(div_key, {})

    return matrices


def load_seat_preference_evidence() -> pd.DataFrame:
    category_path = RAW_DIR / "CATEGORY_PREF_FLOWS_LONG.csv"
    if category_path.exists():
        df = pd.read_csv(category_path)
        required = {"Seat", "Eliminated", "AliveSet", "Recipient", "Share"}
        if not required.issubset(df.columns):
            return pd.DataFrame()
        df = df.copy()
        df["Seat"] = df["Seat"].fillna("").astype(str).str.strip()
        df["division_key"] = df["Seat"].map(division_key)
        df["Eliminated"] = df["Eliminated"].map(_normalise_party)
        df["Recipient"] = df["Recipient"].map(_normalise_party)
        df["AliveSet"] = df["AliveSet"].map(_normalise_alive_set)
        df["ReportedAliveSet"] = df["AliveSet"]
        df["AliveSetSource"] = "aec_candidate_round_category_exit"
        df["AliveSetPositionConflict"] = False
        return df

    path = RAW_DIR / "SEAT_PREF_FLOWS_LONG.csv"
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path)
    required = {"Seat", "Eliminated", "AliveSet", "Recipient", "Share"}
    if not required.issubset(df.columns):
        return pd.DataFrame()

    round_metadata, approved_seats = _load_wide_flow_round_metadata()
    records = []

    for _, row in df.iterrows():
        seat = str(row.get("Seat") or "").strip()
        if approved_seats and seat not in approved_seats:
            continue
        eliminated = _normalise_party(row.get("Eliminated"))
        recipient = _normalise_party(row.get("Recipient"))
        reported_alive = _normalise_alive_set(row.get("AliveSet"))
        alive = set(reported_alive.split("+")) if reported_alive else set()
        metadata = round_metadata.get((seat, eliminated), {})
        top_three = metadata.get("top_three", [])
        position = metadata.get("position")

        expected_alive = set(alive)
        if eliminated in top_three:
            expected_alive.update(top_three[: top_three.index(eliminated)])
        else:
            expected_alive.update(top_three)
            if position:
                expected_alive.update(
                    party
                    for party, party_position in metadata.get("positions", {}).items()
                    if party_position and party_position < position
                )

        # A positive recipient must have been alive in the manually compiled
        # scenario. Positional labels are validation evidence, not authority.
        expected_alive.add(recipient)
        canonical_alive = "+".join(sorted(p for p in expected_alive if p in PARTIES))
        position_conflict = bool(
            position and position <= 3 and eliminated not in top_three
        )

        record = row.to_dict()
        record.update(
            {
                "Seat": seat,
                "division_key": division_key(seat),
                "Eliminated": eliminated,
                "Recipient": recipient,
                "ReportedAliveSet": reported_alive,
                "AliveSet": canonical_alive,
                "AliveSetSource": "positive_recipients_validated_against_3cp",
                "AliveSetPositionConflict": position_conflict,
                "RecordedPosition": position,
                "TopThree": "+".join(top_three),
            }
        )
        records.append(record)

    return pd.DataFrame(records)


def _load_wide_flow_round_metadata() -> tuple[dict[tuple[str, str], dict], set[str]]:
    path = RAW_DIR / "SEAT_PREF_FLOWS.csv"
    if not path.exists():
        return {}, set()

    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 4:
        return {}, set()

    owners = []
    current_owner = ""
    for value in rows[0]:
        party = _normalise_party(value)
        if party in PARTIES:
            current_owner = party
        owners.append(current_owner)

    position_columns = {
        owners[index]: index
        for index, value in enumerate(rows[2])
        if str(value).strip().upper() == "POSITION" and owners[index] in PARTIES
    }
    rank = {
        "FIRST": 1,
        "SECOND": 2,
        "THIRD": 3,
        "FOURTH": 4,
        "FIFTH": 5,
        "SIXTH": 6,
        "SIXITH": 6,
    }
    metadata = {}
    approved_seats = set()

    for row in rows[3:]:
        if len(row) < 5:
            continue
        seat = str(row[1] or "").strip()
        if not seat:
            continue
        status = str(row[-1] or "").strip().upper()
        if status != "Y":
            continue
        approved_seats.add(seat)

        top_three = [
            party
            for party in (_normalise_party(value) for value in row[2:5])
            if party in PARTIES
        ]
        positions = {
            party: rank.get(str(row[column] or "").strip().upper())
            for party, column in position_columns.items()
            if column < len(row)
        }

        for eliminated, position in positions.items():
            if position is None:
                continue
            metadata[(seat, eliminated)] = {
                "top_three": top_three,
                "positions": positions,
                "position": position,
            }

    return metadata, approved_seats


def load_seat_preference_flows() -> dict[str, dict[str, dict[str, float]]]:
    df = load_seat_preference_evidence()
    if df.empty:
        return {}

    out: dict[str, dict[str, dict[str, float]]] = {}
    for _, row in df.iterrows():
        division = str(row.get("Seat") or "").strip()
        elim = _normalise_party(row.get("Eliminated"))
        recipient = _normalise_party(row.get("Recipient"))
        alive = _normalise_alive_set(row.get("AliveSet"))
        share = _to_float(row.get("Share"))

        if not division or elim not in PARTIES or recipient not in PARTIES:
            continue
        if not alive or share <= 0:
            continue

        key = f"{elim}|{alive}"
        out.setdefault(division_key(division), {}).setdefault(key, {})[recipient] = share

    return out


def load_seat_preference_flow_evidence() -> dict[str, dict[str, dict]]:
    df = load_seat_preference_evidence()
    if df.empty:
        return {}

    out: dict[str, dict[str, dict]] = {}
    for _, row in df.iterrows():
        division = str(row.get("Seat") or "").strip()
        eliminated = _normalise_party(row.get("Eliminated"))
        recipient = _normalise_party(row.get("Recipient"))
        alive = _normalise_alive_set(row.get("AliveSet"))
        votes = _to_float(row.get("Votes"))
        share = _to_float(row.get("Share"))

        if not division or eliminated not in PARTIES or recipient not in PARTIES:
            continue
        if not alive or share <= 0:
            continue

        key = f"{eliminated}|{alive}"
        scenario = (
            out.setdefault(division_key(division), {})
            .setdefault(
                key,
                {
                    "eliminated": eliminated,
                    "alive_set": alive,
                    "shares": {},
                    "recipient_votes": {},
                    "scenario_total": 0.0,
                    "seats": 1,
                    "source": "SEAT_PREF_FLOWS_LONG",
                    "alive_set_source": row.get("AliveSetSource", ""),
                    "position_conflict": bool(row.get("AliveSetPositionConflict", False)),
                    "evidence_multiplier": max(
                        0.0,
                        min(
                            1.0,
                            _to_float(
                                row.get("EffectiveEvidenceMultiplier"),
                                default=1.0,
                            ),
                        ),
                    ),
                    "method": str(row.get("Method") or "").strip().upper(),
                },
            )
        )
        scenario["shares"][recipient] = share
        scenario["recipient_votes"][recipient] = votes
        scenario["scenario_total"] += votes

    return out


def _normalise_party(value: str) -> str:
    text = str(value or "").strip().upper()
    mapping = {
        "LIB": "LNP",
        "LIBERAL": "LNP",
        "NAT": "LNP",
        "NATIONAL": "LNP",
        "ONP": "ON",
        "ONE NATION": "ON",
        "GREENS": "GRN",
        "GREEN": "GRN",
        "INDEPENDENT": "IND",
        "OTHER": "OTH",
    }
    return mapping.get(text, text)
