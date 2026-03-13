"""Uploader module for UDSv4 NACC Uploader.

This module handles uploading processed data to Flywheel and REDCap.
"""

import os
import sys
import json
import requests
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

# Add the project root to Python path for demo imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from nacc_common.center_info import get_center_id, CenterError
    from flywheel import Client
    from nacc_common.pipeline import get_project
    FLYWHEEL_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Flywheel dependencies not available: {e}")
    FLYWHEEL_AVAILABLE = False

logger = logging.getLogger(__name__)


def upload_to_flywheel(csv_path: Path, adcid: int, datatype: str = "form", 
                      pipeline: str = "ingest") -> Dict[str, Any]:
    """Upload processed CSV data to Flywheel.
    
    Args:
        csv_path: Path to the processed CSV file
        adcid: ADRC site ID
        datatype: Data type (dicom, enrollment, form)
        pipeline: Pipeline type (sandbox, ingest)
        
    Returns:
        Dictionary with upload results
        
    Raises:
        ConnectionError: If Flywheel connection fails
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If upload parameters are invalid
    """
    if not FLYWHEEL_AVAILABLE:
        raise ImportError("Flywheel dependencies not available")
    
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    if not os.path.getsize(csv_path) > 0:
        raise ValueError(f"CSV file is empty: {csv_path}")
    
    # Get API key from environment
    if "FW_API_KEY" not in os.environ:
        raise ConnectionError("FW_API_KEY environment variable not found")
    
    logger.info(f"Starting Flywheel upload")
    logger.info(f"Parameters: adcid={adcid}, datatype={datatype}, pipeline={pipeline}")
    
    try:
        # Create Flywheel client
        client = Client(os.environ["FW_API_KEY"])
        if not client:
            raise ConnectionError("Failed to connect to Flywheel")
        
        # Get center group ID
        try:
            group_id = get_center_id(client=client, adcid=str(adcid))
        except CenterError as error:
            raise ValueError(f"Center lookup failed: {error}")
        
        logger.info(f"Group ID for ADCID {adcid}: {group_id}")
        
        # Get upload project
        upload_project = get_project(
            client=client,
            group_id=group_id,
            datatype=datatype,
            pipeline_type=pipeline,
            study_id="adrc"  # Default study ID
        )
        
        if not upload_project:
            raise ValueError(f"No {pipeline} {datatype} project found for center: {group_id}")
        
        logger.info(f"Using project: {upload_project.group}/{upload_project.label}")
        
        # Perform upload
        logger.info(f"Uploading file: {csv_path}")
        response = upload_project.upload_file(str(csv_path))
        
        upload_result = {
            "success": True,
            "file_path": str(csv_path),
            "project": f"{upload_project.group}/{upload_project.label}",
            "file_size": response[0]["size"] if response else "unknown",
            "pipeline": pipeline
        }
        
        logger.info(f"Upload completed successfully: {response[0]['size'] if response else 'unknown'} bytes")
        return upload_result
        
    except Exception as e:
        logger.error(f"Flywheel upload failed: {e}")
        raise


