from __future__ import annotations

import argparse
import os
from pathlib import Path

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "raw"
MANIFEST_FILE = DATA_DIR / "_manifest.csv"
CREDENTIALS_FILE = ROOT / "credentials.json"
SHEET_ID_FILE = ROOT / "sheet_id.txt"


def resolve_sheet_id(cli_sheet_id: str | None) -> str:
    if cli_sheet_id:
        return cli_sheet_id.strip()

    env_sheet_id = os.environ.get("FEDERAL_IRV_SHEET_ID", "").strip()
    if env_sheet_id:
        return env_sheet_id

    if SHEET_ID_FILE.exists():
        return SHEET_ID_FILE.read_text().strip()

    raise SystemExit(
        "No Google Sheet ID supplied. Pass --sheet-id, set FEDERAL_IRV_SHEET_ID, "
        "or create sheet_id.txt containing the Google Sheet ID."
    )


def load_manifest() -> dict[str, str]:
    manifest = pd.read_csv(MANIFEST_FILE)
    required = {"sheet_name", "csv_file"}
    if not required.issubset(manifest.columns):
        raise SystemExit(f"{MANIFEST_FILE} must contain columns: {', '.join(sorted(required))}")

    files = {}
    for _, row in manifest.iterrows():
        sheet_name = str(row["sheet_name"] or "").strip()
        csv_file = str(row["csv_file"] or "").strip()
        if sheet_name and csv_file:
            files[sheet_name] = csv_file
    return files


def worksheet_to_dataframe(worksheet) -> pd.DataFrame:
    values = worksheet.get_all_values()
    return pd.DataFrame(values)


def sync_sheet(sheet_id: str, only_tabs: set[str] | None = None) -> None:
    creds = Credentials.from_service_account_file(
        CREDENTIALS_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )

    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(sheet_id)
    files = load_manifest()
    available_tabs = {worksheet.title for worksheet in sheet.worksheets()}

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\nSyncing from Google Sheet: {sheet.title}\n")

    for tab_name, csv_filename in files.items():
        if only_tabs and tab_name not in only_tabs and csv_filename not in only_tabs:
            continue

        if tab_name not in available_tabs:
            print(f"  x  {tab_name} - tab not found, skipping")
            continue

        try:
            worksheet = sheet.worksheet(tab_name)
            df = worksheet_to_dataframe(worksheet)
            out_path = DATA_DIR / csv_filename
            df.to_csv(out_path, index=False, header=False, lineterminator="\r\n")
            print(f"  ✓  {tab_name} -> data/raw/{csv_filename} ({len(df)} rows)")
        except Exception as exc:
            print(f"  x  {tab_name} - error: {exc}")

    print("\nSync complete. Restart Streamlit to pick up changes.\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync federal IRV CSV inputs from Google Sheets.")
    parser.add_argument("--sheet-id", help="Google Sheet ID to sync from.")
    parser.add_argument(
        "--only",
        nargs="*",
        help="Optional list of sheet tab names or CSV filenames to sync.",
    )
    args = parser.parse_args()

    sync_sheet(resolve_sheet_id(args.sheet_id), set(args.only or []))


if __name__ == "__main__":
    main()
