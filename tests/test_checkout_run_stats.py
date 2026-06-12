import json
from pathlib import Path

from src.cli import cli as cli_module


def test_handle_upload_checkout_writes_stats_json(tmp_path, monkeypatch):
    checkout_dir = tmp_path / "checkout"
    checkout_dir.mkdir()

    finalization_json = checkout_dir / "finalization.json"
    error_notes_json = checkout_dir / "error_notes.json"
    finalization_json.write_text("{}", encoding="utf-8")
    error_notes_json.write_text("{}", encoding="utf-8")

    def fake_upload_to_redcap(json_path: Path):
        if json_path == finalization_json:
            return {"success": True, "records_updated": 6}
        if json_path == error_notes_json:
            return {"success": True, "records_updated": 133}
        raise AssertionError(f"Unexpected upload path: {json_path}")

    monkeypatch.setattr(cli_module, "upload_to_redcap", fake_upload_to_redcap)

    stats_path = cli_module._handle_upload_checkout(
        initials="JDT",
        checkout_dir=checkout_dir,
        errors_csv="fw_errors/errors-ingest-form-2026-06-05.csv",
        status_csv="fw_status/qc-status-ingest-form-2026-06-05.csv",
        redcap_snapshot_csv="output/NACC_UPLOAD_05JUN2026-084512/NACC_READYRECORDS_05JUN2026-084512.csv",
        checkout_stats={
            "total_fw_finalized": 31,
            "total_errors_in_fw": 133,
            "records_queued_for_redcap": 6,
            "records_skipped_pass": 25,
            "records_blocked_errors": 133,
            "records_error_notes": 133,
        },
        finalization_json_path=finalization_json,
        error_notes_json_path=error_notes_json,
    )

    assert stats_path == checkout_dir / "checkout-run-stats.json"
    assert stats_path.exists()

    payload = json.loads(stats_path.read_text(encoding="utf-8"))
    assert payload["initiated_by"] == "JDT"
    assert payload["inputs"]["errors_csv"] == "fw_errors/errors-ingest-form-2026-06-05.csv"
    assert payload["inputs"]["status_csv"] == "fw_status/qc-status-ingest-form-2026-06-05.csv"
    assert (
        payload["inputs"]["redcap_snapshot_csv"]
        == "output/NACC_UPLOAD_05JUN2026-084512/NACC_READYRECORDS_05JUN2026-084512.csv"
    )
    assert payload["checkout_stats"]["records_queued_for_redcap"] == 6
    assert payload["checkout_stats"]["records_error_notes"] == 133
    assert payload["redcap_push"]["finalization_status"] == "success"
    assert payload["redcap_push"]["records_finalized"] == 6
    assert payload["redcap_push"]["error_notes_status"] == "success"
    assert payload["redcap_push"]["records_error_notes_pushed"] == 133
