"""Golden-path tests for checkout/finalization update generation."""

from datetime import datetime

from src.redcap_data.finalization_processor import build_finalization_updates


def test_pass_records_include_note_when_upload_notes_empty():
    """PASS records should always receive a finalization note."""
    finalized_fw_records = [
        {"ptid": "P001", "visitdate": "2024-01-01", "module": "uds"},
        {"ptid": "P002", "visitdate": "2024-01-02", "module": "uds"},
    ]
    redcap_records = [
        {
            "ptid": "P001",
            "visitdate": "2024-01-01",
            "redcap_event_name": "udsvisit_arm_1",
            "nacc_finalization_status": "0",
            "upload_notes": "[01-01-2024] Existing note",
        },
        {
            "ptid": "P002",
            "visitdate": "2024-01-02",
            "redcap_event_name": "udsvisit_arm_1",
            "nacc_finalization_status": "0",
            "upload_notes": "",
        },
    ]

    updates, skipped = build_finalization_updates(finalized_fw_records, redcap_records, "ABC")

    assert skipped == []
    by_ptid = {update["ptid"]: update for update in updates}

    datestamp = datetime.now().strftime("%m-%d-%Y")
    new_note = f"[{datestamp}] Packet finalized by NACC | Processed by ABC"

    assert by_ptid["P001"]["upload_notes"] == f"[01-01-2024] Existing note; {new_note}"
    assert by_ptid["P002"]["upload_notes"] == new_note
