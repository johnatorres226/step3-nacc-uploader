"""Shared two-gate finalization parsing and CSV field handling.

The two-gate rule — form-qc-checker = PASS AND form-qc-coordinator = PASS —
is the safety-critical condition for marking packets finalized in REDCap.
It has exactly one implementation here, shared by the packet-finalization
and upload-checkout paths.

Also home to the explicit column schemas for the pull-errors / pull-status
CSVs (validated loudly at read time) and the project's date policy: ISO
(YYYY-MM-DD) everywhere, payloads and note text alike.
"""

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

FINALIZATION_STAGE = "form-qc-coordinator"
CHECKER_STAGE = "form-qc-checker"

STATUS_CSV_REQUIRED_COLUMNS = ("ptid", "visitdate", "stage", "status", "adcid", "module")
ERRORS_CSV_REQUIRED_COLUMNS = ("ptid", "date")


def field(row: Dict[str, Any], name: str) -> str:
    """Null-safe accessor: a missing key and a None value both become ''."""
    return (row.get(name) or "").strip()


def today_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def note_stamp() -> str:
    """Date stamp embedded in REDCap note text (same ISO policy as payloads)."""
    return today_iso()


def validate_csv_columns(csv_path: Path, required: Tuple[str, ...], label: str) -> None:
    """Fail loudly when an expected column is missing instead of yielding empty strings."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        header = next(csv.reader(f), [])
    missing = [column for column in required if column not in header]
    if missing:
        raise ValueError(
            f"{label} CSV {csv_path.name} is missing required column(s): "
            f"{', '.join(missing)} (found: {', '.join(header) or 'no header'})"
        )


def parse_two_gate_finalized(status_csv_path: Path) -> List[Dict[str, str]]:
    """Parse a pull-status CSV and return packets where BOTH QC gates passed.

    A packet qualifies only when form-qc-checker = PASS AND
    form-qc-coordinator = PASS. Coordinator-pass with checker-fail is
    excluded (and logged) — the packet has errors and must not be finalized.

    Returns:
        List of dicts with keys: ptid, adcid, module, visitdate.
    """
    validate_csv_columns(status_csv_path, STATUS_CSV_REQUIRED_COLUMNS, "pull-status")

    packet_stages: Dict[Tuple[str, str], Dict[str, str]] = {}
    packet_meta: Dict[Tuple[str, str], Dict[str, str]] = {}

    with open(status_csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ptid = field(row, "ptid")
            visitdate = field(row, "visitdate")
            if not ptid or not visitdate:
                continue
            key = (ptid, visitdate)
            if key not in packet_stages:
                packet_stages[key] = {}
                packet_meta[key] = {
                    "ptid": ptid,
                    "adcid": field(row, "adcid"),
                    "module": field(row, "module"),
                    "visitdate": visitdate,
                }
            stage = field(row, "stage")
            if stage in (FINALIZATION_STAGE, CHECKER_STAGE):
                packet_stages[key][stage] = field(row, "status").upper()

    finalized: List[Dict[str, str]] = []
    excluded_checker_fail = 0
    for key, stages in packet_stages.items():
        coordinator_pass = stages.get(FINALIZATION_STAGE) == "PASS"
        checker_pass = stages.get(CHECKER_STAGE) == "PASS"
        if coordinator_pass and checker_pass:
            finalized.append(packet_meta[key])
        elif coordinator_pass and not checker_pass:
            excluded_checker_fail += 1
            logger.warning(
                "Excluded from finalization: ptid=%s visitdate=%s — "
                "form-qc-coordinator=PASS but form-qc-checker=%s",
                key[0],
                key[1],
                stages.get(CHECKER_STAGE, "missing"),
            )

    logger.info(
        "Two-gate parse: %d finalized records; %d excluded due to checker not PASS",
        len(finalized),
        excluded_checker_fail,
    )
    return finalized
