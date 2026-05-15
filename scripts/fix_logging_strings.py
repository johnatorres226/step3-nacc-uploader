"""Fix logging statements by replacing f-strings with % formatting (manual approach)."""

from pathlib import Path
import re

def fix_file(filename):
    """Fix logging statements in a single file."""
    filepath = Path(filename)
    print(f"Processing: {filepath.name}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Define all the specific replacements (escaped properly for regex)
    replacements = [
        # uploader.py patterns
        (r'logger\.info\(f"Starting Flywheel upload"\)', r'logger.info("Starting Flywheel upload")'),
        (r'logger\.info\(f"Parameters: adcid=\{adcid\}, datatype=\{datatype\}, pipeline=\{pipeline\}"\)', 
         r'logger.info("Parameters: adcid=%s, datatype=%s, pipeline=%s", adcid, datatype, pipeline)'),
        (r'logger\.info\(f"Group ID for ADCID \{adcid\}: \{group_id\}"\)', 
         r'logger.info("Group ID for ADCID %s: %s", adcid, group_id)'),
        (r'logger\.info\(f"Using project: \{upload_project\.group\}/\{upload_project\.label\}"\)', 
         r'logger.info("Using project: %s/%s", upload_project.group, upload_project.label)'),
        (r'logger\.info\(f"Uploading file: \{csv_path\}"\)', 
         r'logger.info("Uploading file: %s", csv_path)'),
        (r'logger\.info\(f"Upload completed successfully: \{response\[0\]\[\'size\'\] if response else \'unknown\'\} bytes"\)', 
         r'logger.info("Upload completed successfully: %s bytes", response[0][\'size\'] if response else \'unknown\')'),
        (r'logger\.error\(f"Flywheel upload failed: \{e\}"\)', 
         r'logger.error("Flywheel upload failed: %s", e)'),
        (r'logger\.info\(f"Starting Flywheel API upload"\)', 
         r'logger.info("Starting Flywheel API upload")'),
        (r'logger\.info\(f"Attempting JSON payload upload via API\.\.\."\)', 
         r'logger.info("Attempting JSON payload upload via API...")'),
        (r'logger\.info\(f"Converted \{len\(json_data\)\} records to JSON format"\)',
         r'logger.info("Converted %d records to JSON format", len(json_data))'),
        (r'logger\.info\(f"JSON upload not available \(\{json_error\}\), falling back to CSV file upload"\)',
         r'logger.info("JSON upload not available (%s), falling back to CSV file upload", json_error)'),
        (r'logger\.info\(f"Uploading CSV file: \{csv_path\}"\)',
         r'logger.info("Uploading CSV file: %s", csv_path)'),
        (r'logger\.info\(f"CSV upload completed successfully: \{response\[0\]\[\'size\'\] if response else \'unknown\'\} bytes"\)',
         r'logger.info("CSV upload completed successfully: %s bytes", response[0][\'size\'] if response else \'unknown\')'),
        (r'logger\.error\(f"Flywheel API upload failed: \{e\}"\)',
         r'logger.error("Flywheel API upload failed: %s", e)'),
        (r'logger\.info\(f"Starting REDCap status upload from: \{json_path\}"\)',
         r'logger.info("Starting REDCap status upload from: %s", json_path)'),
        (r'logger\.warning\(f"No records found in JSON file"\)',
         r'logger.warning("No records found in JSON file")'),
        (r'logger\.info\(f"Found \{len\(records\)\} records to update"\)',
         r'logger.info("Found %d records to update", len(records))'),
        (r'logger\.warning\(f"REDCap credentials not found - skipping status update"\)',
         r'logger.warning("REDCap credentials not found - skipping status update")'),
        (r'logger\.info\(f"Sending status update to REDCap for \{len\(records\)\} records"\)',
         r'logger.info("Sending status update to REDCap for %d records", len(records))'),
        (r'logger\.info\(f"REDCap status update successful: \{result\}"\)',
         r'logger.info("REDCap status update successful: %s", result)'),
 (r'logger\.error\(f"REDCap status update failed: \{response\.status_code\} - \{response\.text\}"\)',
         r'logger.error("REDCap status update failed: %s - %s", response.status_code, response.text)'),
        (r'logger\.error\(f"Invalid JSON file: \{e\}"\)',
         r'logger.error("Invalid JSON file: %s", e)'),
        (r'logger\.error\(f"REDCap upload failed: \{e\}"\)',
         r'logger.error("REDCap upload failed: %s", e)'),
        (r'logger\.warning\(f"REDCap API credentials not found in environment variables"\)',
         r'logger.warning("REDCap API credentials not found in environment variables")'),
        (r'logger\.info\(f"Set REDCAP_API_KEY \(or REDCAP_API_TOKEN\) and REDCAP_API_URL in your \.env file"\)',
         r'logger.info("Set REDCAP_API_KEY (or REDCAP_API_TOKEN) and REDCAP_API_URL in your .env file")'),
        (r'logger\.info\(f"REDCap connection validation placeholder - returning True"\)',
         r'logger.info("REDCap connection validation placeholder - returning True")'),
        (r'logger\.info\(f"Flywheel validation completed: \{validation_result\}"\)',
         r'logger.info("Flywheel validation completed: %s", validation_result)'),
        (r'logger\.error\(f"Flywheel validation failed: \{e\}"\)',
         r'logger.error("Flywheel validation failed: %s", e)'),
        (r'logger\.warning\(f"Error getting upload summary: \{e\}"\)',
         r'logger.warning("Error getting upload summary: %s", e)'),
        (r'logger\.info\(f"Updating REDCap status for \{len\(ptids\)\} records"\)',
         r'logger.info("Updating REDCap status for %d records", len(ptids))'),
        (r'logger\.info\(f"Sending status update to REDCap for \{len\(update_records\)\} records"\)',
         r'logger.info("Sending status update to REDCap for %d records", len(update_records))'),
        (r'logger\.error\(f"Failed to update REDCap status: \{e\}"\)',
         r'logger.error("Failed to update REDCap status: %s", e)'),
        
        # fetcher.py patterns
        (r'logger\.info\(f"Fetching REDCap report \(ID: \{report_id\}, mode: \{mode\}\)"\)',
         r'logger.info("Fetching REDCap report (ID: %s, mode: %s)", report_id, mode)'),
        (r'logger\.info\(f"Filtering for PTIDs: \{ptids\}"\)',
         r'logger.info("Filtering for PTIDs: %s", ptids)'),
        (r'logger\.info\(f"REDCap report saved to: \{output_path\}"\)',
         r'logger.info("REDCap report saved to: %s", output_path)'),
        (r'logger\.error\(f"Failed to fetch REDCap report: \{e\}"\)',
         r'logger.error("Failed to fetch REDCap report: %s", e)'),
        (r'logger\.info\(f"Making REDCap API request for report \{report_id\}"\)',
         r'logger.info("Making REDCap API request for report %s", report_id)'),
        (r'logger\.info\(f"Fetched \{len\(all_records\)\} total records from REDCap"\)',
         r'logger.info("Fetched %d total records from REDCap", len(all_records))'),
        (r'logger\.info\(f"Filtered to \{len\(filtered_records\)\} records matching PTIDs: \{ptids\}"\)',
         r'logger.info("Filtered to %d records matching PTIDs: %s", len(filtered_records), ptids)'),
        (r'logger\.info\(f"No PTID filter applied, using all \{len\(filtered_records\)\} records"\)',
         r'logger.info("No PTID filter applied, using all %d records", len(filtered_records))'),
        (r'logger\.warning\(f"No records matched the filter criteria"\)',
         r'logger.warning("No records matched the filter criteria")'),
        (r'logger\.warning\(f"Using placeholder data - this should not be used in production"\)',
         r'logger.warning("Using placeholder data - this should not be used in production")'),
        (r'logger\.warning\(f"NACC_REDCAP_REPORT_ID not found in environment variables"\)',
         r'logger.warning("NACC_REDCAP_REPORT_ID not found in environment variables")'),
        (r'logger\.info\(f"REDCap connection validation placeholder - Report ID: \{nacc_report_id\}"\)',
         r'logger.info("REDCap connection validation placeholder - Report ID: %s", nacc_report_id)'),
        (r'logger\.error\(f"REDCap connection validation failed: \{e\}"\)',
         r'logger.error("REDCap connection validation failed: %s", e)'),
    ]
    
    # Apply all replacements
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  ✓ Updated")
    else:
        print(f"  No changes needed")

if __name__ == "__main__":
    base_dir = Path(__file__).parent.parent
    
    files = [
        base_dir / "src" / "redcap_data" / "uploader.py",
        base_dir / "src" / "redcap_data" / "fetcher.py",
    ]
    
    for file in files:
        if file.exists():
            fix_file(file)
        else:
            print(f"File not found: {file}")
    
    print("\nConversion complete!")
