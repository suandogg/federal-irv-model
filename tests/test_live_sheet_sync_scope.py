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
        ("PARTISAN_VOTE_INDEX", "PARTISAN_VOTE_INDEX.csv"),
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
    assert sheet.requested_batches == [["'PARAMS'", "'PARTISAN_VOTE_INDEX'"]]
    assert (tmp_path / "PARAMS.csv").exists()
    assert (tmp_path / "PARTISAN_VOTE_INDEX.csv").exists()
    assert not (tmp_path / "LOGIT_PVI.csv").exists()
    assert not (tmp_path / "SHRINKAGE_LEVEL_VALIDATION.csv").exists()


def test_live_sync_scope_excludes_aborted_and_diagnostic_outputs():
    assert "SEAT_PROBS_3CP.csv" not in live_sync.PRODUCTION_SYNC_CSV_FILES
    assert "SHRINKAGE_LEVEL_VALIDATION.csv" not in live_sync.PRODUCTION_SYNC_CSV_FILES
    assert "CATEGORY_FLOW_PRODUCTION_IMPACT.csv" not in live_sync.PRODUCTION_SYNC_CSV_FILES
    assert "PARAMS.csv" in live_sync.PRODUCTION_SYNC_CSV_FILES
    assert "CATEGORY_PREF_FLOWS_LONG.csv" in live_sync.PRODUCTION_SYNC_CSV_FILES
    assert "PARTISAN_VOTE_INDEX.csv" in live_sync.PRODUCTION_SYNC_CSV_FILES
    assert "LOGIT_PVI.csv" not in live_sync.PRODUCTION_SYNC_CSV_FILES
    assert {"FORECAST PARAMS.csv", "DISPLAY PARAMS.csv", "CANDIDATE_CLASSIFICATION.csv"}.issubset(live_sync.PRODUCTION_SYNC_CSV_FILES)
    assert len(live_sync.PRODUCTION_SYNC_CSV_FILES) == 27


def test_testing_workbook_cannot_be_redirected_by_main_setting(monkeypatch, tmp_path):
    path=tmp_path/'sheet_id.txt';path.write_text('testing-workbook')
    monkeypatch.setattr(live_sync,'SHEET_ID_FILE',path)
    monkeypatch.setenv('FEDERAL_IRV_SHEET_ID','main-workbook')
    monkeypatch.delenv('FEDERAL_TESTING_SHEET_ID',raising=False)
    assert live_sync.resolve_sheet_id({'google_sheet_id':'main-secret'})=='testing-workbook'


def test_forecast_tab_refresh_changes_loaded_settings(monkeypatch,tmp_path):
    from SRC.forecast_params import parameter_table,load_forecast_params
    table=parameter_table();table.loc[table.Parameter=='SEED','Value']=42
    values=[table.columns.tolist()]+table.values.tolist()
    sheet=FakeSheet(['FORECAST PARAMS'])
    sheet.values_batch_get=lambda ranges:{'valueRanges':[{'values':values}]}
    monkeypatch.setattr(live_sync,'DATA_DIR',tmp_path)
    monkeypatch.setattr(live_sync,'resolve_sheet_id',lambda _: 'testing')
    monkeypatch.setattr(live_sync,'resolve_credentials',lambda _:object())
    monkeypatch.setattr(live_sync,'load_manifest',lambda:[('FORECAST PARAMS','FORECAST PARAMS.csv')])
    monkeypatch.setattr(live_sync.gspread,'authorize',lambda _:SimpleNamespace(open_by_key=lambda _:sheet))
    assert live_sync.sync_inputs_from_google_sheet()['ok']
    assert load_forecast_params(tmp_path/'FORECAST PARAMS.csv')[0]['SEED']==42