def upload_to_flywheel_api(csv_path: Path, adcid: int, datatype: str = "form", 
                           pipeline: str = "ingest") -> Dict[str, Any]:
    """Upload data to Flywheel via direct API call (JSON payload preferred, CSV fallback).
    
    This function attempts to send the data as JSON directly via API. If that fails,
    it falls back to CSV file upload.
    
    Args:
        csv_path: Path to the processed CSV file
        adcid: ADRC site ID
        datatype: Data type (dicom, enrollment, form)
        pipeline: Pipeline type (sandbox, ingest)
        
    Returns:
        Dictionary with upload results
        
    Raises:
        ConnectionError: If Flywheel connection fails
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If upload parameters are invalid
    """
    if not FLYWHEEL_AVAILABLE:
        raise ImportError("Flywheel dependencies not available")
    
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    if not os.path.getsize(csv_path) > 0:
        raise ValueError(f"CSV file is empty: {csv_path}")
    
    # Get API key from environment
    if "FW_API_KEY" not in os.environ:
        raise ConnectionError("FW_API_KEY environment variable not found")
    
    logger.info(f"Starting Flywheel API upload")
    logger.info(f"Parameters: adcid={adcid}, datatype={datatype}, pipeline={pipeline}")
    
    try:
        # Create Flywheel client
        client = Client(os.environ["FW_API_KEY"])
        if not client:
            raise ConnectionError("Failed to connect to Flywheel")
        
        # Get center group ID
        try:
            group_id = get_center_id(client=client, adcid=str(adcid))
        except CenterError as error:
            raise ValueError(f"Center lookup failed: {error}")
        
        logger.info(f"Group ID for ADCID {adcid}: {group_id}")
        
        # Get upload project
        upload_project = get_project(
            client=client,
            group_id=group_id,
            datatype=datatype,
            pipeline_type=pipeline,
            study_id="adrc"  # Default study ID
        )
        
        if not upload_project:
            raise ValueError(f"No {pipeline} {datatype} project found for center: {group_id}")
        
        logger.info(f"Using project: {upload_project.group}/{upload_project.label}")
        
        # Try JSON payload first
        try:
            logger.info("Attempting JSON payload upload via API...")
            import pandas as pd
            import json as json_lib
            
            # Read CSV and convert to JSON
            df = pd.read_csv(csv_path)
            json_data = df.to_dict(orient='records')
            
            # Try to upload as JSON (this may not be supported by all Flywheel projects)
            # Note: This is a conceptual approach - actual API endpoint may differ
            logger.info(f"Converted {len(json_data)} records to JSON format")
            
            # For now, fall back to file upload as Flywheel primarily expects files
            # Future: investigate if Flywheel has a data ingestion API endpoint
            raise NotImplementedError("JSON API endpoint not yet implemented")
            
        except (NotImplementedError, Exception) as json_error:
            logger.info(f"JSON upload not available ({json_error}), falling back to CSV file upload")
            
            # Fallback: Upload CSV file
            logger.info(f"Uploading CSV file: {csv_path}")
            response = upload_project.upload_file(str(csv_path))
            
            upload_result = {
                "success": True,
                "method": "file_upload_csv",
                "file_path": str(csv_path),
                "project": f"{upload_project.group}/{upload_project.label}",
                "file_size": response[0]["size"] if response else "unknown",
                "pipeline": pipeline
            }
            
            logger.info(f"CSV upload completed successfully: {response[0]['size'] if response else 'unknown'} bytes")
            return upload_result
        
    except Exception as e:
        logger.error(f"Flywheel API upload failed: {e}")
        raise


def upload_to_redcap(json_path: Path) -> Dict[str, Any]:
    """Upload status updates to REDCap.
    
    Args:
        json_path: Path to the JSON file with REDCap updates
        
    Returns:
        Dictionary with upload results
        
    Raises:
        FileNotFoundError: If JSON file doesn't exist
        ConnectionError: If REDCap API connection fails
        ValueError: If JSON data is invalid
    """
    if not json_path or not Path(json_path).exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")
    
    logger.info(f"Starting REDCap status upload from: {json_path}")
    
    try:
        # Read JSON data
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        records = json_data.get("records", [])
        if not records:
            logger.warning("No records found in JSON file")
            return {"success": True, "records_updated": 0, "message": "No records to update"}
        
        logger.info(f"Found {len(records)} records to update")
        
        # Get REDCap credentials
        redcap_api_token = os.getenv('REDCAP_API_TOKEN') or os.getenv('REDCAP_API_KEY')
        redcap_api_url = os.getenv('REDCAP_API_URL')
        
        if not redcap_api_token or not redcap_api_url:
            logger.warning("REDCap credentials not found - skipping status update")
            return {
                "success": False,
                "message": "REDCap credentials not configured",
                "records_updated": 0
            }
        
        # Prepare API request to import records
        data = {
            'token': redcap_api_token,
            'content': 'record',
            'format': 'json',
            'type': 'flat',
            'overwriteBehavior': 'normal',
            'data': json.dumps(records),
            'returnContent': 'count',
            'returnFormat': 'json'
        }
        
        # Send update to REDCap
        logger.info(f"Sending status update to REDCap for {len(records)} records")
        response = requests.post(redcap_api_url, data=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"REDCap status update successful: {result}")
            return {
                "success": True,
                "records_updated": result.get('count', len(records)),
                "json_path": str(json_path),
                "message": "Status updated successfully"
            }
        else:
            logger.error(f"REDCap status update failed: {response.status_code} - {response.text}")
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text}",
                "records_updated": 0
            }
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON file: {e}")
        raise ValueError(f"Invalid JSON file: {e}")
    except Exception as e:
        logger.error(f"REDCap upload failed: {e}")
        raise


