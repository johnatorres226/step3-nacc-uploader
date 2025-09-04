#!/usr/bin/env python3
"""Test script for UDSv4 NACC Uploader functionality."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test that core modules can be imported."""
    print("Testing imports...")
    
    try:
        from redcap_data import fetcher, data_processor, uploader
        print("✓ REDCap data modules imported successfully")
    except ImportError as e:
        print(f"✗ REDCap data import failed: {e}")
        return False
    
    try:
        from demo.logger import logger
        print("✓ Logger module imported successfully")
    except ImportError as e:
        print(f"✗ Logger import failed: {e}")
        return False
    
    try:
        from cli import cli
        print("✓ CLI module imported successfully")
    except ImportError as e:
        print(f"✗ CLI import failed: {e}")
        return False
    
    return True

def test_fetcher():
    """Test the REDCap fetcher with placeholder data."""
    print("\nTesting REDCap fetcher...")
    
    try:
        from redcap_data.fetcher import fetch_redcap_report
        
        # Test 'all' mode
        result_path = fetch_redcap_report('all')
        print(f"✓ All mode test successful: {result_path}")
        
        # Test 'single' mode
        result_path = fetch_redcap_report('single', ['TEST001'])
        print(f"✓ Single mode test successful: {result_path}")
        
        # Test 'batch' mode
        result_path = fetch_redcap_report('batch', ['TEST001', 'TEST002'])
        print(f"✓ Batch mode test successful: {result_path}")
        
        return True
        
    except Exception as e:
        print(f"✗ Fetcher test failed: {e}")
        return False

def test_data_processor():
    """Test the data processor functionality."""
    print("\nTesting data processor...")
    
    try:
        from redcap_data.data_processor import validate_input_data
        from redcap_data.fetcher import fetch_redcap_report
        
        # Create test data
        test_csv = fetch_redcap_report('all')
        
        # Validate the test data
        validation_result = validate_input_data(test_csv)
        print(f"✓ Data validation test: {validation_result['valid']}")
        
        if not validation_result['valid']:
            print(f"  Errors: {validation_result['errors']}")
        
        return validation_result['valid']
        
    except Exception as e:
        print(f"✗ Data processor test failed: {e}")
        return False

def test_logger():
    """Test the logging functionality."""
    print("\nTesting logger...")
    
    try:
        from demo.logger.logger import setup_logging, log_operation
        
        # Set up logging
        output_dir = Path.cwd() / "test_logs"
        output_dir.mkdir(exist_ok=True)
        
        logger = setup_logging("TEST", output_dir)
        print("✓ Logger setup successful")
        
        # Test logging operation
        log_operation(logger, "test_operation", {"test": True})
        print("✓ Log operation successful")
        
        # Clean up test logs
        import shutil
        shutil.rmtree(output_dir, ignore_errors=True)
        
        return True
        
    except Exception as e:
        print(f"✗ Logger test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("UDSv4 NACC Uploader - Test Suite")
    print("=" * 40)
    
    tests = [
        test_imports,
        test_fetcher,
        test_data_processor,
        test_logger
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        if test_func():
            passed += 1
        print()
    
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The system is ready for use.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
