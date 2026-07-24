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


def load_sheet_baseline_results() -> pd.DataFrame:
    path = RAW_DIR / "SEAT_PROBS_3CP.csv"
    if not path.exists():
        return pd.DataFrame()

    rows = []
    with path.open(newline="") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if len(row) < 13:
                continue

            division = _normalise_division(row[0])
            if not division or division.upper() == "DIVISION":
                continue

            values = [_to_float(value, default=0.0) for value in row[7:13]]
            if sum(values) <= 0:
                continue

            final_values = dict(zip(PARTIES, values))
            final_parties = [party for party, value in final_values.items() if value > 1e-12]
            if len(final_parties) < 2:
                continue

            ordered = sorted(final_parties, key=lambda party: final_values[party], reverse=True)
            rows.append(
                {
                    "division": division,
                    "division_key": division_key(division),
                    "sheet_winner": ordered[0],
                    "sheet_runner_up": ordered[1],
                    "sheet_winner_pct": final_values[ordered[0]],
                    "sheet_runner_up_pct": final_values[ordered[1]],
                    "sheet_final_two": "+".join(sorted(final_parties)),
                    **{f"sheet_{party}_final": final_values[party] for party in PARTIES},
                }
            )

    return pd.DataFrame(rows)


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
            values[party] = _to_float(row.get(f"{party}_primary", row.get(party)))
            for stage in ["3CP", "2CP", "2PP"]:
                col = f"{party}_{stage}"
                if col in df.columns:
                    values[col] = _to_float(row.get(col))
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
                df[col] = df[col].map(_to_float)

    return df


def load_partisan_vote_index() -> pd.DataFrame:
    path = RAW_DIR / "PARTISAN_VOTE_INDEX.csv"
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path)
    if "Division" not in df.columns:
        return pd.DataFrame()

    df = df.rename(columns={"Division": "division", "State": "state"})
    df["division"] = df["division"].map(_normalise_division)
    df["division_key"] = df["division"].map(division_key)

    for party in PARTIES:
        if party in df.columns:
            df[party] = df[party].map(_to_float)

    return df[["division", "division_key", *[party for party in PARTIES if party in df.columns]]]


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
        "siphon": load_siphon(),
        "ideology": load_ideology(),
    }


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
    out = load_primary_2cp_lnp_to_on()
    out.update(load_inferred_lnp_to_on_from_3cp())
    return out


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


def load_inferred_lnp_to_on_from_3cp() -> dict[str, float]:
    path = RAW_DIR / "SEAT_PROBS_3CP.csv"
    if not path.exists():
        return {}

    out = {}
    with path.open(newline="") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if len(row) < 13:
                continue

            division = str(row[0] or "").strip()
            if not division or division.upper() == "DIVISION":
                continue

            values = [_to_float(value, default=0.0) for value in row[1:13]]
            alp_3cp, lnp_3cp, _, on_3cp, _, _ = values[:6]
            alp_2cp, lnp_2cp, _, on_2cp, _, _ = values[6:12]

            if not (alp_3cp > 0 and lnp_3cp > 0 and on_3cp > 0):
                continue
            if not (alp_2cp > 0 and on_2cp > 0 and lnp_2cp <= 0):
                continue

            lnp_to_on = (on_2cp - on_3cp) / lnp_3cp
            if 0 <= lnp_to_on <= 1:
                out[division_key(division)] = lnp_to_on

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
    df = _read_csv("SCENARIO_STATS.csv")
    out = {}

    for _, row in df.iterrows():
        elim = str(row.get("Eliminated") or "").strip().upper()
        recipient = str(row.get("Recipient") or "").strip().upper()
        alive = _normalise_alive_set(row.get("AliveSet"))
        share = _to_float(row.get("Share"))

        if elim not in PARTIES or recipient not in PARTIES or not alive or share <= 0:
            continue

        out.setdefault(f"{elim}|{alive}", {})[recipient] = share

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
                }
                r += 8
            else:
                r += 1

    seat_flows = load_seat_preference_flows()
    for div_key, flows in seat_flows.items():
        if div_key in matrices:
            matrices[div_key]["seat_flows"] = flows

    return matrices


def load_seat_preference_flows() -> dict[str, dict[str, dict[str, float]]]:
    path = RAW_DIR / "SEAT_PREF_FLOWS_LONG.csv"
    if not path.exists():
        return {}

    df = pd.read_csv(path)
    required = {"Seat", "Eliminated", "AliveSet", "Recipient", "Share"}
    if not required.issubset(df.columns):
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
