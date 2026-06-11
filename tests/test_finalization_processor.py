"""Offline tests for src/redcap_data/finalization_processor.py."""

import json

import pytest

from src.redcap_data.finalization_processor import (
    build_finalization_updates,
    parse_finalized_records,
    save_finalization_json,
)
from src.redcap_data.qc_gates import today_iso

STATUS_CSV = """ptid,visitdate,stage,status,adcid,module
P001,2026-01-01,form-qc-checker,PASS,48,UDSv4
P001,2026-01-01,form-qc-coordinator,PASS,48,UDSv4
P002,2026-02-01,form-qc-checker,FAIL,48,UDSv4
P002,2026-02-01,form-qc-coordinator,PASS,48,UDSv4
P003,2026-03-01,form-qc-checker,PASS,48,UDSv4
P006,2026-06-01,form-qc-coordinator,PASS,48,UDSv4
"""


@pytest.fixture
def status_csv(tmp_path):
    path = tmp_path / "status.csv"
    path.write_text(STATUS_CSV, encoding="utf-8")
    return path


class TestTwoGateRule:
    def test_only_double_pass_is_finalized(self, status_csv):
        finalized = parse_finalized_records(status_csv)
        assert [r["ptid"] for r in finalized] == ["P001"]

    def test_single_gate_pass_is_never_finalized(self, status_csv):
        finalized = parse_finalized_records(status_csv)
        ptids = {r["ptid"] for r in finalized}
        assert "P002" not in ptids  # checker FAIL
        assert "P003" not in ptids  # checker only
        assert "P006" not in ptids  # coordinator only

    def test_missing_column_raises(self, tmp_path):
        path = tmp_path / "status.csv"
        path.write_text("ptid,visitdate,status\nP001,2026-01-01,PASS\n", encoding="utf-8")
        with pytest.raises(ValueError, match="missing required column"):
            parse_finalized_records(path)


class TestBuildFinalizationUpdates:
    FW = [{"ptid": "P001", "visitdate": "2026-01-01", "module": "UDSv4", "adcid": "48"}]

    def test_match_queues_update_with_iso_dates(self):
        redcap = [{
            "ptid": "P001", "visitdate": "2026-01-01",
            "redcap_event_name": "udsv4visit_arm_1",
            "nacc_finalization_status": "", "redcap_repeat_instance": "3",
            "upload_notes": "old",
        }]

        updates, skipped = build_finalization_updates(self.FW, redcap, initials="JDT")

        assert skipped == []
        update = updates[0]
        assert update["nacc_finalization_status"] == "1"
        assert update["nacc_upload_status_complete"] == "2"
        assert update["packet_finalization_date"] == today_iso()
        assert update["redcap_repeat_instance"] == "3"
        assert update["upload_notes"].startswith("old; [" + today_iso() + "]")

    def test_already_finalized_is_skipped(self):
        redcap = [{"ptid": "P001", "visitdate": "2026-01-01", "nacc_finalization_status": "1"}]

        updates, skipped = build_finalization_updates(self.FW, redcap, initials="JDT")

        assert updates == []
        assert skipped[0]["reason"] == "already_finalized_in_redcap"

    def test_not_in_report_is_skipped(self):
        updates, skipped = build_finalization_updates(self.FW, [], initials="JDT")

        assert updates == []
        assert skipped[0]["reason"] == "not_in_redcap_report"

    def test_upload_notes_never_written_when_absent_from_report(self):
        redcap = [{"ptid": "P001", "visitdate": "2026-01-01", "nacc_finalization_status": ""}]

        updates, _ = build_finalization_updates(self.FW, redcap, initials="JDT")

        assert "upload_notes" not in updates[0]


def test_save_finalization_json_shape(tmp_path):
    out = tmp_path / "updates.json"
    save_finalization_json([{"ptid": "P001"}], out)

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["metadata"]["total_records"] == 1
    assert payload["metadata"]["type"] == "finalization_update"
    assert payload["records"] == [{"ptid": "P001"}]
