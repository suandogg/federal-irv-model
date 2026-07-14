from __future__ import annotations

import argparse
import csv
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


def load_manifest() -> list[tuple[str, str]]:
    manifest = pd.read_csv(MANIFEST_FILE)
    required = {"sheet_name", "csv_file"}
    if not required.issubset(manifest.columns):
        raise SystemExit(f"{MANIFEST_FILE} must contain columns: {', '.join(sorted(required))}")

    rows = []
    for _, row in manifest.iterrows():
        sheet_name = str(row["sheet_name"] or "").strip()
        csv_file = str(row["csv_file"] or "").strip()
        if sheet_name and csv_file:
            rows.append((sheet_name, csv_file))
    return rows


def read_csv_grid(csv_filename: str) -> list[list[str]]:
    path = DATA_DIR / csv_filename
    if not path.exists():
        return []

    with path.open(newline="") as handle:
        return list(csv.reader(handle))


def worksheet_for(sheet, tab_name: str, rows: int, cols: int):
    try:
        worksheet = sheet.worksheet(tab_name)
        worksheet.resize(max(rows, 1), max(cols, 1))
        return worksheet
    except gspread.exceptions.WorksheetNotFound:
        return sheet.add_worksheet(
            title=tab_name,
            rows=max(rows, 1),
            cols=max(cols, 1),
        )


def push_sheet(sheet_id: str, only_tabs: set[str] | None = None) -> None:
    creds = Credentials.from_service_account_file(
        CREDENTIALS_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )

    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(sheet_id)

    print(f"\nPushing CSV snapshot to Google Sheet: {sheet.title}\n")

    for tab_name, csv_filename in load_manifest():
        if only_tabs and tab_name not in only_tabs and csv_filename not in only_tabs:
            continue

        grid = read_csv_grid(csv_filename)
        rows = len(grid)
        cols = max((len(row) for row in grid), default=1)

        try:
            worksheet = worksheet_for(sheet, tab_name, rows, cols)
            worksheet.clear()

            if grid:
                worksheet.update(
                    range_name="A1",
                    values=grid,
                    value_input_option="RAW",
                )

            print(f"  ✓  data/raw/{csv_filename} -> {tab_name} ({rows} rows)")
        except Exception as exc:
            print(f"  x  {tab_name} - error: {exc}")

    print("\nPush complete. You can now edit the Google Sheet and run sync_from_sheets.py.\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate a federal IRV Google Sheet from local CSVs.")
    parser.add_argument("--sheet-id", help="Google Sheet ID to push into.")
    parser.add_argument(
        "--only",
        nargs="*",
        help="Optional list of sheet tab names or CSV filenames to push.",
    )
    args = parser.parse_args()

    push_sheet(resolve_sheet_id(args.sheet_id), set(args.only or []))


if __name__ == "__main__":
    main()
