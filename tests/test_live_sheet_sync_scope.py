from types import SimpleNamespace

import SRC.live_sheet_sync as live_sync


class FakeSheet:
    def __init__(self, titles):
        self._titles = titles
        self.requested_batches = []

    def worksheets(self):
        return [SimpleNamespace(title=title) for title in self._titles]

    def values_batch_get(self, ranges):
        self.requested_batches.append(ranges)
        return {
            "valueRanges": [
                {"values": [["header"], [sheet_range]]}
                for sheet_range in ranges
            ]
        }


def test_default_live_sync_batches_only_production_inputs(monkeypatch, tmp_path):
    manifest = [
        ("PARAMS", "PARAMS.csv"),
        ("LOGIT_PVI", "LOGIT_PVI.csv"),
        ("SHRINKAGE_LEVEL_VALIDATION", "SHRINKAGE_LEVEL_VALIDATION.csv"),
    ]
    sheet = FakeSheet([tab for tab, _ in manifest])
    client = SimpleNamespace(open_by_key=lambda _sheet_id: sheet)

    monkeypatch.setattr(live_sync, "DATA_DIR", tmp_path)
    monkeypatch.setattr(live_sync, "resolve_sheet_id", lambda _secrets: "sheet-id")
    monkeypatch.setattr(live_sync, "resolve_credentials", lambda _secrets: object())
    monkeypatch.setattr(live_sync, "load_manifest", lambda: manifest)
    monkeypatch.setattr(live_sync.gspread, "authorize", lambda _creds: client)

    status = live_sync.sync_inputs_from_google_sheet()

    assert status["ok"] is True
    assert status["synced"] == 2
    assert sheet.requested_batches == [["'PARAMS'", "'LOGIT_PVI'"]]
    assert (tmp_path / "PARAMS.csv").exists()
    assert (tmp_path / "LOGIT_PVI.csv").exists()
    assert not (tmp_path / "SHRINKAGE_LEVEL_VALIDATION.csv").exists()


def test_live_sync_scope_excludes_aborted_and_diagnostic_outputs():
    assert "SEAT_PROBS_3CP.csv" not in live_sync.PRODUCTION_SYNC_CSV_FILES
    assert "SHRINKAGE_LEVEL_VALIDATION.csv" not in live_sync.PRODUCTION_SYNC_CSV_FILES
    assert "CATEGORY_FLOW_PRODUCTION_IMPACT.csv" not in live_sync.PRODUCTION_SYNC_CSV_FILES
    assert "PARAMS.csv" in live_sync.PRODUCTION_SYNC_CSV_FILES
    assert "CATEGORY_PREF_FLOWS_LONG.csv" in live_sync.PRODUCTION_SYNC_CSV_FILES
    assert len(live_sync.PRODUCTION_SYNC_CSV_FILES) == 25
