"""Upload checkout processor for UDSv4 NACC Uploader.

Combines pull-errors and pull-status results to produce a same-day checkout
summary after a Flywheel upload.  For each record visible in Flywheel the
processor determines:

  - fw_finalized=YES  (form-qc-checker AND form-qc-coordinator both PASS,
                        and ptid has zero entries in the errors file)
  - fw_finalized=NO   (one or more error rows exist in the errors file)

Records with fw_finalized=YES are cross-referenced against the current REDCap
upload report.  Those that match are queued for a REDCap finalization update
(nacc_finalization_status=1).  All others are skipped with a reason.

Output artefacts written to NACC_UPLOAD_CHECKOUT_{stamp}/:
  checkout-summary-{YYYY-MM-DD}.csv
  NACC_UPLOAD_CHECKOUT_{stamp}_updates.json
"""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

FINALIZATION_STAGE = "form-qc-coordinator"
CHECKER_STAGE = "form-qc-checker"


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_error_counts(errors_csv_path: Path) -> Dict[str, Dict[str, Any]]:
    """Return per-ptid error counts from a pull-errors CSV.

    The pull-errors CSV has one row per error instance.  Rows are grouped by
    ptid; the visitdate comes from the ``date`` column.

    Returns:
        Dict keyed by ptid → {"error_count": int, "visitdate": str}
    """
    result: Dict[str, Dict[str, Any]] = {}
    with open(errors_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ptid = row.get("ptid", "").strip()
            if not ptid:
                continue
            visitdate = row.get("date", "").strip()
            if ptid not in result:
                result[ptid] = {"error_count": 0, "visitdate": visitdate}
            result[ptid]["error_count"] += 1
    logger.info("Parsed errors for %d ptids from %s", len(result), errors_csv_path.name)
    return result


def parse_fw_finalized(status_csv_path: Path) -> List[Dict[str, str]]:
    """Return records where form-qc-checker AND form-qc-coordinator both PASS.

    Uses the same two-stage logic as finalization_processor so that checkout
    and full packet-finalization stay consistent.

    Returns:
        List of dicts with keys: ptid, adcid, module, visitdate.
    """
    packet_stages: Dict[Tuple[str, str], Dict[str, str]] = {}
    packet_meta: Dict[Tuple[str, str], Dict[str, str]] = {}

    with open(status_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stage = row.get("stage", "").strip()
            status = row.get("status", "").strip().upper()
            ptid = row.get("ptid", "").strip()
            visitdate = row.get("visitdate", "").strip()
            if not ptid or not visitdate:
                continue
            key = (ptid, visitdate)
            if key not in packet_stages:
                packet_stages[key] = {}
                packet_meta[key] = {
                    "ptid": ptid,
                    "adcid": row.get("adcid", "").strip(),
                    "module": row.get("module", "").strip(),
                    "visitdate": visitdate,
                }
            if stage in (FINALIZATION_STAGE, CHECKER_STAGE):
                packet_stages[key][stage] = status

    finalized: List[Dict[str, str]] = []
    for key, stages in packet_stages.items():
        if stages.get(CHECKER_STAGE) == "PASS" and stages.get(FINALIZATION_STAGE) == "PASS":
            finalized.append(packet_meta[key])

    logger.info("Found %d FW-finalized records in %s", len(finalized), status_csv_path.name)
    return finalized


# ---------------------------------------------------------------------------
# Core checkout logic
# ---------------------------------------------------------------------------

def build_checkout_results(
    fw_finalized: List[Dict[str, str]],
    error_counts: Dict[str, Dict[str, Any]],
    redcap_records: List[Dict[str, Any]],
    initials: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Build the three result sets that drive the checkout output.

    Args:
        fw_finalized: Records that passed both QC stages in Flywheel.
        error_counts: Per-ptid error data from parse_error_counts().
        redcap_records: Records from the current REDCap upload report.
        initials: User initials for the upload_notes entry.

    Returns:
        Tuple of (summary_rows, update_records, error_rows, error_note_records)
        - summary_rows: all rows for the checkout-summary CSV
        - update_records: REDCap payloads for PASS records (nacc_finalization_status=1)
        - error_rows: fw_finalized=NO rows (one per errored ptid)
        - error_note_records: REDCap payloads for error records that are in NACC_READYRECORDS
    """
    today = datetime.now().strftime("%Y-%m-%d")
    datestamp = datetime.now().strftime("%m-%d-%Y")
    new_note = f"[{datestamp}] Upload checkout PASS | Processed by {initials}"
    error_note = f"[{datestamp}] Upload checkout | Processed by {initials}"

    # REDCap report index keyed by (ptid, visitdate)
    redcap_index: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for rec in redcap_records:
        ptid = rec.get("ptid", "").strip()
        visitdate = rec.get("visitdate", "").strip()
        if ptid and visitdate:
            key = (ptid, visitdate)
            if key not in redcap_index or rec.get("redcap_repeat_instance", "").strip():
                redcap_index[key] = rec

    summary_rows: List[Dict[str, Any]] = []
    update_records: List[Dict[str, Any]] = []

    # ---- fw_finalized=YES records (from pull-status) ----
    for fw_rec in fw_finalized:
        ptid = fw_rec["ptid"]
        visitdate = fw_rec["visitdate"]
        key = (ptid, visitdate)
        redcap_rec = redcap_index.get(key)

        if redcap_rec is None:
            action = "skipped"
            skip_reason = "not_in_redcap_report"
            msg = f"PASS in FW — skipped (not_in_redcap_report)"
        elif redcap_rec.get("nacc_finalization_status", "").strip() == "1":
            action = "skipped"
            skip_reason = "already_finalized_in_redcap"
            msg = "PASS in FW — skipped (already_finalized_in_redcap)"
        else:
            action = "queued_for_redcap_update"
            skip_reason = ""
            msg = "PASS — queued for finalization (nacc_finalization_status=1)"

            existing_notes = redcap_rec.get("upload_notes", "").strip()
            update: Dict[str, Any] = {
                "ptid": ptid,
                "redcap_event_name": redcap_rec.get("redcap_event_name", "udsvisit_arm_1"),
                "nacc_finalization_status": "1",
                "packet_finalization_date": today,
                "nacc_upload_status_complete": "2",
            }
            if existing_notes:
                update["upload_notes"] = f"{existing_notes}; {new_note}"
            repeat_instance = redcap_rec.get("redcap_repeat_instance", "").strip()
            if repeat_instance:
                update["redcap_repeat_instance"] = repeat_instance
            update_records.append(update)

        summary_rows.append({
            "ptid": ptid,
            "visitdate": visitdate,
            "module": fw_rec.get("module", ""),
            "adcid": fw_rec.get("adcid", ""),
            "fw_finalized": "YES",
            "error_count": 0,
            "redcap_action": action,
            "skip_reason": skip_reason,
            "checkout_message": msg,
        })

    # ---- fw_finalized=NO records (from pull-errors) ----
    error_rows: List[Dict[str, Any]] = []
    error_note_records: List[Dict[str, Any]] = []
    for ptid, err_data in error_counts.items():
        count = err_data["error_count"]
        visitdate = err_data["visitdate"]
        msg = f"FAIL — {count} error(s) found, finalization blocked"
        row = {
            "ptid": ptid,
            "visitdate": visitdate,
            "module": "",
            "adcid": "",
            "fw_finalized": "NO",
            "error_count": count,
            "redcap_action": "skipped",
            "skip_reason": "has_errors",
            "checkout_message": msg,
        }
        summary_rows.append(row)
        error_rows.append(row)

        # Build a REDCap note update for error records that are in NACC_READYRECORDS
        redcap_rec = redcap_index.get((ptid, visitdate))
        if redcap_rec:
            existing_notes = redcap_rec.get("upload_notes", "").strip()
            note_text = f"FW QC: {count} error(s) found | {error_note}"
            error_update: Dict[str, Any] = {
                "ptid": ptid,
                "redcap_event_name": redcap_rec.get("redcap_event_name", "udsvisit_arm_1"),
                "upload_notes": f"{existing_notes}; {note_text}" if existing_notes else note_text,
            }
            repeat_instance = redcap_rec.get("redcap_repeat_instance", "").strip()
            if repeat_instance:
                error_update["redcap_repeat_instance"] = repeat_instance
            error_note_records.append(error_update)

    logger.info(
        "Checkout results: %d queued for REDCap, %d skipped (PASS), %d blocked (errors), %d error notes",
        len(update_records),
        len([r for r in summary_rows if r["fw_finalized"] == "YES" and r["redcap_action"] == "skipped"]),
        len(error_rows),
        len(error_note_records),
    )
    return summary_rows, update_records, error_rows, error_note_records


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

SUMMARY_FIELDS = [
    "ptid", "visitdate", "module", "adcid",
    "fw_finalized", "error_count", "redcap_action", "skip_reason", "checkout_message",
]


def save_checkout_summary_csv(summary_rows: List[Dict[str, Any]], output_path: Path) -> None:
    """Write checkout-summary-{YYYY-MM-DD}.csv."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(summary_rows)
    logger.info("Checkout summary CSV saved to: %s", output_path)


def save_checkout_updates_json(update_records: List[Dict[str, Any]], output_path: Path) -> None:
    """Write NACC_UPLOAD_CHECKOUT_{stamp}_updates.json."""
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
        json.dump(payload, f, indent=2, ensure_ascii=False)
    logger.info("Checkout updates JSON saved to: %s", output_path)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_upload_checkout(
    errors_csv_path: Path,
    status_csv_path: Path,
    redcap_records: List[Dict[str, Any]],
    initials: str,
    output_dir: Path,
) -> Tuple[Path, Path, Path, Dict[str, int]]:
    """Run the full upload checkout and write output artefacts.

    Args:
        errors_csv_path: Pull-errors CSV produced by --pull-errors.
        status_csv_path: Pull-status CSV produced by --pull-status.
        redcap_records: Records from the current REDCap upload report.
        initials: User initials for REDCap notes.
        output_dir: Base output directory (e.g. output/).

    Returns:
        Tuple of (checkout_summary_path, checkout_updates_json_path, stats).
        stats keys: records_queued, records_skipped_pass, records_blocked_errors,
                    total_fw_finalized, total_errors.
    """
    datestamp = datetime.now().strftime("%d%b%Y").upper()
    timestamp = datetime.now().strftime("%H%M%S")
    today_iso = datetime.now().strftime("%Y-%m-%d")
    stamp = f"{datestamp}-{timestamp}"

    folder = output_dir / f"NACC_UPLOAD_CHECKOUT_{stamp}"
    folder.mkdir(parents=True, exist_ok=True)

    summary_path = folder / f"checkout-summary-{today_iso}.csv"
    updates_path = folder / f"NACC_UPLOAD_CHECKOUT_{stamp}_updates.json"

    error_counts = parse_error_counts(errors_csv_path)
    fw_finalized = parse_fw_finalized(status_csv_path)

    summary_rows, update_records, error_rows, error_note_records = build_checkout_results(
        fw_finalized, error_counts, redcap_records, initials
    )

    error_notes_path = folder / f"NACC_UPLOAD_CHECKOUT_{stamp}_error_notes.json"

    stats: Dict[str, int] = {
        "records_queued": len(update_records),
        "records_skipped_pass": len(
            [r for r in summary_rows if r["fw_finalized"] == "YES" and r["redcap_action"] == "skipped"]
        ),
        "records_blocked_errors": len(error_rows),
        "records_error_notes": len(error_note_records),
        "total_fw_finalized": len(fw_finalized),
        "total_errors": len(error_counts),
    }

    save_checkout_summary_csv(summary_rows, summary_path)
    save_checkout_updates_json(update_records, updates_path)
    save_checkout_updates_json(error_note_records, error_notes_path)

    return summary_path, updates_path, error_notes_path, stats
