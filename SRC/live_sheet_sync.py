from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "raw"
MANIFEST_FILE = DATA_DIR / "_manifest.csv"
CREDENTIALS_FILE = ROOT / "credentials.json"
SHEET_ID_FILE = ROOT / "sheet_id.txt"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Only files read by the production Streamlit runtime belong in the live-sync
# path.  The workbook also contains dozens of diagnostics, archived model
# sheets, and validation outputs; downloading all of them on every app restart
# can exhaust the Google Sheets per-minute request quota.
PRODUCTION_SYNC_CSV_FILES = frozenset(
    {
        "Classification.csv",
        "SEAT_HELPER.csv",
        "SEAT_METADATA.csv",
        "PARAMS.csv",
        "SEAT_SHRINKAGE_OVERRIDES.csv",
        "CATEGORY_FLOW_OVERRIDES.csv",
        "CATEGORY_PREF_FLOWS_LONG.csv",
        "CATEGORY_SCENARIO_STATS.csv",
        "BASELINE_PRIMARY_BY_STATE.csv",
        "BASELINE_RESULTS_BY_SEAT.csv",
        "BASELINE_SEATS_BY_STATE.csv",
        "PARTISAN_VOTE_INDEX.csv",
        "LOGIT_PVI.csv",
        "IDEOLOGY.csv",
        "SIPHON.csv",
        "Proj_2CP.csv",
        "PRIMARY_2CP.csv",
        *{
            f"PREF_MATRIX_{state}.csv"
            for state in ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"]
        },
    }
)
SYNC_BATCH_SIZE = 10


def _secret_get(secrets: Mapping[str, Any] | None, key: str, default: Any = None) -> Any:
    if secrets is None:
        return default
    try:
        return secrets.get(key, default)
    except Exception:
        try:
            return secrets[key]
        except Exception:
            return default


def _as_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return dict(value)
    try:
        return dict(value)
    except Exception:
        return None


def resolve_sheet_id(secrets: Mapping[str, Any] | None = None) -> str | None:
    for key in ["FEDERAL_IRV_SHEET_ID", "federal_irv_sheet_id", "google_sheet_id", "sheet_id"]:
        value = os.environ.get(key) or _secret_get(secrets, key)
        if value:
            return str(value).strip()

    if SHEET_ID_FILE.exists():
        value = SHEET_ID_FILE.read_text().strip()
        if value:
            return value

    return None


def resolve_credentials(secrets: Mapping[str, Any] | None = None) -> Credentials | None:
    raw_json = os.environ.get("FEDERAL_IRV_GOOGLE_CREDENTIALS_JSON")
    if raw_json:
        info = json.loads(raw_json)
        return Credentials.from_service_account_info(info, scopes=SCOPES)

    for key in ["gcp_service_account", "google_service_account", "service_account"]:
        info = _as_dict(_secret_get(secrets, key))
        if info:
            return Credentials.from_service_account_info(info, scopes=SCOPES)

    # Also support putting service-account fields at the top level of st.secrets.
    top_level = _as_dict(secrets)
    if top_level and {"client_email", "private_key"}.issubset(top_level):
        return Credentials.from_service_account_info(top_level, scopes=SCOPES)

    if CREDENTIALS_FILE.exists():
        return Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)

    return None


def load_manifest() -> list[tuple[str, str]]:
    manifest = pd.read_csv(MANIFEST_FILE)
    required = {"sheet_name", "csv_file"}
    if not required.issubset(manifest.columns):
        raise ValueError(f"{MANIFEST_FILE} must contain columns: {', '.join(sorted(required))}")

    rows = []
    for _, row in manifest.iterrows():
        sheet_name = str(row["sheet_name"] or "").strip()
        csv_file = str(row["csv_file"] or "").strip()
        if sheet_name and csv_file:
            rows.append((sheet_name, csv_file))
    return rows


def sync_inputs_from_google_sheet(
    secrets: Mapping[str, Any] | None = None,
    only_tabs: set[str] | None = None,
) -> dict[str, Any]:
    try:
        sheet_id = resolve_sheet_id(secrets)
        creds = resolve_credentials(secrets)
    except Exception as exc:
        return {
            "ok": False,
            "synced": 0,
            "skipped": [],
            "errors": [f"Google Sheet configuration: {exc}"],
            "message": "Google Sheet sync unavailable; using committed CSV inputs",
        }

    if not sheet_id or creds is None:
        missing = []
        if not sheet_id:
            missing.append("sheet id")
        if creds is None:
            missing.append("Google service-account credentials")
        return {
            "ok": False,
            "synced": 0,
            "skipped": [],
            "errors": [],
            "message": "Missing " + " and ".join(missing),
        }

    try:
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(sheet_id)
        files = load_manifest()
        available_tabs = {worksheet.title for worksheet in sheet.worksheets()}
    except Exception as exc:
        return {
            "ok": False,
            "synced": 0,
            "skipped": [],
            "errors": [f"Google Sheet connection: {exc}"],
            "message": "Google Sheet sync unavailable; using committed CSV inputs",
        }
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if only_tabs:
        selected_files = [
            (tab_name, csv_filename)
            for tab_name, csv_filename in files
            if tab_name in only_tabs or csv_filename in only_tabs
        ]
    else:
        selected_files = [
            (tab_name, csv_filename)
            for tab_name, csv_filename in files
            if csv_filename in PRODUCTION_SYNC_CSV_FILES
        ]

    skipped = [
        tab_name for tab_name, _ in selected_files if tab_name not in available_tabs
    ]
    selected_files = [
        (tab_name, csv_filename)
        for tab_name, csv_filename in selected_files
        if tab_name in available_tabs
    ]

    synced = 0
    errors = []
    for start in range(0, len(selected_files), SYNC_BATCH_SIZE):
        batch = selected_files[start : start + SYNC_BATCH_SIZE]
        ranges = [
            f"'{tab_name.replace(chr(39), chr(39) * 2)}'"
            for tab_name, _ in batch
        ]
        try:
            response = sheet.values_batch_get(ranges)
            value_ranges = response.get("valueRanges", [])
            if len(value_ranges) != len(batch):
                raise ValueError(
                    f"Google returned {len(value_ranges)} ranges for {len(batch)} requested tabs"
                )
            for (tab_name, csv_filename), value_range in zip(batch, value_ranges):
                values = value_range.get("values", [])
                pd.DataFrame(values).to_csv(
                    DATA_DIR / csv_filename,
                    index=False,
                    header=False,
                    lineterminator="\r\n",
                )
                synced += 1
        except Exception as exc:
            errors.append(f"{', '.join(tab for tab, _ in batch)}: {exc}")

    return {
        "ok": len(errors) == 0,
        "synced": synced,
        "skipped": skipped,
        "errors": errors,
        "message": f"Synced {synced} Google Sheet tabs",
    }
