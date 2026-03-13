# UDSv4-NU (NACC Uploader)

A Windows-first tool for uploading data to the NACC Data Platform using REDCap and Flywheel integration.

## Quick Start

### Prerequisites

- **Python 3.11** (required for nacc-common compatibility)
- **Poetry** for dependency management
- **Flywheel API Key** from NACC Data Platform
- **REDCap API access**

### Installation

1. **Clone this repository:**
   ```powershell
   git clone <repository-url>
   cd udv4-nacc-uploader
   ```

2. **Install Poetry (if not already installed):**
   ```powershell
   pip install poetry
   ```

3. **Install dependencies:**
   ```powershell
   poetry install
   ```

4. **Set up environment variables:**
   Create a `.env` file in the project root:
   ```
   FW_API_KEY=your_flywheel_api_key_here
   REDCAP_API_KEY=your_redcap_api_key_here
   REDCAP_API_URL=your_redcap_api_url_here
   NACC_REDCAP_REPORT_ID=your_report_id
   ```

## CLI Usage

Run commands using Poetry:
```powershell
poetry run udsv4-nu [command] [options]
```

### Quick Upload with Defaults

**NEW: Simplified upload - just provide initials:**
```powershell
poetry run udsv4-nu -i JDT
```

This simple command:
- `-i` provides your initials
- Uses `PROJECT_ID` from `.env` as the default ADCID
- Defaults to `ingest` pipeline and `form` datatype
- Uploads all eligible records
- Updates REDCap status automatically after successful upload

### Core Commands

- `-i, --initials TEXT` - **Your initials - triggers complete upload workflow with defaults**
- `--fetch` - Fetch REDCap data and produce final dataset
- `--pull-errors` - Pull pipeline file errors
- `--pull-identifiers` - Pull enrollment identifiers
- `--pull-status` - Pull QC status information
- `--packet-finalization` - Handle packet finalization process

### Upload Options

**Required:**
- `-i, --initials TEXT` - Your initials (triggers upload)

**Optional:**
- `--adcid INT` - ADRC site ID (defaults to `PROJECT_ID` env var)
- `--pipeline ["sandbox", "ingest"]` - Pipeline (default: `ingest`)
- `--datatype ["dicom", "enrollment", "form"]` - Data type (default: `form`)
- `--ptid TEXT` - Record ID(s) - single or comma-separated (default: all records)

### Usage Examples

**✨ Default: Upload all eligible records:**
```powershell
poetry run udsv4-nu -i JDT
```

**Upload single record:**
```powershell
poetry run udsv4-nu -i JDT --ptid NM0099
```

**Upload multiple records:**
```powershell
poetry run udsv4-nu -i JDT --ptid 10001,10002,10003
```

**Upload to sandbox environment:**
```powershell
poetry run udsv4-nu -i JDT --pipeline sandbox
```

**Upload with explicit ADCID:**
```powershell
poetry run udsv4-nu -i JDT --adcid 99
```

**Fetch new REDCap dataset:**
```powershell
poetry run udsv4-nu --fetch
```

**Pull operational reports:**
```powershell
poetry run udsv4-nu --pull-errors --adcid 123
poetry run udsv4-nu --pull-identifiers --adcid 123  
poetry run udsv4-nu --pull-status --adcid 123
```

**Packet finalization (locks UDS events):**
```powershell
poetry run udsv4-nu --packet-finalization
```

## Workflow

### End-to-End Upload Pipeline

1. **Fetch** - REDCap data retrieval
2. **Process** - Data transformation and validation
3. **Upload to Flywheel** - CSV upload to NACC Data Platform
4. **Update REDCap Status** - Automatic status update in REDCap after successful upload
5. **Packet Finalization** - Lock UDS events when confirmed (separate command)

### Data Processing

- **Eligibility**: Record is eligible UNLESS (`nacc_finalization_status = 1` AND `nacc_upload_status_complete = 2`)
  - If packet is finalized (1) AND complete (2) → Record is SKIPPED
  - All other combinations → Record is eligible
- **Initial Upload**: `nacc_upload_date` is empty
- **Re-upload**: `nacc_upload_date` exists (record remains eligible until finalized AND complete)
- **Output Structure**:
  ```
  NACC_UPLOAD_{DDMMYYYY}_{HHMMSS}/
    ├── NACC_UPLOAD_{DDMMYYYY}_{HHMMSS}.csv (Flywheel)
    └── NACC_READYRECORDS_{DDMMYYYY}_{HHMMSS}.csv (snapshot)
  redcap-upload-ready-data/
    └── NACC_UPLOAD_{DDMMYYYY}_{HHMMSS}_status.json (REDCap)
  ```

### REDCap Status Fields

Updated during upload:
1. `nacc_finalization_status` - Packet Finalized? (1 = Yes, 0 = No)
2. `nacc_upload_status_complete` - Complete? (0 = Incomplete, 1 = Unverified, 2 = Complete)
3. `nacc_upload_date` - Date of initial upload only (`YYYY-MM-DD` format)
4. `upload_notes` - Append transaction: `[MM-DD-YYYY] Record was uploaded successfully by [initials]`
5. `packet_finalization_date` - Updated via `--packet-finalization` (handled separately)

**NEW: Automatic REDCap Status Updates**
After successful Flywheel upload, the following fields are automatically updated:
- `nacc_upload_status` - Set to '2' (Uploaded to Flywheel)
- `nacc_upload_date` - Timestamp of upload
- `nacc_upload_project` - Flywheel project path
- `nacc_upload_pipeline` - Pipeline used (ingest/sandbox)
- `nacc_upload_adcid` - ADRC site ID