def _validate_redcap_connection() -> bool:
    """Validate REDCap API connection and credentials.
    
    Returns:
        True if connection is valid, False otherwise
    """
    # Check for required environment variables (try both REDCAP_API_KEY and REDCAP_API_TOKEN)
    redcap_api_key = os.getenv('REDCAP_API_KEY') or os.getenv('REDCAP_API_TOKEN')
    redcap_api_url = os.getenv('REDCAP_API_URL')
    
    if not redcap_api_key or not redcap_api_url:
        logger.warning("REDCap API credentials not found in environment variables")
        logger.info("Set REDCAP_API_KEY (or REDCAP_API_TOKEN) and REDCAP_API_URL in your .env file")
        return False
    
    # TODO: Implement actual REDCap API validation
    logger.info("REDCap connection validation placeholder - returning True")
    return True


def validate_flywheel_connection(adcid: int) -> Dict[str, Any]:
    """Validate Flywheel connection and center access.
    
    Args:
        adcid: ADRC site ID to validate access for
        
    Returns:
        Dictionary with validation results
    """
    validation_result = {
        "valid": False,
        "errors": [],
        "adcid": adcid,
        "group_id": None,
        "available_projects": []
    }
    
    if not FLYWHEEL_AVAILABLE:
        validation_result["errors"].append("Flywheel dependencies not available")
        return validation_result
    
    try:
        # Check API key
        if "FW_API_KEY" not in os.environ:
            validation_result["errors"].append("FW_API_KEY environment variable not found")
            return validation_result
        
        # Create client
        client = Client(os.environ["FW_API_KEY"])
        if not client:
            validation_result["errors"].append("Failed to connect to Flywheel")
            return validation_result
        
        # Validate center access
        try:
            group_id = get_center_id(client=client, adcid=str(adcid))
            validation_result["group_id"] = group_id
        except CenterError as error:
            validation_result["errors"].append(f"Center access failed: {error}")
            return validation_result
        
        # Check available projects
        try:
            for datatype in ["form", "enrollment", "dicom"]:
                for pipeline in ["sandbox", "ingest"]:
                    try:
                        project = get_project(
                            client=client,
                            group_id=group_id,
                            datatype=datatype,
                            pipeline_type=pipeline,
                            study_id="adrc"
                        )
                        if project:
                            validation_result["available_projects"].append({
                                "datatype": datatype,
                                "pipeline": pipeline,
                                "project_label": project.label
                            })
                    except Exception:
                        # Project not available, continue
                        pass
        except Exception as e:
            validation_result["errors"].append(f"Project enumeration failed: {e}")
        
        validation_result["valid"] = len(validation_result["errors"]) == 0
        logger.info(f"Flywheel validation completed: {validation_result}")
        
    except Exception as e:
        validation_result["errors"].append(f"Validation error: {e}")
        logger.error(f"Flywheel validation failed: {e}")
    
    return validation_result


