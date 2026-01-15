"""Tests for REDCap fetcher module."""

import pytest
from pathlib import Path
from demo.redcap_data.fetcher import fetch_redcap_report


class TestFetchRedcapReport:
    """Test REDCap report fetching."""
    
    def test_fetch_all_mode(self):
        """Test fetching all records."""
        result = fetch_redcap_report([])
        
        assert result.exists()
        assert result.suffix == ".csv"
        assert "REDCAP_NACC_UPLOAD_REPORT" in result.name
    
    def test_fetch_single_record(self):
        """Test fetching single record."""
        result = fetch_redcap_report(["TEST001"])
        
        assert result.exists()
        assert result.suffix == ".csv"
    
    def test_fetch_multiple_records(self):
        """Test fetching multiple records."""
        result = fetch_redcap_report(["TEST001", "TEST002", "TEST003"])
        
        assert result.exists()
        assert result.suffix == ".csv"
    
    def test_output_filename_format(self):
        """Test output filename follows convention."""
        result = fetch_redcap_report([])
        
        # Should match: REDCAP_NACC_UPLOAD_REPORT_{DDMMYYYY}_{HHMMSS}.csv
        assert "REDCAP_NACC_UPLOAD_REPORT_" in result.name
        assert result.suffix == ".csv"
    
    def test_creates_data_directory(self):
        """Test that data directory is created."""
        result = fetch_redcap_report([])
        
        assert result.parent.exists()
        assert result.parent.name == "data"
