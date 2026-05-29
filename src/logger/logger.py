"""Logger module for UDSv4 NACC Uploader.

This module provides centralized logging functionality for CLI operations
with comprehensive tracking and backup capabilities.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import os

# Tracks the active run's logs directory; set by setup_logging()
_active_logs_dir: Optional[Path] = None


def get_timestamp() -> str:
    """Get current timestamp in HHMMSS format."""
    return datetime.now().strftime("%H%M%S")


def get_datestamp() -> str:
    """Get current date in DDMMMYYYY format."""
    return datetime.now().strftime("%d%b%Y").upper()


def setup_logging(initials: str, output_dir: Path, log_level: str = "INFO") -> logging.Logger:
    """Set up comprehensive logging for the upload process.
    
    Args:
        initials: User initials for log identification
        output_dir: Directory for log files
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        
    Returns:
        Configured logger instance
    """
    global _active_logs_dir

    # Create logs directory
    logs_dir = output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    _active_logs_dir = logs_dir
    
    # Set up main logger
    logger = logging.getLogger("udsv4_nacc_uploader")
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)
    
    # File handler for detailed logs
    datestamp = get_datestamp()
    timestamp = get_timestamp()
    log_filename = f"UPLOAD_LOG_{initials}_{datestamp}_{timestamp}.log"
    file_handler = logging.FileHandler(logs_dir / log_filename, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)
    
    # Initialize comprehensive log
    comprehensive_log_path = logs_dir / "UPLOAD_LOG_COMPREHENSIVE.json"
    _initialize_comprehensive_log(comprehensive_log_path, initials)
    
    # Set up backup log directory
    backup_log_path = os.getenv('BACKUP_LOG_PATH')
    if backup_log_path:
        backup_dir = Path(backup_log_path)
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_comprehensive_path = backup_dir / "UPLOAD_LOG_COMPREHENSIVE.json"
        _initialize_comprehensive_log(backup_comprehensive_path, initials)
    
    logger.info(f"Logging initialized for user: {initials}")
    logger.info(f"Log files location: {logs_dir}")
    
    return logger


def log_operation(logger: logging.Logger, operation: str, data: Dict[str, Any], 
                 level: str = "INFO") -> None:
    """Log an operation to both regular logs and comprehensive JSON log.
    
    Args:
        logger: Logger instance
        operation: Operation name/type
        data: Operation data to log
        level: Log level for the operation
    """
    # Log to regular logger
    log_level = getattr(logging, level.upper())
    logger.log(log_level, f"Operation: {operation} - Data: {data}")
    
    # Log to comprehensive JSON log
    _update_comprehensive_log(operation, data)


def _initialize_comprehensive_log(log_path: Path, initials: str) -> None:
    """Initialize the comprehensive JSON log file."""
    if not log_path.exists():
        initial_log = {
            "metadata": {
                "created": datetime.now().isoformat(),
                "version": "1.0",
                "user_initials": initials,
                "log_type": "comprehensive_upload_tracker"
            },
            "operations": []
        }
        
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(initial_log, f, indent=2, ensure_ascii=False)


def _update_comprehensive_log(operation: str, data: Dict[str, Any]) -> None:
    """Update the comprehensive JSON log with new operation."""
    # Write to the active run's logs dir when available, else root logs/
    logs_dir = _active_logs_dir if _active_logs_dir is not None else Path.cwd() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    comprehensive_log_path = logs_dir / "UPLOAD_LOG_COMPREHENSIVE.json"
    
    _append_to_json_log(comprehensive_log_path, operation, data)
    
    # Update backup log if configured
    backup_log_path = os.getenv('BACKUP_LOG_PATH')
    if backup_log_path:
        backup_comprehensive_path = Path(backup_log_path) / "UPLOAD_LOG_COMPREHENSIVE.json"
        _append_to_json_log(backup_comprehensive_path, operation, data)


def _append_to_json_log(log_path: Path, operation: str, data: Dict[str, Any]) -> None:
    """Append operation to JSON log file."""
    try:
        # Read existing log
        if log_path.exists():
            with open(log_path, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
        else:
            log_data = {
                "metadata": {
                    "created": datetime.now().isoformat(),
                    "version": "1.0",
                    "log_type": "comprehensive_upload_tracker"
                },
                "operations": []
            }
        
        # Add new operation
        operation_entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "data": data
        }
        log_data["operations"].append(operation_entry)
        
        # Update metadata
        log_data["metadata"]["last_updated"] = datetime.now().isoformat()
        log_data["metadata"]["total_operations"] = len(log_data["operations"])
        
        # Write back to file
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        # Use basic logging to avoid recursion
        print(f"Error updating comprehensive log: {e}")


def get_log_summary(logs_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Get summary of recent log activity.
    
    Args:
        logs_dir: Optional logs directory path
        
    Returns:
        Dictionary with log summary information
    """
    if not logs_dir:
        logs_dir = Path.cwd() / "logs"
    
    summary = {
        "logs_directory": str(logs_dir),
        "directory_exists": logs_dir.exists(),
        "log_files": [],
        "comprehensive_log": None,
        "recent_operations": []
    }
    
    try:
        if logs_dir.exists():
            # List log files
            for log_file in logs_dir.glob("*.log"):
                summary["log_files"].append({
                    "name": log_file.name,
                    "size": log_file.stat().st_size,
                    "modified": log_file.stat().st_mtime
                })
            
            # Check comprehensive log
            comprehensive_log_path = logs_dir / "UPLOAD_LOG_COMPREHENSIVE.json"
            if comprehensive_log_path.exists():
                with open(comprehensive_log_path, 'r', encoding='utf-8') as f:
                    log_data = json.load(f)
                
                summary["comprehensive_log"] = {
                    "exists": True,
                    "total_operations": len(log_data.get("operations", [])),
                    "created": log_data.get("metadata", {}).get("created"),
                    "last_updated": log_data.get("metadata", {}).get("last_updated")
                }
                
                # Get recent operations (last 10)
                operations = log_data.get("operations", [])
                summary["recent_operations"] = operations[-10:] if operations else []
        
    except Exception as e:
        summary["error"] = str(e)
    
    return summary


