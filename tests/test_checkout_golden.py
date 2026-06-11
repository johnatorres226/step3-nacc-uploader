"""Golden-file test for the upload checkout outputs (issue #6 refinement).

Pins the checkout summary CSV and REDCap update payloads for a fixture set
covering: both gates PASS (queued), checker FAIL with coordinator PASS
(excluded by the two-gate rule), single-gate-only (absent), already
finalized in REDCap (skipped), not in report (skipped), and errored ptids
(blocked, with an error note only when present in the report).

Run-dependent values (today's date, created_date) are normalized before
comparison.
"""

import json
import re
from pathlib import Path

import pytest

from src.redcap_data.qc_gates import today_iso
from src.redcap_data.upload_checkout_processor import run_upload_checkout

STATUS_CSV = """ptid,visitdate,stage,status,adcid,module
P001,2026-01-01,form-qc-checker,PASS,48,UDSv4
P001,2026-01-01,form-qc-coordinator,PASS,48,UDSv4
P002,2026-02-01,form-qc-checker,FAIL,48,UDSv4
P002,2026-02-01,form-qc-coordinator,PASS,48,UDSv4
P003,2026-03-01,form-qc-checker,PASS,48,UDSv4
P004,2026-04-01,form-qc-checker,PASS,48,UDSv4
P004,2026-04-01,form-qc-coordinator,PASS,48,UDSv4
P005,2026-05-01,form-qc-checker,PASS,48,UDSv4
P005,2026-05-01,form-qc-coordinator,PASS,48,UDSv4
"""

ERRORS_CSV = """ptid,date,error_description
P002,2026-02-01,missing field a1
P002,2026-02-01,bad value b2
P009,2026-06-01,orphan error
"""

REDCAP_RECORDS = [
    {"ptid": "P001", "visitdate": "2026-01-01", "redcap_event_name": "udsv4visit_arm_1",
     "nacc_finalization_status": "", "redcap_repeat_instance": "2", "upload_notes": "prior note"},
    {"ptid": "P004", "visitdate": "2026-04-01", "redcap_event_name": "udsv4visit_arm_1",
     "nacc_finalization_status": "1"},
    {"ptid": "P002", "visitdate": "2026-02-01", "redcap_event_name": "udsv4visit_arm_1",
     "nacc_finalization_status": ""},
]

GOLDEN_SUMMARY = """ptid,visitdate,module,adcid,fw_finalized,error_count,redcap_action,skip_reason,checkout_message
P001,2026-01-01,UDSv4,48,YES,0,queued_for_redcap_update,,PASS — queued for finalization (nacc_finalization_status=1)
P004,2026-04-01,UDSv4,48,YES,0,skipped,already_finalized_in_redcap,PASS in FW — skipped (already_finalized_in_redcap)
P005,2026-05-01,UDSv4,48,YES,0,skipped,not_in_redcap_report,PASS in FW — skipped (not_in_redcap_report)
P002,2026-02-01,,,NO,2,skipped,has_errors,"FAIL — 2 error(s) found, finalization blocked"
P009,2026-06-01,,,NO,1,skipped,has_errors,"FAIL — 1 error(s) found, finalization blocked"
"""

GOLDEN_UPDATES = {
    "metadata": {"created_date": "<TS>", "total_records": 1,
                 "format_version": "1.0", "type": "finalization_update"},
    "records": [
        {"ptid": "P001", "redcap_event_name": "udsv4visit_arm_1",
         "nacc_finalization_status": "1", "packet_finalization_date": "<DATE>",
         "nacc_upload_status_complete": "2",
         "upload_notes": "prior note; [<DATE>] Upload checkout PASS | Processed by JDT",
         "redcap_repeat_instance": "2"}
    ],
}

GOLDEN_ERROR_NOTES = {
    "metadata": {"created_date": "<TS>", "total_records": 1,
                 "format_version": "1.0", "type": "finalization_update"},
    "records": [
        {"ptid": "P002", "redcap_event_name": "udsv4visit_arm_1",
         "upload_notes": "FW QC: 2 error(s) found | [<DATE>] Upload checkout | Processed by JDT"}
    ],
}

GOLDEN_STATS = {
    "records_queued": 1,
    "records_skipped_pass": 2,
    "records_blocked_errors": 2,
    "records_error_notes": 1,
    "total_fw_finalized": 3,
    "total_errors": 2,
}


def _normalize_json(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    document["metadata"]["created_date"] = "<TS>"
    text = json.dumps(document)
    text = text.replace(today_iso(), "<DATE>")
    return json.loads(text)


@pytest.fixture
def checkout_run(tmp_path):
    errors_csv = tmp_path / "errors.csv"
    status_csv = tmp_path / "status.csv"
    errors_csv.write_text(ERRORS_CSV, encoding="utf-8")
    status_csv.write_text(STATUS_CSV, encoding="utf-8")
    return run_upload_checkout(
        errors_csv_path=errors_csv,
        status_csv_path=status_csv,
        redcap_records=[dict(r) for r in REDCAP_RECORDS],
        initials="JDT",
        output_dir=tmp_path / "out",
    )


def test_checkout_summary_matches_golden(checkout_run):
    summary_path, _, _, _ = checkout_run
    assert summary_path.read_text(encoding="utf-8").replace("\r\n", "\n") == GOLDEN_SUMMARY


def test_checkout_updates_match_golden(checkout_run):
    _, updates_path, _, _ = checkout_run
    assert _normalize_json(updates_path) == GOLDEN_UPDATES


def test_checkout_error_notes_match_golden(checkout_run):
    _, _, error_notes_path, _ = checkout_run
    assert _normalize_json(error_notes_path) == GOLDEN_ERROR_NOTES


def test_checkout_stats_match_golden(checkout_run):
    _, _, _, stats = checkout_run
    assert stats == GOLDEN_STATS


def test_missing_status_column_fails_loudly(tmp_path):
    status_csv = tmp_path / "status.csv"
    status_csv.write_text("ptid,visitdate,status\nP001,2026-01-01,PASS\n", encoding="utf-8")
    errors_csv = tmp_path / "errors.csv"
    errors_csv.write_text(ERRORS_CSV, encoding="utf-8")

    with pytest.raises(ValueError, match=r"stage.*adcid.*module|missing required column"):
        run_upload_checkout(
            errors_csv_path=errors_csv,
            status_csv_path=status_csv,
            redcap_records=[],
            initials="JDT",
            output_dir=tmp_path / "out",
        )


def test_missing_errors_column_fails_loudly(tmp_path):
    errors_csv = tmp_path / "errors.csv"
    errors_csv.write_text("ptid,error_description\nP002,missing a1\n", encoding="utf-8")
    status_csv = tmp_path / "status.csv"
    status_csv.write_text(STATUS_CSV, encoding="utf-8")

    with pytest.raises(ValueError, match="date"):
        run_upload_checkout(
            errors_csv_path=errors_csv,
            status_csv_path=status_csv,
            redcap_records=[],
            initials="JDT",
            output_dir=tmp_path / "out",
        )


def test_both_parser_aliases_share_one_implementation(tmp_path):
    from src.redcap_data import finalization_processor, upload_checkout_processor

    status_csv = tmp_path / "status.csv"
    status_csv.write_text(STATUS_CSV, encoding="utf-8")

    via_finalization = finalization_processor.parse_finalized_records(status_csv)
    via_checkout = upload_checkout_processor.parse_fw_finalized(status_csv)
    assert via_finalization == via_checkout
    assert {r["ptid"] for r in via_finalization} == {"P001", "P004", "P005"}
