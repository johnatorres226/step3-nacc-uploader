"""Finalization processor for UDSv4 NACC Uploader.

Processes Flywheel QC status data to identify packets that have been finalized
by NACC and generates REDCap update records for those packets.

A packet is considered finalized only when ALL of the following are true:
  - 'form-qc-checker' stage has a 'PASS' status (no errors in the packet)
  - 'form-qc-coordinator' stage has a 'PASS' status (coordinator accepted it)

If form-qc-checker = FAIL the packet has errors and must NOT be marked finalized
in REDCap regardless of the coordinator status.
"""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.redcap_data.qc_gates import (
    CHECKER_STAGE,
    FINALIZATION_STAGE,
    field,
    note_stamp,
    parse_two_gate_finalized,
    today_iso,
)

logger = logging.getLogger(__name__)


def parse_finalized_records(status_csv_path: Path) -> List[Dict[str, str]]:
    """Parse QC status CSV and return records where both QC stages passed.

    Thin alias over qc_gates.parse_two_gate_finalized() — the single
    implementation of the two-gate rule shared with upload checkout.
    """
    return parse_two_gate_finalized(status_csv_path)


def build_finalization_updates(
    finalized_fw_records: List[Dict[str, str]],
    redcap_records: List[Dict[str, Any]],
    initials: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Cross-reference finalized Flywheel records with REDCap report and build update payloads.

    Matching key: ptid + visitdate (both present in Flywheel status and REDCap report).

    A record is included in the update set only if:
    - It appears in the REDCap report (ptid+visitdate match found)
    - Its 'nacc_finalization_status' in REDCap is NOT already '1'

    REDCap update fields set per finalized record:
    - nacc_finalization_status: '1'  (Packet Finalized = Yes)
    - packet_finalization_date: today in YYYY-MM-DD
    - nacc_upload_status_complete: '2'  (Complete)
    - upload_notes: existing notes appended with finalization note

    Args:
        finalized_fw_records: Finalized records from parse_finalized_records().
        redcap_records: All REDCap records fetched from the upload report.
        initials: User initials to embed in the upload_notes entry.

    Returns:
        Tuple of (update_records, skipped_records).
    """
    today = today_iso()
    new_note = f"[{note_stamp()}] Packet finalized by NACC | Processed by {initials}"

    # Build lookup index: (ptid, visitdate) -> redcap_record
    redcap_index: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for rec in redcap_records:
        ptid = field(rec, "ptid")
        visitdate = field(rec, "visitdate")
        if ptid and visitdate:
            key = (ptid, visitdate)
            if key in redcap_index:
                # If duplicate (shouldn't happen), keep the one with a repeat instance
                if field(rec, "redcap_repeat_instance"):
                    redcap_index[key] = rec
            else:
                redcap_index[key] = rec

    update_records: List[Dict[str, Any]] = []
    skipped_records: List[Dict[str, Any]] = []

    for fw_rec in finalized_fw_records:
        ptid = fw_rec["ptid"]
        visitdate = fw_rec["visitdate"]
        key = (ptid, visitdate)

        redcap_rec = redcap_index.get(key)

        if redcap_rec is None:
            logger.warning(
                "Finalized FW record not found in REDCap report: ptid=%s visitdate=%s "
                "(may already be finalized in REDCap or not yet in report)",
                ptid,
                visitdate,
            )
            skipped_records.append(
                {
                    "ptid": ptid,
                    "visitdate": visitdate,
                    "module": fw_rec.get("module", ""),
                    "reason": "not_in_redcap_report",
                }
            )
            continue

        # Skip if already marked finalized in REDCap
        if field(redcap_rec, "nacc_finalization_status") == "1":
            logger.debug("Already finalized in REDCap: ptid=%s visitdate=%s", ptid, visitdate)
            skipped_records.append(
                {
                    "ptid": ptid,
                    "visitdate": visitdate,
                    "module": fw_rec.get("module", ""),
                    "reason": "already_finalized_in_redcap",
                }
            )
            continue

        # Build REDCap update record.
        #
        # NOTE on upload_notes: The REDCap upload report (NACC_REDCAP_REPORT_ID) does
        # not currently include the upload_notes field.  If upload_notes is absent from
        # redcap_rec, we MUST NOT write it — doing so would overwrite existing history
        # in REDCap with an empty-prefixed string.
        # Only append when we can confirm the existing text (report provides non-empty value).
        # Add upload_notes to the REDCap report if you want the finalization event logged there.
        existing_notes = field(redcap_rec, "upload_notes")

        update: Dict[str, Any] = {
            "ptid": ptid,
            "redcap_event_name": redcap_rec.get("redcap_event_name", "udsvisit_arm_1"),
            "nacc_finalization_status": "1",
            "packet_finalization_date": today,
            "nacc_upload_status_complete": "2",
        }

        if existing_notes:
            update["upload_notes"] = f"{existing_notes}; {new_note}"
        else:
            logger.debug(
                "upload_notes not in report for ptid=%s; field left unchanged in REDCap", ptid
            )

        # Include repeat instance if present (required for repeating events in REDCap)
        repeat_instance = field(redcap_rec, "redcap_repeat_instance")
        if repeat_instance:
            update["redcap_repeat_instance"] = repeat_instance

        update_records.append(update)
        logger.debug(
            "Queued REDCap finalization update: ptid=%s visitdate=%s instance=%s",
            ptid,
            visitdate,
            repeat_instance or "N/A",
        )

    logger.info(
        "Finalization build complete: %d to update, %d skipped",
        len(update_records),
        len(skipped_records),
    )
    return update_records, skipped_records


def save_finalization_json(update_records: List[Dict[str, Any]], output_path: Path) -> None:
    """Save finalization update records to a JSON file for REDCap import.

    The JSON format matches the structure expected by upload_to_redcap().

    Args:
        update_records: List of REDCap update dicts from build_finalization_updates().
        output_path: Destination file path.
    """
    payload = {
        "metadata": {
            "created_date": datetime.now().isoformat(),
            "total_records": len(update_records),
            "format_version": "1.0",
            "type": "finalization_update",
        },
        "records": update_records,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    logger.info("Finalization JSON saved to: %s", output_path)


def save_finalized_csv(
    finalized_fw_records: List[Dict[str, str]],
    skipped_records: List[Dict[str, Any]],
    update_records: List[Dict[str, Any]],
    output_path: Path,
) -> None:
    """Save a summary CSV of all finalized FW records and their disposition.

    Columns: ptid, visitdate, module, adcid, fw_finalized, redcap_action, reason

    Args:
        finalized_fw_records: All records found finalized in Flywheel.
        skipped_records: Records skipped (already done or not in report).
        update_records: Records queued for REDCap update.
        output_path: Destination file path.
    """
    # Build lookup sets for disposition labeling
    skipped_map = {(r["ptid"], r["visitdate"]): r.get("reason", "") for r in skipped_records}
    update_set = {(r["ptid"], r.get("packet_finalization_date", "")): True for r in update_records}
    update_ptids = {r["ptid"] for r in update_records}

    rows = []
    for fw_rec in finalized_fw_records:
        ptid = fw_rec["ptid"]
        visitdate = fw_rec["visitdate"]
        key = (ptid, visitdate)

        if ptid in update_ptids:
            action = "queued_for_redcap_update"
            reason = ""
        else:
            action = "skipped"
            reason = skipped_map.get(key, "unknown")

        rows.append(
            {
                "ptid": ptid,
                "visitdate": visitdate,
                "module": fw_rec.get("module", ""),
                "adcid": fw_rec.get("adcid", ""),
                "fw_finalized": "YES",
                "redcap_action": action,
                "skip_reason": reason,
            }
        )

    fieldnames = ["ptid", "visitdate", "module", "adcid", "fw_finalized", "redcap_action", "skip_reason"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    logger.info("Finalization summary CSV saved to: %s", output_path)
