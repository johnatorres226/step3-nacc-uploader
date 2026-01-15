# Quick Setup Guide

## Poetry Installation & Setup

### 1. Install Poetry
```powershell
pip install poetry
```

### 2. Configure Poetry (Optional)
```powershell
# Use project-local .venv folder
poetry config virtualenvs.in-project true
```

### 3. Install Dependencies
```powershell
poetry install
```

**Note:** This project requires **Python 3.11** due to `nacc-common` dependency constraints.

### 4. Activate Virtual Environment
```powershell
poetry shell
```

Or run commands directly:
```powershell
poetry run udsv4-nu --help
```

## Environment Configuration

Create a `.env` file in project root:
```
FW_API_KEY=your_flywheel_api_key
REDCAP_API_KEY=your_redcap_api_key
REDCAP_API_URL=https://your-redcap-url/api/
NACC_REDCAP_REPORT_ID=your_report_id
```

## Quick Start Commands

```powershell
# Upload all records (default)
poetry run udsv4-nu --upload --initials JDT --adcid 123

# Upload specific records
poetry run udsv4-nu --upload --ptid 10001,10002 --initials JDT --adcid 123

# Fetch REDCap data
poetry run udsv4-nu --fetch

# Pull status reports
poetry run udsv4-nu --pull-status --adcid 123
```

## CLI Simplifications

- **Default behavior**: Upload all eligible records (no `--all` flag needed)
- **--ptid**: Accepts single or comma-separated values
  - Single: `--ptid 10001`
  - Multiple: `--ptid 10001,10002,10003`
- **Removed**: `--list` option (merged into `--ptid`)
