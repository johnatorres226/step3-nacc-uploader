# Workflow Documentation

## End-to-End Upload Workflow

This document describes the complete upload workflow for the UDSv4 NACC Uploader.

### Overview

The uploader follows a 4-step process:
1. **Fetch** - Query REDCap for eligible records
2. **Process** - Transform data and create upload artifacts
3. **Upload** - Send data to Flywheel
4. **Update** - Update REDCap with upload status

### Workflow Steps

#### 1. Fetch Data from REDCap (`fetcher.py`)

```python
from src.redcap_data.fetcher import fetch_redcap_report

# Fetch specific records
csv_path = fetch_redcap_report(ptids=['NM0001', 'NM0002'])

# Fetch all eligible records
csv_path = fetch_redcap_report(ptids=[])
```

**Eligibility Rules:**
- Records are excluded if: `nacc_finalization_status = 1` AND `nacc_upload_status_complete = 2`
- All other records are eligible for upload

**Output:** CSV file in `data/` directory with naming convention:
`REDCAP_NACC_UPLOAD_REPORT_{DDMMYYYY}_{HHMMSS}.csv`

#### 2. Process Data (`data_processor.py`)

```python
from src.redcap_data.data_processor import process_data

csv_path, json_path = process_data(
    input_csv_path=raw_data_path,
   initials="JT",
    output_dir=Path("output")
)
```

**Processing Steps:**
- Read fetched CSV data
- Filter records using eligibility rules
- Create transaction notes with timestamp and initials
- Generate two artifacts:

**Artifact 1: Flywheel CSV** (`{DDMMYYYY}{HHMMSS}-uds.csv`)
- Removes REDCap-specific columns before upload
- Removed columns:
  - `redcap_event_name`
  - `redcap_repeat_instance`
  - `nacc_finalization_status`
  - `nacc_upload_status_complete`
  - `packet_finalization_date`
  - `nacc_upload_date`
  - `upload_notes`

**Artifact 2: REDCap Status JSON** (`NACC_UPLOAD_{DDMMYYYY}_{HHMMSS}_status.json`)
```json
{
  "metadata": {
    "created_date": "2026-03-13T13:12:29.620978",
    "total_records": 5,
    "format_version": "1.0"
  },
  "records": [
    {
      "ptid": "NM0054",
      "redcap_event_name": "udsvisit_arm_1",
      "redcap_repeat_instance": "1",
      "upload_notes": "[03-13-2026] Record was uploaded successfully by JT",
      "nacc_upload_date": "2026-03-13",
      "nacc_upload_status_complete": "2"
    }
  ]
}
```

**Field Descriptions:**
- `ptid`: Participant ID (record identifier)
- `redcap_event_name`: REDCap event name
- `redcap_repeat_instance`: Instance number for repeating events (required!)
- `upload_notes`: Transaction notes appended with `[MM-DD-YYYY] Message by INITIALS`
- `nacc_upload_date`: Date of initial upload (`YYYY-MM-DD`)
- `nacc_upload_status_complete`: Form status (`2` = Complete)

#### 3. Upload to Flywheel (`uploader.py`)

```python
from src.redcap_data.uploader import upload_to_flywheel_api

upload_result = upload_to_flywheel_api(
    csv_path=csv_path,
    adcid=48,
    datatype="form",
    pipeline="ingest"
)
```

**Upload Process:**
- Connects to Flywheel using `FW_API_KEY`
- Resolves ADCID to Flywheel group ID
- Uploads CSV file to appropriate project (e.g., `unm/ingest-form`)
- Returns upload confirmation with file size and project info

#### 4. Update REDCap Status (`uploader.py`)

```python
from src.redcap_data.uploader import upload_to_redcap

redcap_result = upload_to_redcap(json_path)
```

**Update Process:**
- Reads the status JSON generated in step 2
- Sends data to REDCap via API using `REDCAP_API_TOKEN`
- Updates the following fields for each record:
  - `upload_notes`: Appends transaction note
  - `nacc_upload_date`: Sets date (initial uploads only)
  - `nacc_upload_status_complete`: Sets to `2` (Complete)

**Important:** The `redcap_repeat_instance` field is **required** for repeating events in REDCap.

### CLI Usage

#### Complete End-to-End Upload

```powershell
# Upload 5 specific records
poetry run udsv4-nu -i JT --ptid NM0054,NM0063,NM0098,NM0101,NM0109

# Upload all eligible records
poetry run udsv4-nu -i JT

# Upload to sandbox environment
poetry run udsv4-nu -i JT --pipeline sandbox
```

#### Query Ready Records (Utility Script)

```powershell
# List all ready-to-upload records
poetry run python scripts/query_ready_records.py

# Limit to first 10
poetry run python scripts/query_ready_records.py --limit 10

# Save to file
poetry run python scripts/query_ready_records.py --output ptids.txt
```

### Environment Variables Required

```env
# REDCap Configuration
REDCAP_API_TOKEN=your_token_here
REDCAP_API_URL=https://your-redcap-url/api/
NACC_REDCAP_REPORT_ID=22552
PROJECT_ID=48

# Flywheel Configuration
FW_API_KEY=your_flywheel_key_here
```

###REDCap Field Reference

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `nacc_finalization_status` | yesno | 0=No, 1=Yes | Packet finalized? |
| `upload_notes` | notes | text | Transaction log |
| `nacc_upload_date` | date_ymd | YYYY-MM-DD | Initial upload date |
| `packet_finalization_date` | date_ymd | YYYY-MM-DD | Finalization date |
| `nacc_upload_status_complete` | dropdown | 0=Incomplete, 1=Unverified, 2=Complete | Form status |
| `redcap_repeat_instance` | number | 1, 2, 3... | Instance number (required for repeating events) |

### Success Criteria

An end-to-end upload is successful when:

1. ✓ Data fetched from REDCap (CSV created)
2. ✓ Data processed (Flywheel CSV + REDCap JSON created)
3. ✓ Data uploaded to Flywheel (confirmation received)
4. ✓ REDCap status updated (records marked complete)

### Error Handling

- **Flywheel upload fails**: REDCap status is *not* updated
- **REDCap status update fails**: Warning logged, but overall workflow continues
- **Missing `redcap_repeat_instance`**: REDCap API returns 400 error (fixed in current implementation)

### Output Files

All outputs are stored in time-stamped directories under `output/`:

```
output/
└── NACC_UPLOAD_13032026_130129/
    ├── 13032026130129-uds.csv                          # Flywheel upload file
    ├── NACC_READYRECORDS_13032026_130129.csv          # Snapshot of ready records
    └── NACC_UPLOAD_13032026_130129_status.json        # REDCap status update
```

### Logging

Comprehensive logs are stored in `output/logs/`:
- `UPLOAD_LOG_COMPREHENSIVE.json`: JSON log with all operation details
- Individual log entries include timestamps, operation type, and data payloads
