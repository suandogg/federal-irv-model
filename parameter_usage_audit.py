from __future__ import annotations

import ast
import csv
import difflib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
REPORT_DIR = ROOT / "reports"
PYTHON_MODEL_FILES = (
    ROOT / "app.py",
    ROOT / "SRC" / "irv.py",
    ROOT / "SRC" / "loaders.py",
    ROOT / "SRC" / "preference_engine.py",
)


def _python_scalar_usage() -> dict[str, list[str]]:
    usage: dict[str, list[str]] = {}

    for path in PYTHON_MODEL_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue

            is_scalar_helper = isinstance(node.func, ast.Name) and node.func.id == "_scalar"
            is_scalars_get = (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "scalars"
            )
            if not (is_scalar_helper or is_scalars_get):
                continue

            key_arg = node.args[1] if is_scalar_helper and len(node.args) > 1 else node.args[0]
            if not isinstance(key_arg, ast.Constant) or not isinstance(key_arg.value, str):
                continue

            key = key_arg.value.strip().upper()
            location = f"{path.relative_to(ROOT)}:{node.lineno}"
            usage.setdefault(key, []).append(location)

    return usage


def _sheet_scalar_settings() -> dict[str, dict[str, str]]:
    settings: dict[str, dict[str, str]] = {}
    path = RAW_DIR / "PARAMS.csv"

    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row_number, row in enumerate(csv.reader(handle), start=1):
            if len(row) < 2:
                continue

            key = row[0].strip().upper()
            if not re.fullmatch(r"[A-Z][A-Z0-9]*_[A-Z0-9_]+", key):
                continue

            try:
                float(row[1])
            except (TypeError, ValueError):
                continue

            settings[key] = {
                "value": row[1].strip(),
                "description": row[2].strip() if len(row) > 2 else "",
                "sheet_location": f"PARAMS!A{row_number}:C{row_number}",
            }

    return settings


def build_scalar_audit() -> list[dict[str, str]]:
    sheet_settings = _sheet_scalar_settings()
    runtime_usage = _python_scalar_usage()
    rows: list[dict[str, str]] = []

    for key in sorted(sheet_settings):
        setting = sheet_settings[key]
        locations = runtime_usage.get(key, [])
        close_runtime = difflib.get_close_matches(key, runtime_usage, n=1, cutoff=0.82)
        mismatch = close_runtime[0] if not locations and close_runtime else ""

        rows.append(
            {
                "parameter": key,
                "sheet_value": setting["value"],
                "status": "active" if locations else "unused",
                "production_locations": "; ".join(locations),
                "possible_name_mismatch": mismatch,
                "sheet_location": setting["sheet_location"],
                "description": setting["description"],
            }
        )

    for key in sorted(set(runtime_usage) - set(sheet_settings)):
        close_sheet = difflib.get_close_matches(key, sheet_settings, n=1, cutoff=0.82)
        rows.append(
            {
                "parameter": key,
                "sheet_value": "",
                "status": "code_default_only",
                "production_locations": "; ".join(runtime_usage[key]),
                "possible_name_mismatch": close_sheet[0] if close_sheet else "",
                "sheet_location": "",
                "description": "Read by production code but not declared under this name in PARAMS.",
            }
        )

    return rows


def build_structured_input_audit() -> list[dict[str, str]]:
    return [
        {
            "input": "PARAMS primary-model a table",
            "status": "active",
            "production_use": "Controls party-specific PVI strength in statewide primary adjustment.",
        },
        {
            "input": "PARAMS primary-model UseLogit table",
            "status": "active",
            "production_use": "Selects additive or logit PVI adjustment by party.",
        },
        {
            "input": "PARAMS preference matrix (A1:G7)",
            "status": "unused",
            "production_use": "Python uses the state PREF_MATRIX sheets instead.",
        },
        {
            "input": "PARAMS MinorParty Uplift table",
            "status": "unused",
            "production_use": "Not loaded by the Python model.",
        },
        {
            "input": "PARAMS Geography table",
            "status": "unused",
            "production_use": "Not loaded by the Python model.",
        },
        {
            "input": "SCENARIO_STATS Share",
            "status": "active",
            "production_use": "Loaded as pooled posterior preference scenarios.",
        },
        {
            "input": "SCENARIO_STATS Votes / ScenarioTotal / Seats",
            "status": "active_metadata",
            "production_use": "Preserved as evidence metadata for shrinkage and reliability reporting.",
        },
        {
            "input": "SEAT_PREF_FLOWS_LONG Share",
            "status": "active",
            "production_use": "Exact seat and AliveSet preference-flow override.",
        },
        {
            "input": "SEAT_PREF_FLOWS_LONG Votes",
            "status": "active_metadata",
            "production_use": "Preserved for seat-level evidence, pooled statistics and variance estimation.",
        },
        {
            "input": "SEAT_SHRINKAGE_OVERRIDES",
            "status": "conditionally_active",
            "production_use": "Overrides the global SEAT_SHRINKAGE_K only for rows explicitly enabled by division.",
        },
        {
            "input": "CANDIDATE_CLASSIFICATION",
            "status": "reference_input_pending_recompile",
            "production_use": "Candidate-level category, subtype and observed flow evidence for the shadow recompilation pipeline; it does not yet replace production preference evidence.",
        },
        {
            "input": "IDEOLOGY",
            "status": "conditionally_active",
            "production_use": "Fallback when exact/AEC/posterior evidence is incomplete or unavailable.",
        },
        {
            "input": "SIPHON",
            "status": "loaded_but_unused",
            "production_use": "Loaded into params but never consulted by the Python production engine.",
        },
        {
            "input": "CALIBRATION_PARAMS",
            "status": "unused",
            "production_use": "Synced but not loaded by the Python production engine.",
        },
    ]


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_reports() -> tuple[Path, Path, Path]:
    scalar_rows = build_scalar_audit()
    input_rows = build_structured_input_audit()
    REPORT_DIR.mkdir(exist_ok=True)

    scalar_path = REPORT_DIR / "parameter_usage_audit.csv"
    input_path = REPORT_DIR / "structured_input_usage_audit.csv"
    markdown_path = REPORT_DIR / "parameter_usage_audit.md"
    _write_csv(scalar_path, scalar_rows)
    _write_csv(input_path, input_rows)

    active = sum(row["status"] == "active" for row in scalar_rows)
    unused = sum(row["status"] == "unused" for row in scalar_rows)
    defaults = sum(row["status"] == "code_default_only" for row in scalar_rows)
    mismatches = [row for row in scalar_rows if row["possible_name_mismatch"]]

    lines = [
        "# Federal model parameter-usage audit",
        "",
        "This report describes the current Python production path. It does not change model behaviour.",
        "",
        f"- Active scalar settings: {active}",
        f"- Unused scalar settings: {unused}",
        f"- Code-default-only settings: {defaults}",
        f"- Possible naming mismatches: {len(mismatches)}",
        "",
        "## Possible naming mismatches",
        "",
    ]
    if mismatches:
        for row in mismatches:
            lines.append(
                f"- `{row['parameter']}` ↔ `{row['possible_name_mismatch']}` "
                f"({row['status']})"
            )
    else:
        lines.append("- None.")

    lines.extend(
        [
            "",
            "## Structured inputs requiring attention",
            "",
        ]
    )
    for row in input_rows:
        if row["status"] != "active":
            lines.append(
                f"- **{row['input']}** — `{row['status']}`: {row['production_use']}"
            )

    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return scalar_path, input_path, markdown_path


def main() -> None:
    for path in write_reports():
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
