"""Data processor for UDSv4 NACC Uploader.

This module processes REDCap data and creates artifacts for Flywheel upload
and REDCap status updates.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Tuple, Dict, List, Any
import logging
import csv

logger = logging.getLogger(__name__)


def get_timestamp() -> str:
    """Get current timestamp in HHMMSS format."""
    return datetime.now().strftime("%H%M%S")


def get_datestamp() -> str:
    """Get current date in DDMMYYYY format."""
    return datetime.now().strftime("%d%m%Y")


def get_current_date_iso() -> str:
    """Get current date in YYYY-MM-DD format."""
    return datetime.now().strftime("%Y-%m-%d")


def process_data(input_csv_path: Path, initials: str, output_dir: Path) -> Tuple[Path, Path]:
    """Process REDCap data and create upload-ready artifacts.
    
    Args:
        input_csv_path: Path to the fetched REDCap CSV
        initials: User initials for logging and REDCap variables
        output_dir: Base output directory
        
    Returns:
        Tuple of (CSV path for Flywheel, JSON path for REDCap)
        
    Raises:
        FileNotFoundError: If input CSV doesn't exist
        ValueError: If data processing fails
    """
    if not input_csv_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv_path}")
    
    # Create run-scoped data folder
    datestamp = get_datestamp()
    timestamp = get_timestamp()
    data_folder = output_dir / f"NACC_UPLOAD_{datestamp}_{timestamp}"
    data_folder.mkdir(parents=True, exist_ok=True)
    
    # Define output paths
    csv_output_path = data_folder / f"NACC_UPLOAD_{datestamp}_{timestamp}.csv"
    json_output_path = output_dir / "redcap-upload-ready-data" / f"NACC_UPLOAD_{datestamp}_{timestamp}_status.json"
    ready_records_path = data_folder / f"NACC_READYRECORDS_{datestamp}_{timestamp}.csv"
    
    # Ensure JSON output directory exists
    json_output_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Processing data from: {input_csv_path}")
    logger.info(f"Output data folder: {data_folder}")
    
    try:
        # Read input CSV
        records = _read_csv_data(input_csv_path)
        logger.info(f"Read {len(records)} records from input CSV")
        
        # Process records and determine upload status
        ready_records, redcap_updates = _process_records(records, initials)
        logger.info(f"Identified {len(ready_records)} records ready for upload")
        
        # Save ready records snapshot
        _save_ready_records(ready_records, ready_records_path)
        logger.info(f"Ready records saved to: {ready_records_path}")
        
        # Create Flywheel CSV (with columns removed)
        flywheel_records = _prepare_flywheel_data(ready_records)
        _save_csv_data(flywheel_records, csv_output_path)
        logger.info(f"Flywheel CSV saved to: {csv_output_path}")
        
        # Create REDCap JSON
        _save_redcap_json(redcap_updates, json_output_path)
        logger.info(f"REDCap JSON saved to: {json_output_path}")
        
        return csv_output_path, json_output_path
        
    except Exception as e:
        logger.error(f"Data processing failed: {e}")
        raise ValueError(f"Data processing failed: {e}")


def _read_csv_data(csv_path: Path) -> List[Dict[str, Any]]:
    """Read CSV data into list of dictionaries."""
    records = []
    with open(csv_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(dict(row))
    return records


def _process_records(records: List[Dict[str, Any]], initials: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Process records to determine upload eligibility and create REDCap updates.
    
    Args:
        records: List of record dictionaries
        initials: User initials
        
    Returns:
        Tuple of (ready records, REDCap update records)
    """
    ready_records = []
    redcap_updates = []
    current_date = get_current_date_iso()
    
    for record in records:
        # Check if record is ready for upload
        is_initial_upload = _is_initial_upload(record)
        is_reupload_needed = _is_reupload_needed(record)
        
        if is_initial_upload or is_reupload_needed:
            ready_records.append(record.copy())
            
            # Create REDCap update record
            redcap_update = {
                "ptid": record.get("ptid", ""),
                "redcap_event_name": record.get("redcap_event_name", ""),
                "nacc_upload_by_initals": initials,
                "nacc_upload_date": current_date,
                "nacc_upload_status_complete": "1",
                "nacc_reupload_date": current_date if is_reupload_needed else "",
                "nacc_reupload_date_2": current_date if is_reupload_needed else ""
            }
            redcap_updates.append(redcap_update)
            
            logger.debug(f"Record {record.get('ptid')} ready for {'reupload' if is_reupload_needed else 'initial upload'}")
    
    return ready_records, redcap_updates