def archive_old_logs(logs_dir: Path, days_to_keep: int = 30) -> Dict[str, Any]:
    """Archive old log files to prevent disk space issues.
    
    Args:
        logs_dir: Directory containing log files
        days_to_keep: Number of days of logs to keep
        
    Returns:
        Dictionary with archive operation results
    """
    import time
    from datetime import timedelta
    
    cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
    
    archive_result = {
        "archived_files": [],
        "errors": [],
        "total_archived": 0
    }
    
    try:
        if not logs_dir.exists():
            return archive_result
        
        # Create archive directory
        archive_dir = logs_dir / "archive"
        archive_dir.mkdir(exist_ok=True)
        
        # Process log files
        for log_file in logs_dir.glob("*.log"):
            if log_file.stat().st_mtime < cutoff_time:
                try:
                    archive_path = archive_dir / log_file.name
                    log_file.rename(archive_path)
                    archive_result["archived_files"].append({
                        "original": str(log_file),
                        "archived": str(archive_path)
                    })
                    archive_result["total_archived"] += 1
                except Exception as e:
                    archive_result["errors"].append(f"Failed to archive {log_file}: {e}")
        
    except Exception as e:
        archive_result["errors"].append(f"Archive operation failed: {e}")
    
    return archive_result


class UploadLoggerContext:
    """Context manager for upload operations with automatic logging."""
    
    def __init__(self, initials: str, operation: str, output_dir: Path):
        self.initials = initials
        self.operation = operation
        self.output_dir = output_dir
        self.logger = None
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        self.logger = setup_logging(self.initials, self.output_dir)
        log_operation(self.logger, f"{self.operation}_start", {
            "initials": self.initials,
            "start_time": self.start_time.isoformat()
        })
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time and self.logger:
            end_time = datetime.now()
            duration = (end_time - self.start_time).total_seconds()
            
            if exc_type is None:
                log_operation(self.logger, f"{self.operation}_complete", {
                    "success": True,
                    "duration_seconds": duration,
                    "end_time": end_time.isoformat()
                })
            else:
                log_operation(self.logger, f"{self.operation}_error", {
                    "success": False,
                    "error": str(exc_val),
                    "duration_seconds": duration,
                    "end_time": end_time.isoformat()
                }, level="ERROR")
