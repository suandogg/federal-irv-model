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
    sheet_id = resolve_sheet_id(secrets)
    creds = resolve_credentials(secrets)

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

    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(sheet_id)
    files = load_manifest()
    available_tabs = {worksheet.title for worksheet in sheet.worksheets()}
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    synced = 0
    skipped = []
    errors = []

    for tab_name, csv_filename in files:
        if only_tabs and tab_name not in only_tabs and csv_filename not in only_tabs:
            continue

        if tab_name not in available_tabs:
            skipped.append(tab_name)
            continue

        try:
            worksheet = sheet.worksheet(tab_name)
            values = worksheet.get_all_values()
            df = pd.DataFrame(values)
            df.to_csv(DATA_DIR / csv_filename, index=False, header=False, lineterminator="\r\n")
            synced += 1
        except Exception as exc:
            errors.append(f"{tab_name}: {exc}")

    return {
        "ok": len(errors) == 0,
        "synced": synced,
        "skipped": skipped,
        "errors": errors,
        "message": f"Synced {synced} Google Sheet tabs",
    }