### Packet Finalization & Locking

Once records are confirmed as finalized, UDS-related events can be locked to prevent modifications.

**See detailed documentation:** [REDCAP_LOCKING.md](REDCAP_LOCKING.md)

Key features:
- Integration with REDCap Locking API
- Locks all UDS v4 events (IVP, FVP, TFP)
- Triggered via `--packet-finalization` command
- Audit trail in comprehensive logs

## License

Mozilla Public License 2.0

### 5. Logging
- Managed by `logging.py`
- Conventions:
  - **File names**: Uppercase first letter, underscores for spaces
  - **Date**: `DDMMMYYYY`
  - **Timestamp**: `HHMMSS`
  - Comprehensive log file: `logs/UPLOAD_LOG_COMPREHENSIVE.json`
  - Backup stored in `BACKUP_LOG_PATH`

## Output Conventions

**Standalone tools outputs stored in:**
```
output/NACC_{COMMAND}_{DDMMYYYY}_{HHMMSS}/
```

Examples:
- `NACC_ERRORS_{DDMMYYYY}_{HHMMSS}/`
- `NACC_IDENTIFIERS_{DDMMYYYY}_{HHMMSS}/`
- `NACC_STATUS_{DDMMYYYY}_{HHMMSS}/`
- `NACC_PACKET_FINALIZATION_{DDMMYYYY}_{HHMMSS}/`

## Configuration

### Environment Variables

Create a `.env` file with:

```env
# Flywheel Configuration
FW_API_KEY=your_flywheel_api_key

# REDCap Configuration
REDCAP_API_TOKEN=your_redcap_api_token
REDCAP_API_URL=https://redcap.example.com/api/
PROJECT_ID=48

# REDCap Report Configuration
NACC_REDCAP_REPORT_ID=22552
NACC_REDCAP_REPORT_NAME="Export UDSv4 Records"
NACC_REDCAP_REPORT_UNIQUE_NAME="R-667TY4CTCD"

# Optional: Backup log location
BACKUP_LOG_PATH=C:\backup\logs

# Optional: REDCap Locking Configuration
REDCAP_LOCK_ON_FINALIZATION=true
REDCAP_LOCK_ALL_EVENTS=true
```

### REDCap Report Configuration

The uploader fetches a specific REDCap report using the `NACC_REDCAP_REPORT_ID`. This report should contain all participant data ready for upload.

**Important**: The following variables are automatically **removed** before uploading to Flywheel via API:
- `redcap_event_name`
- `nacc_finalization_status`
- `nacc_upload_status_complete`
- `packet_finalization_date`
- `nacc_upload_date`

These variables are used internally for processing and eligibility determination but are not included in the final upload payload.

### Finding Your Flywheel API Key

1. Login to the NACC Flywheel instance
2. Click your avatar (top right) → "Profile"
3. Under "Flywheel Access" → "Generate API Key"
4. Set expiration date and create key
5. Copy the key value (you won't see it again)

## Development Status

### ✅ Ready Features
- Windows-first environment with `pyproject.toml` + `venv`
- CLI with streamlined command structure (`udsv4-nu [options]`)
- **NEW**: Simplified `-i` shortcut for ingest-form uploads
- **NEW**: Default ADCID from `PROJECT_ID` environment variable
- **NEW**: Automatic REDCap status updates after Flywheel upload
- REDCap data fetching (placeholder implementation)
- Data processing with eligibility logic (`nacc_finalization_status`)
- Flywheel upload integration via API
- Comprehensive logging system
- Legacy pull commands (`--pull-errors`, `--pull-identifiers`, `--pull-status`)
- **NEW**: REDCap Locking API integration for packet finalization

### 🚧 In Development
- REDCap API integration for data fetching
- Full packet finalization workflow implementation
- Error handling and retry mechanisms

## Removed Features

From the original specification, these have been **removed**:
- `reupload` command ❌
- `--test` option ❌
- `--data-redcap [PATH]` ❌
- `--data-flywheel [PATH]` ❌
- All Pants/Docker references ❌

## Troubleshooting

### Common Issues

**Missing API Key:**
```
Error: FW_API_KEY environment variable not found
```
Solution: Add `FW_API_KEY=your_key` to your `.env` file.

**Connection Failed:**
```
Error: Failed to connect to Flywheel
```
Solution: Verify your API key is valid and not expired.

**Module Not Found:**
```
ImportError: No module named 'click'
```
Solution: Ensure virtual environment is activated and dependencies installed:
```cmd
.venv\Scripts\activate
pip install -e .
```

### Getting Help

- Use `udsv4-nu --help` for command overview
- Check logs in `./logs/` directory for detailed error information

## Attribution

This project is based on code from the [NACC Data Platform demos repository](https://github.com/naccdata/data-platform-demos) and maintains the same Mozilla Public License 2.0.

The original demos provide excellent examples for working with the NACC Data Platform and Flywheel systems.

The REDCap Locking API integration uses the [redcap-locking-api](https://github.com/lsgs/redcap-locking-api) external module by Luke Stevens, Murdoch Children's Research Institute.

## Documentation

- **[CHANGELOG.md](CHANGELOG.md)** - Version history and release notes
- **[REDCAP_LOCKING.md](REDCAP_LOCKING.md)** - REDCap Locking API integration guide
- **[REDCAP_STATUS_FORM.md](REDCAP_STATUS_FORM.md)** - Status field documentation
- **[SETUP.md](SETUP.md)** - Detailed setup instructions

## License

This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this file, You can obtain one at http://mozilla.org/MPL/2.0/.
