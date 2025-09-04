# UDSv4 NACC Uploader - Usage Examples

This document provides practical examples of using the UDSv4 NACC Uploader CLI.

## Prerequisites

1. **Install and activate the environment:**
   ```cmd
   # Run the setup script
   setup_windows.bat
   
   # Or manually:
   python -m venv .venv
   .venv\Scripts\activate
   pip install -e .
   ```

2. **Configure your .env file with API keys:**
   ```
   FW_API_KEY=your_actual_flywheel_api_key
   REDCAP_API_KEY=your_redcap_api_key  
   REDCAP_API_URL=https://your.redcap.instance.com/api/
   ```

## Basic Upload Examples

### 1. Upload All Data to Sandbox (Test)

```cmd
udsv4-nacc-uploader upload flywheel --initials ABC --adcid 42 --pipeline sandbox
```

**What this does:**
- Fetches all records from REDCap report
- Processes data for upload readiness  
- Uploads to Flywheel sandbox (test environment)
- Creates comprehensive logs with initials "ABC"

### 2. Production Upload with Test Run First

```cmd
# First, test with sandbox
udsv4-nacc-uploader upload flywheel --test --initials ABC --adcid 42 --datatype form

# If test succeeds, run production
udsv4-nacc-uploader upload flywheel --initials ABC --adcid 42 --pipeline ingest --datatype form
```

### 3. Upload Specific Participants (Batch Mode)

```cmd
udsv4-nacc-uploader upload flywheel --initials ABC --adcid 42 --pipeline sandbox --mode batch --ptid PTID001 PTID002 PTID003
```

### 4. Upload Single Participant

```cmd
udsv4-nacc-uploader upload flywheel --initials ABC --adcid 42 --pipeline sandbox --mode single --ptid PTID001
```

## Pull Operations Examples

### 5. Pull Error Reports

```cmd
# Pull errors for form data
udsv4-nacc-uploader pull-errors --adcid 42 --datatype form --pipeline sandbox --output ./reports

# Pull errors for enrollment data
udsv4-nacc-uploader pull-errors --adcid 42 --datatype enrollment --pipeline ingest --output ./reports
```

### 6. Pull Participant Identifiers

```cmd
udsv4-nacc-uploader pull-identifiers --adcid 42 --pipeline ingest --output ./reports
```

### 7. Pull QC Status

```cmd
udsv4-nacc-uploader pull-status --adcid 42 --datatype form --pipeline ingest --output ./reports
```

## Advanced Examples

### 8. Custom Output Directory

```cmd
udsv4-nacc-uploader upload flywheel --initials ABC --adcid 42 --pipeline sandbox --output "C:\NACC_Uploads\2024-08-12"
```

### 9. Enrollment Data Upload

```cmd
udsv4-nacc-uploader upload flywheel --initials ABC --adcid 42 --pipeline ingest --datatype enrollment
```

### 10. Full Help for Any Command

```cmd
# General help
udsv4-nacc-uploader --help

# Specific command help
udsv4-nacc-uploader upload --help
udsv4-nacc-uploader pull-errors --help
```

## Workflow Examples

### Daily Upload Workflow

```cmd
# 1. First check for errors from previous day
udsv4-nacc-uploader pull-errors --adcid 42 --datatype form --pipeline ingest --output ./daily_reports

# 2. Pull current status
udsv4-nacc-uploader pull-status --adcid 42 --datatype form --pipeline ingest --output ./daily_reports

# 3. Test upload with sandbox
udsv4-nacc-uploader upload flywheel --test --initials ABC --adcid 42

# 4. If test passes, run production upload
udsv4-nacc-uploader upload flywheel --initials ABC --adcid 42 --pipeline ingest
```

### Reupload Specific Participants

```cmd
# After fixing data issues for specific participants
udsv4-nacc-uploader upload flywheel --initials ABC --adcid 42 --pipeline ingest --mode batch --ptid PTID001 PTID002
```

### Troubleshooting Workflow

```cmd
# 1. Check recent errors
udsv4-nacc-uploader pull-errors --adcid 42 --output ./troubleshooting

# 2. Check identifiers  
udsv4-nacc-uploader pull-identifiers --adcid 42 --output ./troubleshooting

# 3. Test upload for specific problematic participant
udsv4-nacc-uploader upload flywheel --test --initials ABC --adcid 42 --mode single --ptid PROBLEMATIC_PTID
```

## Output Locations

### Upload Outputs
- **Data folder:** `NACC_UPLOAD_{DDMMYYYY}_{HHMMSS}/`
- **Flywheel CSV:** In data folder  
- **REDCap JSON:** `./redcap-upload-ready-data/NACC_UPLOAD_{DDMMYYYY}_{HHMMSS}_status.json`
- **Logs:** `./logs/` directory

### Pull Command Outputs
- **Errors:** `NACC_ERRORS_{DDMMYYYY}_{HHMMSS}/`
- **Identifiers:** `NACC_IDENTIFIERS_{DDMMYYYY}_{HHMMSS}/`
- **Status:** `NACC_STATUS_{DDMMYYYY}_{HHMMSS}/`

## Troubleshooting Common Issues

### Missing API Key
```cmd
# Error: FW_API_KEY environment variable not found
# Solution: Check your .env file
```

### Invalid ADCID
```cmd
# Error: Center lookup failed
# Solution: Verify your ADCID is correct and you have access
```

### Connection Issues
```cmd
# Error: Failed to connect to Flywheel
# Solution: Check your API key is valid and not expired
```

### Empty Report
```cmd
# Error: No records found for upload
# Solution: Check REDCap report configuration and data availability
```

## Best Practices

1. **Always test first:** Use `--test` flag before production uploads
2. **Use meaningful initials:** Include your initials for audit trails
3. **Check outputs:** Review log files and output directories
4. **Regular pulls:** Run pull commands regularly to monitor status
5. **Backup logs:** Set `BACKUP_LOG_PATH` in .env for log backups

## Future Features (In Development)

```cmd
# These will be available once REDCap integration is complete:

# REDCap status upload
udsv4-nacc-uploader upload redcap --initials ABC

# End-to-end upload (Flywheel + REDCap)  
udsv4-nacc-uploader upload full-upload --initials ABC --adcid 42
```