def get_upload_summary(csv_path: Path, json_path: Optional[Path] = None) -> Dict[str, Any]:
    """Get summary information about files ready for upload.
    
    Args:
        csv_path: Path to Flywheel CSV file
        json_path: Optional path to REDCap JSON file
        
    Returns:
        Dictionary with upload summary
    """
    summary = {
        "flywheel_csv": {
            "path": str(csv_path),
            "exists": csv_path.exists(),
            "size": csv_path.stat().st_size if csv_path.exists() else 0,
            "record_count": 0
        },
        "redcap_json": {
            "path": str(json_path) if json_path else None,
            "exists": json_path.exists() if json_path else False,
            "size": json_path.stat().st_size if json_path and json_path.exists() else 0,
            "record_count": 0
        }
    }
    
    try:
        # Count CSV records
        if csv_path.exists():
            import csv as csv_module
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv_module.reader(f)
                next(reader, None)  # Skip header
                summary["flywheel_csv"]["record_count"] = sum(1 for _ in reader)
        
        # Count JSON records
        if json_path and json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
                summary["redcap_json"]["record_count"] = len(json_data.get("records", []))
                
    except Exception as e:
        logger.warning(f"Error getting upload summary: {e}")
    
    return summary


def update_redcap_status(ptids: List[str], adcid: int, upload_result: Dict[str, Any]) -> Dict[str, Any]:
    """Update REDCap status for records after successful Flywheel upload.
    
    This function updates the NACC upload status fields in REDCap to reflect that
    records have been successfully uploaded to Flywheel.
    
    Args:
        ptids: List of participant IDs (record IDs) that were uploaded
        adcid: ADRC site ID
        upload_result: Result dictionary from Flywheel upload containing success status
        
    Returns:
        Dictionary with status update results
        
    Raises:
        ConnectionError: If REDCap API connection fails
        ValueError: If parameters are invalid
    """
    logger.info(f"Updating REDCap status for {len(ptids)} records")
    
    # Get REDCap credentials from environment
    redcap_api_token = os.getenv('REDCAP_API_TOKEN') or os.getenv('REDCAP_API_KEY')
    redcap_api_url = os.getenv('REDCAP_API_URL')
    
    if not redcap_api_token or not redcap_api_url:
        logger.warning("REDCap credentials not found - skipping status update")
        return {
            "success": False,
            "message": "REDCap credentials not configured",
            "records_updated": 0
        }
    
    try:
        # Prepare status update records
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        update_records = []
        
        for ptid in ptids:
            # Build REDCap import record
            # Using 'ptid' as the record identifier field (not 'record_id')
            record = {
                'ptid': ptid,
                'nacc_upload_status': '2',  # Status code for "Uploaded to Flywheel"
                'nacc_upload_date': timestamp,
                'nacc_upload_project': upload_result.get('project', ''),
                'nacc_upload_pipeline': upload_result.get('pipeline', 'ingest'),
                'nacc_upload_adcid': str(adcid)
            }
            update_records.append(record)
        
        # Prepare API request
        data = {
            'token': redcap_api_token,
            'content': 'record',
            'format': 'json',
            'type': 'flat',
            'overwriteBehavior': 'normal',
            'data': json.dumps(update_records),
            'returnContent': 'count',
            'returnFormat': 'json'
        }
        
        # Send update to REDCap
        logger.info(f"Sending status update to REDCap for {len(update_records)} records")
        response = requests.post(redcap_api_url, data=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"REDCap status update successful: {result}")
            return {
                "success": True,
                "records_updated": result.get('count', len(update_records)),
                "timestamp": timestamp,
                "message": "Status updated successfully"
            }
        else:
            logger.error(f"REDCap status update failed: {response.status_code} - {response.text}")
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text}",
                "records_updated": 0
            }
            
    except Exception as e:
        logger.error(f"Failed to update REDCap status: {e}")
        return {
            "success": False,
            "error": str(e),
            "records_updated": 0
        }

