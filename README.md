# UDSv4 NACC Uploader

A Windows-first tool for uploading data to the NACC Data Platform using REDCap and Flywheel integration.

This project is adapted from the [NACC Data Platform demos](https://github.com/naccdata/data-platform-demos) and refactored for Windows environments with modern Python packaging.

## Overview

The UDSv4 NACC Uploader provides a unified command-line interface for:

1. **Fetching** data from REDCap reports
2. **Processing** data for upload-ready artifacts  
3. **Uploading** to Flywheel with comprehensive logging
4. **Updating** REDCap status variables (in development)
5. **Pulling** operational reports (errors, identifiers, status)

## Quick Start

### Prerequisites

- **Python 3.11+** installed on Windows
- **Flywheel API Key** from NACC Data Platform
- **REDCap API access** (for future features)

### Installation

1. **Clone this repository:**
   ```cmd
   git clone <repository-url>
   cd udv4-nacc-uploader
   ```

2. **Create and activate virtual environment:**
   ```cmd
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install the package:**
   ```cmd
   pip install -e .
   ```

4. **Set up environment variables:**
   Create a `.env` file in the project root:
   ```
   FW_API_KEY=your_flywheel_api_key_here
   REDCAP_API_KEY=your_redcap_api_key_here
   REDCAP_API_URL=your_redcap_api_url_here
   BACKUP_LOG_PATH=C:\path\to\backup\logs
   ```

### Basic Usage

```cmd
# Upload all data to Flywheel sandbox
udsv4-nacc-uploader upload flywheel --initials ABC --pipeline sandbox --adcid SITE123

# Test run with specific PTIDs  
udsv4-nacc-uploader upload flywheel --test --initials ABC --mode batch --ptid PTID001 PTID002

# Pull error reports
udsv4-nacc-uploader pull-errors --adcid 0 --output ./reports
```

## Commands

### Upload Commands

#### `upload flywheel`
Upload processed data to Flywheel.

**Required options:**
- `--initials`: User initials for logging
- `--adcid`: ADRC site ID
- `--pipeline`: `sandbox` (test) or `ingest` (production)

**Optional options:**
- `--mode`: `all` (default), `batch`, or `single`
- `--ptid`: PTID(s) for batch/single mode
- `--datatype`: `form` (default), `enrollment`, or `dicom`
- `--test`: Run in test mode (forces sandbox)
- `--output`: Output directory for logs

**Examples:**
```cmd
# Default: all records to sandbox
udsv4-nacc-uploader upload flywheel --initials ABC --adcid 42 --pipeline sandbox

# Specific PTIDs to production
udsv4-nacc-uploader upload flywheel --initials ABC --adcid 42 --pipeline ingest --mode batch --ptid PTID001 PTID002

# Test run
udsv4-nacc-uploader upload flywheel --test --initials ABC --adcid 42
```

#### `upload redcap` *(Coming Soon)*
Update REDCap status variables after Flywheel upload.

#### `upload full-upload` *(Coming Soon)*  
End-to-end upload to both Flywheel and REDCap.

### Pull Commands

#### `pull-errors`
Pull pipeline file errors for troubleshooting.

```cmd
udsv4-nacc-uploader pull-errors --adcid 42 --datatype form --pipeline sandbox --output ./reports
```

#### `pull-identifiers`
Pull participant identifiers from enrollment pipeline.

```cmd
udsv4-nacc-uploader pull-identifiers --adcid 42 --pipeline sandbox --output ./reports
```

#### `pull-status`
Pull QC status information.

```cmd
udsv4-nacc-uploader pull-status --adcid 42 --datatype form --pipeline sandbox --output ./reports  
```

#### `packet-finalization`
Handle packet finalization process.

```cmd
udsv4-nacc-uploader packet-finalization --output ./reports
```

## Workflow

### Data Processing Pipeline

1. **Fetch REDCap Report**
   - Pulls specific REDCap report data
   - Applies filtering based on mode (`all`, `batch`, `single`)
   - Saves as: `REDCAP_NACC_UPLOAD_REPORT_{DDMMYYYY}_{HHMMSS}.csv`

2. **Process Data**
   - Creates run-scoped folder: `NACC_UPLOAD_{DDMMYYYY}_{HHMMSS}/`
   - Identifies initial uploads vs. reuploads
   - Generates ready records snapshot
   - Creates Flywheel CSV (removes REDCap-specific columns)
   - Creates REDCap JSON for status updates

3. **Upload to Flywheel**
   - Uses existing `python-uploader` functionality
   - Supports sandbox (test) and ingest (production) pipelines
   - Provides comprehensive logging

4. **Log Operations** 
   - Maintains comprehensive JSON log: `logs/UPLOAD_LOG_COMPREHENSIVE.json`
   - Creates backup logs if `BACKUP_LOG_PATH` is configured
   - Includes initials in all log entries

### File Naming Conventions

- **Dates**: `DDMMYYYY` format
- **Times**: `HHMMSS` format  
- **Files**: Capitalize first letter, underscores for spaces
- **Folders**: `NACC_{OPERATION}_{DDMMYYYY}_{HHMMSS}`

## Configuration

### Environment Variables

Create a `.env` file with:

```
# Required for Flywheel uploads
FW_API_KEY=your_flywheel_api_key

# Required for REDCap operations (future)
REDCAP_API_KEY=your_redcap_api_key
REDCAP_API_URL=https://redcap.example.com/api/

# Optional: Backup log location
BACKUP_LOG_PATH=C:\backup\logs
```

### Finding Your Flywheel API Key

1. Login to the NACC Flywheel instance
2. Click your avatar (top right) → "Profile"  
3. Under "Flywheel Access" → "Generate API Key"
4. Set expiration date and create key
5. Copy the key value (you won't see it again)

## Development Status

### ✅ Ready Features
- Windows-first environment with `pyproject.toml` + `venv`
- CLI with all primary commands
- REDCap data fetching (placeholder implementation)
- Data processing with upload/reupload logic
- Flywheel upload integration  
- Comprehensive logging system
- Legacy pull commands (`pull-errors`, `pull-identifiers`, `pull-status`)

### 🚧 In Development
- REDCap API integration for data fetching
- REDCap status update functionality
- `full-upload` command (Flywheel + REDCap)
- Enhanced packet finalization logic

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

- Use `udsv4-nacc-uploader --help` for command overview
- Use `udsv4-nacc-uploader [command] --help` for specific command help
- Check logs in `./logs/` directory for detailed error information

## Attribution

This project is based on code from the [NACC Data Platform demos repository](https://github.com/naccdata/data-platform-demos) and maintains the same Mozilla Public License 2.0.

The original demos provide excellent examples for working with the NACC Data Platform and Flywheel systems.

## License

This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this file, You can obtain one at http://mozilla.org/MPL/2.0/.
