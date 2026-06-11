"""Tests for data processor module."""

import pytest
from pathlib import Path
from datetime import datetime
from src.redcap_data.data_processor import (
    _process_records,
    _append_transaction_note,
    validate_input_data
)


class TestProcessRecords:
    """Test record processing logic."""
    
    def test_eligible_record_not_finalized(self):
        """Test that non-finalized records are eligible."""
        records = [{
            "ptid": "TEST001",
            "redcap_event_name": "baseline_arm_1",
            "nacc_finalization_status": "0",
            "nacc_upload_status_complete": "0",
            "nacc_upload_date": "",
            "upload_notes": ""
        }]
        
        ready, updates = _process_records(records, "ABC")
        
        assert len(ready) == 1
        assert len(updates) == 1
        assert ready[0]["ptid"] == "TEST001"
    
    def test_eligible_record_finalized_incomplete(self):
        """Test that finalized but incomplete records are eligible."""
        records = [{
            "ptid": "TEST002",
            "redcap_event_name": "baseline_arm_1",
            "nacc_finalization_status": "1",
            "nacc_upload_status_complete": "0",
            "nacc_upload_date": "",
            "upload_notes": ""
        }]
        
        ready, updates = _process_records(records, "ABC")
        
        assert len(ready) == 1
        assert len(updates) == 1
    
    def test_eligible_record_finalized_unverified(self):
        """Test that finalized but unverified records are eligible."""
        records = [{
            "ptid": "TEST003",
            "redcap_event_name": "baseline_arm_1",
            "nacc_finalization_status": "1",
            "nacc_upload_status_complete": "1",
            "nacc_upload_date": "2024-01-01",
            "upload_notes": "[01-01-2024] Record was uploaded successfully by DEF"
        }]
        
        ready, updates = _process_records(records, "ABC")
        
        assert len(ready) == 1
        assert len(updates) == 1
    
    def test_skip_finalized_complete_record(self):
        """Test that finalized AND complete records are skipped."""
        records = [{
            "ptid": "TEST004",
            "redcap_event_name": "baseline_arm_1",
            "nacc_finalization_status": "1",
            "nacc_upload_status_complete": "2",
            "nacc_upload_date": "2024-01-01",
            "upload_notes": "[01-01-2024] Record was uploaded successfully by DEF"
        }]
        
        ready, updates = _process_records(records, "ABC")
        
        assert len(ready) == 0
        assert len(updates) == 0
    
    def test_initial_upload_sets_date(self):
        """Test that initial upload sets nacc_upload_date."""
        records = [{
            "ptid": "TEST005",
            "redcap_event_name": "baseline_arm_1",
            "nacc_finalization_status": "0",
            "nacc_upload_status_complete": "0",
            "nacc_upload_date": "",
            "upload_notes": ""
        }]
        
        ready, updates = _process_records(records, "ABC")
        
        assert "nacc_upload_date" in updates[0]
        assert updates[0]["nacc_upload_date"] != ""
    
    def test_reupload_preserves_date(self):
        """Test that re-uploads do not update nacc_upload_date."""
        records = [{
            "ptid": "TEST006",
            "redcap_event_name": "baseline_arm_1",
            "nacc_finalization_status": "0",
            "nacc_upload_status_complete": "0",
            "nacc_upload_date": "2024-01-01",
            "upload_notes": "[01-01-2024] Record was uploaded successfully by DEF"
        }]
        
        ready, updates = _process_records(records, "ABC")
        
        assert "nacc_upload_date" not in updates[0]
    
    def test_upload_notes_format(self):
        """Test that upload notes use correct format."""
        records = [{
            "ptid": "TEST007",
            "redcap_event_name": "baseline_arm_1",
            "nacc_finalization_status": "0",
            "nacc_upload_status_complete": "0",
            "nacc_upload_date": "",
            "upload_notes": ""
        }]
        
        ready, updates = _process_records(records, "ABC")
        
        notes = updates[0]["upload_notes"]
        # Format: [MM-DD-YYYY] Record was uploaded successfully by ABC
        assert notes.startswith("[")
        assert "] Record was uploaded successfully by ABC" in notes


class TestAppendTransactionNote:
    """Test transaction note appending."""
    
    def test_append_to_empty_notes(self):
        """Test appending to empty notes."""
        result = _append_transaction_note("", "New note")
        assert result == "New note"
    
    def test_append_to_existing_notes(self):
        """Test appending to existing notes."""
        existing = "[01-01-2024] First note"
        new = "[01-02-2024] Second note"
        result = _append_transaction_note(existing, new)
        assert result == "[01-01-2024] First note; [01-02-2024] Second note"


class TestValidateInputData:
    """Test input data validation."""
    
    def test_validate_missing_file(self):
        """Test validation with missing file."""
        result = validate_input_data(Path("nonexistent.csv"))
        assert result["valid"] is False
        assert len(result["errors"]) > 0
    
    def test_validate_required_columns(self):
        """Test validation checks for required columns."""
        # Create a temporary test CSV with missing columns
        import tempfile
        import csv
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['ptid', 'redcap_event_name'])  # Missing required columns
            writer.writerow(['TEST001', 'baseline_arm_1'])
            temp_path = Path(f.name)
        
        try:
            result = validate_input_data(temp_path)
            assert "required_columns" in result
            assert "ptid" in result["required_columns"]
            assert "nacc_finalization_status" in result["required_columns"]
            assert "nacc_upload_status_complete" in result["required_columns"]
        finally:
            temp_path.unlink()
