# UDSv4-NU (NACC Uploader)

Windows tool for uploading UDS data to NACC via REDCap and Flywheel.

## Setup

**Requirements:** Python 3.11, Poetry

**Installation:**
```powershell
git clone <repository-url>
pip install poetry
poetry install
```

**Configuration:** Create `.env` file:
```env
FW_API_KEY=your_flywheel_api_key
REDCAP_API_TOKEN=your_redcap_token
REDCAP_API_URL=https://redcap.example.com/api/
PROJECT_ID=48
NACC_REDCAP_REPORT_ID=22552
```

## Quick Start

Upload all eligible records:
```powershell
poetry run udsv4-nu -i JDT
```

## Commands

- `-i, --initials TEXT` - Upload with defaults (ingest pipeline, form datatype)
- `--fetch` - Fetch REDCap data
- `--pull-errors` - Pull pipeline errors
- `--pull-identifiers` - Pull identifiers
- `--pull-status` - Pull QC status
- `--packet-finalization` - Lock finalized packets

**Upload options:**
- `--adcid INT` - ADRC site ID (default: PROJECT_ID)
- `--pipeline [sandbox|ingest]` - Pipeline (default: ingest)
- `--datatype [dicom|enrollment|form]` - Data type (default: form)
- `--ptid TEXT` - Record IDs (comma-separated or single; default: all)

**Examples:**
```powershell
poetry run udsv4-nu -i JDT --ptid NM0099
poetry run udsv4-nu -i JDT --pipeline sandbox --adcid 99
poetry run udsv4-nu --fetch
```

## Workflow

1. Fetch REDCap data
2. Process & validate
3. Upload to Flywheel
4. Auto-update REDCap status
5. Finalize packet (optional)

**Eligibility:** Record skipped only if `nacc_finalization_status=1` AND `nacc_upload_status_complete=2`

## Configuration Details

**REDCap Status Fields Updated:**
- `nacc_upload_status` → '2' (Uploaded)
- `nacc_upload_date` → Timestamp
- `nacc_upload_project` → Flywheel path
- `nacc_upload_pipeline` → Pipeline used
- `upload_notes` → Transaction log

**Removed Before Upload:** `redcap_event_name`, `nacc_finalization_status`, `nacc_upload_status_complete`, `packet_finalization_date`, `nacc_upload_date`

**Output Structure:**
```
NACC_UPLOAD_{DDMMYYYY}_{HHMMSS}/
  ├── NACC_UPLOAD_{DDMMYYYY}_{HHMMSS}.csv
  └── NACC_READYRECORDS_{DDMMYYYY}_{HHMMSS}.csv
```

## License

Mozilla Public License 2.0

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
