# REDCap Status Form Specification

## Form: NACC Packet Finalization & Upload Tracking

### Field Definitions

#### 1. `nacc_finalization_status` - Packet Finalized?
- **Field Type**: Yes/No (yesno)
- **Values**:
  - `1` = Yes (Packet is finalized)
  - `0` = No (Packet is not finalized)

#### 2. `nacc_upload_status_complete` - Complete?
- **Field Type**: Dropdown
- **Values**:
  - `0` = Incomplete
  - `1` = Unverified
  - `2` = Complete

#### 3. `nacc_upload_date` - Date of Initial Upload
- **Field Type**: Text (date_ymd)
- **Format**: `YYYY-MM-DD`
- **Behavior**: Set ONLY on first upload, never updated afterward

#### 4. `packet_finalization_date` - Date of Finalization of Packet
- **Field Type**: Text (date_ymd)
- **Format**: `YYYY-MM-DD`
- **Behavior**: Updated by `--packet-finalization` command

#### 5. `upload_notes` - Upload Result Notes
- **Field Type**: Notes
- **Format**: `[MM-DD-YYYY] Record was uploaded successfully by {Initials}`
- **Behavior**: Append new notes (do not overwrite)

---

## Upload Eligibility Logic

### Rule: Record is SKIPPED if BOTH conditions are true:
1. `nacc_finalization_status = 1` (Packet is finalized)
2. `nacc_upload_status_complete = 2` (Form is complete)

### Eligible Scenarios:
- `nacc_finalization_status = 0` (any complete status) → **Eligible**
- `nacc_finalization_status = 1` AND `nacc_upload_status_complete = 0` → **Eligible**
- `nacc_finalization_status = 1` AND `nacc_upload_status_complete = 1` → **Eligible**

### Ineligible Scenario:
- `nacc_finalization_status = 1` AND `nacc_upload_status_complete = 2` → **SKIP** (finalized and complete)

---

## Upload Workflow

### Initial Upload (nacc_upload_date is blank)
1. Upload data to Flywheel
2. Update REDCap fields:
   - Set `nacc_upload_date` = current date (`YYYY-MM-DD`)
   - Append to `upload_notes`: `[MM-DD-YYYY] Record was uploaded successfully by {Initials}`

### Re-upload (nacc_upload_date exists)
1. Upload data to Flywheel
2. Update REDCap fields:
   - **DO NOT** update `nacc_upload_date` (preserve original date)
   - Append to `upload_notes`: `[MM-DD-YYYY] Record was uploaded successfully by {Initials}`

---

## Example Data

### Example 1: Eligible for Upload (Not Finalized)
```csv
ptid,nacc_finalization_status,nacc_upload_status_complete,nacc_upload_date,upload_notes
PTID001,0,0,"",""
```
**Action**: Upload and set initial date

### Example 2: Eligible for Re-upload
```csv
ptid,nacc_finalization_status,nacc_upload_status_complete,nacc_upload_date,upload_notes
PTID002,1,0,"2024-01-15","[01-15-2024] Record was uploaded successfully by ABC"
```
**Action**: Upload and append new note (do NOT update date)

### Example 3: Ineligible (Finalized AND Complete)
```csv
ptid,nacc_finalization_status,nacc_upload_status_complete,nacc_upload_date,upload_notes
PTID003,1,2,"2024-01-15","[01-15-2024] Record was uploaded successfully by ABC"
```
**Action**: SKIP (no upload, no updates)

### Example 4: Eligible (Finalized but Unverified)
```csv
ptid,nacc_finalization_status,nacc_upload_status_complete,nacc_upload_date,upload_notes
PTID004,1,1,"2024-01-15","[01-15-2024] Record was uploaded successfully by ABC"
```
**Action**: Upload and append new note

---

## Implementation Notes

- **Date Format for Upload**: `nacc_upload_date` uses REDCap's `date_ymd` format: `YYYY-MM-DD`
- **Date Format for Notes**: Upload notes use `MM-DD-YYYY` format for readability
- **Transaction Note Structure**: Always include brackets, message, and initials
- **Finalization**: Handled separately via `--packet-finalization` command
- **Multiple Uploads**: Records can be uploaded multiple times until finalized AND complete
