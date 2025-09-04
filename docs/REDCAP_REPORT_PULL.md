# REDCap Report Pull Documentation

This document describes the REDCap report that is fetched by the UDSv4 NACC Uploader.

## Report Overview

The uploader fetches a specific REDCap report containing participant data ready for upload to the NACC Data Platform via Flywheel.

## Report Configuration

### Report Name
`NACC Upload Report` (or similar - to be configured in REDCap)

### Report Fields

The report should include the following fields:

#### Core Identifier Fields
- `ptid` - Participant ID (primary identifier)
- `redcap_event_name` - REDCap event name for the record

#### Upload Status Fields
- `nacc_upload_by_initals` - Initials of person who performed the upload
- `nacc_upload_date` - Date when upload was completed (YYYY-MM-DD format)
- `nacc_upload_status_complete` - Flag indicating upload completion (0/1)

#### Finalization Status Fields  
- `nacc_finalization_status` - First finalization status flag (0/1)
- `nacc_finalization_status_2` - Second finalization status flag (0/1)
- `packet_finalization_date` - Date when packet was finalized
- `reupload_status` - Flag indicating if reupload is needed (0/1)

#### Additional Data Fields
- Any additional fields required for Flywheel upload (e.g., visit data, assessments, etc.)

## Data Processing Logic

### Initial Upload Detection
A record is considered ready for initial upload if ALL of the following fields are empty:
- `nacc_upload_by_initals`
- `nacc_upload_date`
- `packet_finalization_date`
- `nacc_upload_status_complete`

### Reupload Detection
A record is considered ready for reupload if it's NOT an initial upload AND ANY of the following conditions are true:
- `nacc_finalization_status = 0`
- `nacc_finalization_status_2 = 0`
- `reupload_status = 1`

## Filtering Options

The fetcher supports three filtering modes:

### All Mode (default)
- Fetches the complete report
- No additional filtering applied
- Used for bulk operations

### Batch Mode
- Fetches the complete report
- Filters results to only include specified PTIDs
- Used for uploading specific participants

### Single Mode
- Fetches the complete report
- Filters results to include only one specified PTID
- Used for individual participant uploads

## API Configuration

### Environment Variables Required
```
REDCAP_API_KEY=your_redcap_api_key
REDCAP_API_URL=https://your.redcap.instance.com/api/
```

### API Endpoint
The fetcher uses the REDCap API export endpoint:
```
POST {REDCAP_API_URL}
```

### API Parameters
```
token={REDCAP_API_KEY}
content=report
format=csv
report_id={report_id}
rawOrLabel=raw
rawOrLabelHeaders=raw
exportCheckboxLabel=false
```

## Output File Format

### Filename Convention
`REDCAP_NACC_UPLOAD_REPORT_{DDMMYYYY}_{HHMMSS}.csv`

Where:
- `DDMMYYYY` = Date in DD/MM/YYYY format
- `HHMMSS` = Time in HH:MM:SS format

### CSV Structure
The output CSV contains all report fields with proper header row and quoted values.

## Example Report Data

```csv
"ptid","redcap_event_name","nacc_upload_by_initals","nacc_upload_date","nacc_finalization_status","reupload_status","nacc_finalization_status_2","packet_finalization_date","nacc_upload_status_complete","module","adcid","visitdate","visitnum","variable1","variable2"
"PTID001","baseline_arm_1","","","0","0","0","","","dummyv1","1","2024-01-01","1","value1","value2"
"PTID002","baseline_arm_1","ABC","2024-01-15","1","0","1","2024-01-20","1","dummyv1","1","2024-01-02","1","value3","value4"
"PTID003","baseline_arm_1","","","0","1","0","","","dummyv1","1","2024-01-03","1","value5","value6"
```

## Implementation Status

### Current Status: Development Placeholder
The REDCap fetcher currently generates placeholder data for development and testing purposes.

### Future Implementation
- REDCap API integration
- Actual report fetching
- Error handling for API failures
- Connection validation

## Testing

For testing purposes, the fetcher creates sample data based on the specified mode:

- **All mode**: Generates 3+ sample records with various upload states
- **Batch mode**: Generates one record per specified PTID
- **Single mode**: Generates one record for the specified PTID

## Security Considerations

- REDCap API keys should be stored securely in environment variables
- The `.env` file is included in `.gitignore` to prevent accidental commits
- API keys should have appropriate permissions (export only for this report)
- Consider using REDCap's IP restriction features for additional security
