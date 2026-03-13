"""REDCap data fetcher for UDSv4 NACC Uploader.

This module handles fetching reports from REDCap with filtering based on mode and PTIDs.
Follows the specifications in REDCAP_REPORT_PULL.md.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import logging
import requests
import csv

logger = logging.getLogger(__name__)


def get_timestamp() -> str:
    """Get current timestamp in HHMMSS format."""
    return datetime.now().strftime("%H%M%S")


def get_datestamp() -> str:
    """Get current date in DDMMYYYY format."""
    return datetime.now().strftime("%d%m%Y")


def fetch_redcap_report(ptids: Optional[List[str]] = None) -> Path:
    """Fetch REDCap report and apply filtering based on PTIDs.
    
    Uses NACC_REDCAP_REPORT_ID from environment to fetch specific report.
    
    Args:
        ptids: List of PTIDs for filtering. If empty or None, fetches all eligible records
        
    Returns:
        Path to the fetched CSV file
        
    Raises:
        ConnectionError: If REDCap API connection fails
        FileNotFoundError: If report cannot be fetched
        ValueError: If NACC_REDCAP_REPORT_ID not found in environment
    """
    # Verify REDCap report ID is configured
    report_id = os.getenv('NACC_REDCAP_REPORT_ID')
    if not report_id:
        raise ValueError("NACC_REDCAP_REPORT_ID environment variable not found")
    
    # Verify REDCap API credentials (try both REDCAP_API_KEY and REDCAP_API_TOKEN)
    redcap_api_key = os.getenv('REDCAP_API_KEY') or os.getenv('REDCAP_API_TOKEN')
    redcap_api_url = os.getenv('REDCAP_API_URL')
    
    if not redcap_api_key or not redcap_api_url:
        raise ValueError("REDCAP_API_KEY (or REDCAP_API_TOKEN) and REDCAP_API_URL environment variables are required")
    
    # Determine mode based on PTIDs
    if not ptids:
        mode = "all"
    elif len(ptids) == 1:
        mode = "single"
    else:
        mode = "batch"
    
    # Generate output filename following convention
    datestamp = get_datestamp()
    timestamp = get_timestamp()
    filename = f"REDCAP_NACC_UPLOAD_REPORT_{datestamp}_{timestamp}.csv"
    
    # Create data directory if it doesn't exist
    data_dir = Path.cwd() / "data"
    data_dir.mkdir(exist_ok=True)
    
    output_path = data_dir / filename
    
    logger.info(f"Fetching REDCap report (ID: {report_id}, mode: {mode})")
    if ptids:
        logger.info(f"Filtering for PTIDs: {ptids}")
    
    try:
        # Fetch data from REDCap API
        _fetch_from_redcap_api(output_path, mode, ptids, report_id, redcap_api_key, redcap_api_url)
        
        logger.info(f"REDCap report saved to: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Failed to fetch REDCap report: {e}")
        raise


def _fetch_from_redcap_api(output_path: Path, mode: str, ptids: Optional[List[str]], 
                           report_id: str, api_key: str, api_url: str):
    """Fetch actual data from REDCap API and save to CSV.
    
    Args:
        output_path: Path where to save the CSV file
        mode: Filtering mode (all, single, batch)
        ptids: List of PTIDs to filter by
        report_id: REDCap report ID
        api_key: REDCap API key
        api_url: REDCap API URL
    """
    # Prepare API request
    data = {
        'token': api_key,
        'content': 'report',
        'report_id': report_id,
        'format': 'csv',
        'rawOrLabel': 'raw',
        'rawOrLabelHeaders': 'raw',
        'exportCheckboxLabel': 'false',
        'returnFormat': 'csv'
    }
    
    logger.info(f"Making REDCap API request for report {report_id}")
    
    # Make API call
    response = requests.post(api_url, data=data)
    
    if response.status_code != 200:
        raise ConnectionError(f"REDCap API request failed with status {response.status_code}: {response.text}")
    
    # Parse CSV response
    lines = response.text.strip().split('\n')
    if not lines:
        raise ValueError("Empty response from REDCap API")
    
    # Read CSV data
    csv_reader = csv.DictReader(lines)
    all_records = list(csv_reader)
    
    logger.info(f"Fetched {len(all_records)} total records from REDCap")
    
    # Apply filtering based on PTIDs
    if ptids:
        filtered_records = [r for r in all_records if r.get('ptid', '').strip() in ptids]
        logger.info(f"Filtered to {len(filtered_records)} records matching PTIDs: {ptids}")
    else:
        filtered_records = all_records
        logger.info(f"No PTID filter applied, using all {len(filtered_records)} records")
    
    # Write filtered data to output file
    if filtered_records:
        fieldnames = csv_reader.fieldnames
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(filtered_records)
    else:
        # Write empty CSV with headers
        fieldnames = csv_reader.fieldnames
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
        logger.warning("No records matched the filter criteria")


def _create_placeholder_report(output_path: Path, mode: str, ptids: Optional[List[str]], report_id: str):
    """Create a placeholder CSV report for development/testing purposes.
    
    THIS IS DEPRECATED - Use _fetch_from_redcap_api instead.
    
    Args:
        output_path: Path where to save the CSV file
        mode: Filtering mode (all, single, batch)
        ptids: List of PTIDs to filter by
        report_id: REDCap report ID from environment
    """
    logger.warning("Using placeholder data - this should not be used in production")
    # Sample data structure - these variables are no longer used:
    # nacc_upload_by_initals, reupload_status, nacc_finalization_status_2
    header = [
        "ptid", "redcap_event_name", "nacc_upload_date",
        "nacc_finalization_status", "nacc_upload_status_complete",
        "packet_finalization_date", "upload_notes",
        "module", "adcid", "visitdate", "visitnum", "variable1", "variable2"
    ]
    
    # Create sample data (without discontinued variables)
    if mode == "all":
        # Generate multiple records for all mode
        sample_data = [
            ["PTID001", "baseline_arm_1", "", "0", "0", "", "", "dummyv1", "1", "2024-01-01", "1", "value1", "value2"],
            ["PTID002", "baseline_arm_1", "2024-01-15", "1", "2", "2024-01-20", "[01-15-2024] Record was uploaded successfully by ABC", "dummyv1", "1", "2024-01-02", "1", "value3", "value4"],
            ["PTID003", "baseline_arm_1", "", "1", "0", "", "", "dummyv1", "1", "2024-01-03", "1", "value5", "value6"],
        ]
    elif mode == "batch":
        # Generate records for specified PTIDs
        sample_data = []
        if ptids:
            for i, ptid in enumerate(ptids):
                sample_data.append([
                    ptid, "baseline_arm_1", "", "1", "0", "", "",
                    "dummyv1", "1", f"2024-01-{i+1:02d}", "1", f"value{i*2+1}", f"value{i*2+2}"
                ])
    else:  # single
        # Generate one record for the specified PTID
        sample_data = []
        if ptids:
            ptid = ptids[0]
            sample_data = [
                [ptid, "baseline_arm_1", "", "1", "0", "", "", "dummyv1", "1", "2024-01-01", "1", "value1", "value2"]
            ]
    
    # Write CSV file
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        # Write header with comment indicating report ID
        f.write('# Generated from REDCap Report ID: ' + report_id + '\n')
        f.write(','.join(f'"{col}"' for col in header) + '\n')
        
        # Write data rows
        for row in sample_data:
            f.write(','.join(f'"{str(val)}"' for val in row) + '\n')


def validate_redcap_connection() -> bool:
    """Validate REDCap API connection and credentials.
    
    Returns:
        True if connection is successful, False otherwise
    """
    # Check for required environment variables (try both REDCAP_API_KEY and REDCAP_API_TOKEN)
    redcap_api_key = os.getenv('REDCAP_API_KEY') or os.getenv('REDCAP_API_TOKEN')
    redcap_api_url = os.getenv('REDCAP_API_URL')
    nacc_report_id = os.getenv('NACC_REDCAP_REPORT_ID')
    
    if not redcap_api_key or not redcap_api_url:
        logger.warning("REDCap API credentials not found in environment variables")
        return False
    
    if not nacc_report_id:
        logger.warning("NACC_REDCAP_REPORT_ID not found in environment variables")
        return False
    
    try:
        # TODO: Make actual API call to validate connection and report access
        logger.info(f"REDCap connection validation placeholder - Report ID: {nacc_report_id}")
        return True
    except Exception as e:
        logger.error(f"REDCap connection validation failed: {e}")
        return False


def get_report_metadata() -> dict:
    """Get metadata about the REDCap report structure.
    
    Returns:
        Dictionary containing report metadata
    """
    # Get report ID from environment
    report_id = os.getenv('NACC_REDCAP_REPORT_ID', 'unknown')
    
    # TODO: Implement actual metadata fetching from REDCap
    return {
        "report_id": report_id,
        "report_name": os.getenv('NACC_REDCAP_REPORT_NAME', 'NACC Upload Report'),
        "total_records": "Unknown",
        "last_updated": "Unknown",
        "fields": [
            "ptid", "redcap_event_name", "nacc_upload_date", 
            "nacc_finalization_status", "packet_finalization_date", 
            "nacc_upload_status_complete", "upload_notes"
        ],
        "discontinued_fields": [
            "nacc_upload_by_initals", "reupload_status", "nacc_finalization_status_2"
        ]
    }