def _is_initial_upload(record: Dict[str, Any]) -> bool:
    """Check if record is an initial upload (key fields are empty)."""
    initial_upload_fields = [
        "nacc_upload_by_initals",
        "nacc_upload_date",
        "packet_finalization_date",
        "nacc_upload_status_complete"
    ]
    
    return all(not record.get(field, "").strip() for field in initial_upload_fields)


def _is_reupload_needed(record: Dict[str, Any]) -> bool:
    """Check if record needs reupload based on status flags."""
    # If it's an initial upload, no reupload check needed
    if _is_initial_upload(record):
        return False
    
    # Check reupload conditions
    nacc_finalization_status = record.get("nacc_finalization_status", "").strip()
    nacc_finalization_status_2 = record.get("nacc_finalization_status_2", "").strip()
    reupload_status = record.get("reupload_status", "").strip()
    
    return (nacc_finalization_status == "0" or 
            nacc_finalization_status_2 == "0" or 
            reupload_status == "1")


def _prepare_flywheel_data(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Prepare data for Flywheel upload by removing specific columns."""
    columns_to_remove = [
        "redcap_event_name",
        "nacc_upload_by_initals",
        "nacc_upload_date",
        "nacc_finalization_status",
        "reupload_status",
        "nacc_finalization_status_2",
        "packet_finalization_date",
        "nacc_upload_status_complete"
    ]
    
    flywheel_records = []
    for record in records:
        flywheel_record = {k: v for k, v in record.items() if k not in columns_to_remove}
        flywheel_records.append(flywheel_record)
    
    return flywheel_records


def _save_ready_records(records: List[Dict[str, Any]], output_path: Path):
    """Save ready records snapshot to CSV."""
    _save_csv_data(records, output_path)


def _save_csv_data(records: List[Dict[str, Any]], output_path: Path):
    """Save records to CSV file."""
    if not records:
        logger.warning(f"No records to save to {output_path}")
        return
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = records[0].keys()
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(records)


def _save_redcap_json(updates: List[Dict[str, Any]], output_path: Path):
    """Save REDCap updates to JSON file."""
    json_data = {
        "metadata": {
            "created_date": datetime.now().isoformat(),
            "total_records": len(updates),
            "format_version": "1.0"
        },
        "records": updates
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)


def validate_input_data(csv_path: Path) -> Dict[str, Any]:
    """Validate input CSV data structure and content.
    
    Args:
        csv_path: Path to the CSV file to validate
        
    Returns:
        Dictionary with validation results
    """
    validation_result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "record_count": 0,
        "required_columns": []
    }
    
    required_columns = [
        "ptid", "redcap_event_name", "nacc_upload_by_initals", 
        "nacc_upload_date", "nacc_finalization_status", "reupload_status"
    ]
    
    try:
        if not csv_path.exists():
            validation_result["valid"] = False
            validation_result["errors"].append(f"File not found: {csv_path}")
            return validation_result
        
        records = _read_csv_data(csv_path)
        validation_result["record_count"] = len(records)
        
        if not records:
            validation_result["valid"] = False
            validation_result["errors"].append("CSV file is empty")
            return validation_result
        
        # Check required columns
        available_columns = set(records[0].keys())
        missing_columns = [col for col in required_columns if col not in available_columns]
        
        if missing_columns:
            validation_result["valid"] = False
            validation_result["errors"].append(f"Missing required columns: {missing_columns}")
        
        validation_result["required_columns"] = required_columns
        
        # Check for records with missing PTIDs
        missing_ptid_count = sum(1 for record in records if not record.get("ptid", "").strip())
        if missing_ptid_count > 0:
            validation_result["warnings"].append(f"{missing_ptid_count} records have missing PTIDs")
        
        logger.info(f"Validation completed: {validation_result}")
        
    except Exception as e:
        validation_result["valid"] = False
        validation_result["errors"].append(f"Validation error: {e}")
        logger.error(f"Validation failed: {e}")
    
    return validation_result
