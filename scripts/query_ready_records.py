"""Query REDCap for ready-to-upload records.

This script queries REDCap to find records that are ready for upload to NACC.
It filters out records that are both finalized and complete.

Usage:
    poetry run python scripts/query_ready_records.py [--limit N]

The script will output PTIDs that are ready for upload.
"""

import os
import sys
import argparse
import requests
import csv
from io import StringIO
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get credentials
REDCAP_API_TOKEN = os.getenv('REDCAP_API_TOKEN') or os.getenv('REDCAP_API_KEY')
REDCAP_API_URL = os.getenv('REDCAP_API_URL')
NACC_REDCAP_REPORT_ID = os.getenv('NACC_REDCAP_REPORT_ID')


def query_ready_records(limit=None):
    """Query REDCap for ready-to-upload records.
    
    Args:
        limit: Optional limit on number of records to return
        
    Returns:
        List of PTIDs that are ready for upload
    """
    if not all([REDCAP_API_TOKEN, REDCAP_API_URL, NACC_REDCAP_REPORT_ID]):
        print("Error: Missing required environment variables", file=sys.stderr)
        print("Required: REDCAP_API_TOKEN (or REDCAP_API_KEY), REDCAP_API_URL, NACC_REDCAP_REPORT_ID", file=sys.stderr)
        sys.exit(1)

    print(f"Querying REDCap report ID: {NACC_REDCAP_REPORT_ID}")

    data = {
        'token': REDCAP_API_TOKEN,
        'content': 'report',
        'format': 'csv',
        'report_id': NACC_REDCAP_REPORT_ID,
        'rawOrLabel': 'raw',
        'rawOrLabelHeaders': 'raw',
        'exportCheckboxLabel': 'false',
        'returnFormat': 'json'
    }

    try:
        response = requests.post(REDCAP_API_URL, data=data, timeout=30)
        response.raise_for_status()
        
        # Parse CSV response
        csv_data = StringIO(response.text)
        reader = csv.DictReader(csv_data)
        records = list(reader)
        
        print(f"Total records fetched: {len(records)}")
        
        # Filter for ready-to-upload records
        # Rule: exclude if nacc_finalization_status = 1 AND nacc_upload_status_complete = 2
        ready_records = []
        
        for record in records:
            nacc_finalization_status = record.get("nacc_finalization_status", "").strip()
            nacc_upload_status_complete = record.get("nacc_upload_status_complete", "").strip()
            
            # Skip if finalized AND complete
            if nacc_finalization_status == "1" and nacc_upload_status_complete == "2":
                continue
            
            ready_records.append(record)
        
        print(f"Ready-to-upload records: {len(ready_records)}")
        
        # Apply limit if specified
        if limit and len(ready_records) > limit:
            print(f"Limiting to first {limit} records")
            ready_records = ready_records[:limit]
        
        # Extract PTIDs
        ptids = [record.get('ptid', '') for record in ready_records]
        
        return ptids
        
    except requests.exceptions.RequestException as e:
        print(f"Error querying REDCap: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Query REDCap for records ready to upload to NACC'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of records to return'
    )
    parser.add_argument(
        '--output',
        type=Path,
        help='Optional output file to save PTIDs (one per line)'
    )
    
    args = parser.parse_args()
    
    # Query records
    ptids = query_ready_records(limit=args.limit)
    
    if not ptids:
        print("\nNo records ready for upload")
        return
    
    # Display results
    print(f"\n=== Ready-to-Upload PTIDs ===")
    for i, ptid in enumerate(ptids, 1):
        print(f"{i}. {ptid}")
    
    print(f"\nCombined (comma-separated): {','.join(ptids)}")
    
    # Save to file if requested
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w') as f:
            for ptid in ptids:
                f.write(f"{ptid}\n")
        print(f"\nPTIDs saved to: {args.output}")


if __name__ == '__main__':
    main()
