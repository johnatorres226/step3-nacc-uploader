"""UDSv4-NU (NACC Uploader) - Windows-first tool for uploading data to NACC Data Platform.

This CLI tool handles fetching REDCap reports, processing data, and uploading to
Flywheel with comprehensive logging and status tracking.

Based on code from https://github.com/naccdata/data-platform-demos
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime
import click
from dotenv import load_dotenv

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import modules
try:
    from src.redcap_data.fetcher import fetch_redcap_report
    from src.redcap_data.data_processor import process_data
    from src.redcap_data.uploader import upload_to_flywheel, upload_to_redcap, update_redcap_status
    from src.logger.logger import setup_logging, log_operation
    from src.pull_errors.src.python.pull_errors import main as pull_errors_main
    from src.pull_identifiers.src.python.pull_identifiers import main as pull_identifiers_main
    from src.pull_status.src.python.pull_status import main as pull_status_main
    from src.redcap_data.upload_checkout_processor import run_upload_checkout
except ImportError as e:
    # Modules will be created later, this is expected initially
    pass

# Load environment variables
load_dotenv()

# Global constants
CLI_VERSION = "1.0.0"
DEFAULT_OUTPUT_DIR = Path.cwd()

_TELEMETRY_DIR = Path(
    os.getenv("TELEMETRY_PATH") or str(Path(__file__).parent.parent.parent / "telemetry")
).resolve()
_TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)

"""
CLI Commands Reference

This module exposes the following top-level CLI commands via Click:

- upload
    - Runs the end-to-end upload pipeline by default.
    - Key options:
        - --initials (required): User initials for logging and REDCap variables.
        - --pipeline: 'sandbox' or 'ingest' (default: ingest).
        - --adcid (required): Integer ADRC site ID.
        - --datatype: 'dicom', 'enrollment', or 'form' (default: form).
        - --ptid: Single or comma-separated record IDs (default: all eligible records).

- fetch
    - Pulls REDCap data (report-level) and produces the final dataset for upload.
    - Output convention: REDCAP_NACC_UPLOAD_REPORT_{DDMMMYYYY}-{HHMMSS}.csv

- pull-errors
    - Pulls pipeline file errors and writes results to a time-stamped output folder.

- pull-identifiers  
    - Pulls enrollment identifiers and saves them to a time-stamped output folder.

- pull-status
    - Pulls QC status information and saves output to a time-stamped folder.

- packet-finalization
    - Handles packet finalization workflow.

All commands create time-stamped subfolders under the output directory following the convention:
NACC_{COMMAND}_{DDMMMYYYY}-{HHMMSS}/
"""


def get_timestamp():
    """Get current timestamp in HHMMSS format."""
    return datetime.now().strftime("%H%M%S")


def get_datestamp():
    """Get current date in DDMMMYYYY format."""
    return datetime.now().strftime("%d%b%Y").upper()


@click.command()
@click.version_option(version=CLI_VERSION, prog_name="udsv4-nu")
@click.option('-i', '--initials', 'initials', help='User initials - triggers upload workflow with defaults')
@click.option('--fetch', is_flag=True, help='Fetch REDCap data and produce final dataset')
@click.option('--pull-errors', is_flag=True, help='Pull pipeline file errors')
@click.option('--pull-identifiers', is_flag=True, help='Pull enrollment identifiers')
@click.option('--pull-status', is_flag=True, help='Pull QC status information')
@click.option('--packet-finalization', is_flag=True, help='Handle packet finalization process')
@click.option('--upload-checkout', is_flag=True, help='Post-upload checkout: cross-reference FW errors/status against REDCap and queue finalization updates')
@click.option('--errors-csv', type=click.Path(exists=True), help='Path to pull-errors CSV (auto-detected from latest NACC_ERRORS_* if omitted)')
@click.option('--status-csv', type=click.Path(exists=True), help='Path to pull-status CSV (auto-detected from latest NACC_STATUS_* if omitted)')
@click.option('--redcap-csv', type=click.Path(exists=True), help='Path to existing REDCap fetch CSV (for --upload-checkout; fetches fresh if omitted)')
@click.option('--pipeline', type=click.Choice(['sandbox', 'ingest']), default='ingest',
              help='Flywheel pipeline type (default: ingest)')
@click.option('--adcid', type=int, help='ADRC site ID (defaults to PROJECT_ID env var)')
@click.option('--datatype', type=click.Choice(['dicom', 'enrollment', 'form']), default='form',
              help='Data type (default: form)')
@click.option('--ptid', help='Record ID(s) - single value or comma-separated list (default: all records)')
@click.option('--output', type=click.Path(), default=str(DEFAULT_OUTPUT_DIR / 'output'),
              help='Output directory for logs and data files')
@click.pass_context
def cli(ctx, initials, fetch, pull_errors, pull_identifiers, pull_status,
        packet_finalization, upload_checkout, errors_csv, status_csv, redcap_csv,
        pipeline, adcid, datatype, ptid, output):
    """UDSv4-NU (NACC Uploader) - Windows-first tool for NACC Data Platform operations.

    This tool handles data fetching from REDCap, processing, and uploading to Flywheel
    with comprehensive logging and status tracking.

    Examples:
        # Default: upload workflow with initials (uses PROJECT_ID from .env)
        udsv4-nu -i JDT

        # Upload specific record
        udsv4-nu -i JDT --ptid NM0099

        # Upload to sandbox
        udsv4-nu -i JDT --pipeline sandbox

        # Upload multiple records
        udsv4-nu -i JDT --ptid 10001,10002,10003

        # Fetch new REDCap dataset only
        udsv4-nu --fetch

        # Packet finalization
        udsv4-nu --packet-finalization

        # Post-upload checkout (cross-reference FW results with REDCap)
        udsv4-nu --upload-checkout -i JDT --errors-csv output/NACC_ERRORS_.../errors-ingest-form-....csv --status-csv output/NACC_STATUS_.../qc-status-ingest-form-....csv
    """

    # Count how many command flags are set (excluding initials)
    commands = [fetch, pull_errors, pull_identifiers, pull_status, packet_finalization, upload_checkout]
    command_count = sum(bool(cmd) for cmd in commands)

    # If initials provided and no other command, default to upload workflow
    if initials and command_count == 0:
        # Default behavior: run upload workflow
        pass  # Will be handled below
    elif initials and upload_checkout:
        # --upload-checkout accepts -i for REDCap notes; allowed combination
        pass
    elif command_count == 0 and not initials:
        click.echo("Error: No command specified. Use -i with initials for upload, or use --fetch, --pull-*, --packet-finalization, or --upload-checkout.", err=True)
        click.echo("Run 'udsv4-nu --help' for usage information.", err=True)
        sys.exit(1)
    elif command_count > 1:
        click.echo("Error: Only one command can be specified at a time.", err=True)
        sys.exit(1)
    elif command_count > 0 and initials and not upload_checkout:
        click.echo("Error: Cannot combine -i/--initials with other commands.", err=True)
        sys.exit(1)

    # Default adcid to PROJECT_ID env var if not specified
    if not adcid:
        adcid = os.getenv('PROJECT_ID')
        if adcid:
            adcid = int(adcid)

    # Handle commands
    if upload_checkout:
        _handle_upload_checkout(
            initials=initials or "UNK",
            errors_csv_path=Path(errors_csv) if errors_csv else None,
            status_csv_path=Path(status_csv) if status_csv else None,
            redcap_csv_path=Path(redcap_csv) if redcap_csv else None,
            adcid=adcid,
            pipeline=pipeline,
            datatype=datatype,
            output=output,
        )

    elif initials:
        # Validate upload command requirements
        if not adcid:
            click.echo("Error: --adcid is required or PROJECT_ID must be set in .env", err=True)
            sys.exit(1)

        # Handle record selection logic - defaults to all records
        ptids = []
        if ptid:
            # Split by comma and strip whitespace
            ptids = [p.strip() for p in ptid.split(',')]
        # If not specified, defaults to all eligible records (empty list)

        _handle_fwu(initials, pipeline, adcid, datatype, ptids, output)

    elif fetch:
        _handle_fetch(output)

    elif pull_errors:
        if not adcid:
            click.echo("Error: --adcid is required for --pull-errors command", err=True)
            sys.exit(1)
        _handle_pull_errors(adcid, datatype, pipeline, output)

    elif pull_identifiers:
        if not adcid:
            click.echo("Error: --adcid is required for --pull-identifiers command", err=True)
            sys.exit(1)
        _handle_pull_identifiers(adcid, pipeline, output)

    elif pull_status:
        if not adcid:
            click.echo("Error: --adcid is required for --pull-status command", err=True)
            sys.exit(1)
        _handle_pull_status(adcid, datatype, pipeline, output)

    elif packet_finalization:
        _handle_packet_finalization(output)


def _handle_upload(initials, pipeline, adcid, datatype, ptids, output):
    """Handle the upload command workflow."""
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Setup logging
    try:
        logger = setup_logging(initials, output_path)
        log_operation(logger, "upload_start", {
            "ptids": ptids,
            "pipeline": pipeline,
            "adcid": adcid,
            "datatype": datatype
        })
    except NameError:
        click.echo("Warning: Logging module not yet implemented", err=True)
        logger = None
    
    try:
        # Fetch data from REDCap
        click.echo(f"Fetching REDCap data...")
        try:
            raw_data_path = fetch_redcap_report(ptids, output_path)
            click.echo(f"Data fetched: {raw_data_path}")
        except NameError:
            click.echo("Error: REDCap fetcher not yet implemented", err=True)
            sys.exit(1)
        
        # Process data
        click.echo("Processing data...")
        try:
            csv_path, json_path = process_data(raw_data_path, initials, output_path)
            click.echo(f"Data processed: CSV={csv_path}, JSON={json_path}")
        except NameError:
            click.echo("Error: Data processor not yet implemented", err=True)
            sys.exit(1)
        
        # Upload to Flywheel
        click.echo(f"Uploading to Flywheel (pipeline: {pipeline})...")
        try:
            upload_result = upload_to_flywheel(csv_path, adcid, datatype, pipeline)
            click.echo(f"Flywheel upload completed: {upload_result}")
        except NameError:
            click.echo("Error: Flywheel uploader not yet implemented", err=True)
            sys.exit(1)
        
        # Upload status to REDCap
        click.echo("Uploading status to REDCap...")
        try:
            redcap_result = upload_to_redcap(json_path)
            click.echo(f"REDCap upload completed: {redcap_result}")
        except NameError:
            click.echo("Warning: REDCap uploader not yet implemented", err=True)
        
        if logger:
            log_operation(logger, "upload_complete", {"success": True})
        click.echo("Upload operation completed successfully!")
        
    except Exception as e:
        if logger:
            log_operation(logger, "upload_error", {"error": str(e)})
        click.echo(f"Error during upload: {e}", err=True)
        sys.exit(1)


def _handle_fwu(initials, pipeline, adcid, datatype, ptids, output):
    """Handle the direct Flywheel upload command via API."""
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now()

    # Setup logging
    try:
        logger = setup_logging(initials, output_path)
        log_operation(logger, "fwu_start", {
            "ptids": ptids,
            "pipeline": pipeline,
            "adcid": adcid,
            "datatype": datatype
        })
    except NameError:
        click.echo("Warning: Logging module not yet implemented", err=True)
        logger = None
    
    try:
        # Fetch data from REDCap
        click.echo(f"Fetching REDCap data...")
        try:
            raw_data_path = fetch_redcap_report(ptids, output_path)
            click.echo(f"Data fetched: {raw_data_path}")
        except NameError:
            click.echo("Error: REDCap fetcher not yet implemented", err=True)
            sys.exit(1)
        
        # Process data
        click.echo("Processing data...")
        try:
            csv_path, json_path = process_data(raw_data_path, initials, output_path)
            import csv as _csv_mod
            with open(csv_path, newline="", encoding="utf-8") as _f:
                _records_count = sum(1 for _ in _csv_mod.reader(_f)) - 1  # subtract header
            click.echo(f"Data processed: {_records_count} records -> CSV={csv_path}")
        except NameError:
            click.echo("Error: Data processor not yet implemented", err=True)
            sys.exit(1)
        
        # Upload directly to Flywheel via API
        click.echo(f"Uploading to Flywheel via API (pipeline: {pipeline})...")
        try:
            from src.redcap_data.uploader import upload_to_flywheel_api, upload_to_redcap
            upload_result = upload_to_flywheel_api(csv_path, adcid, datatype, pipeline)
            click.echo(f"Flywheel API upload completed: {upload_result}")
            
            # Update REDCap status after successful Flywheel upload
            if upload_result.get('success'):
                click.echo("Updating REDCap status...")
                try:
                    redcap_status_result = upload_to_redcap(json_path)
                    if redcap_status_result.get('success'):
                        click.echo(f"✓ REDCap status updated: {redcap_status_result.get('records_updated', 0)} records")
                    else:
                        click.echo(f"Warning: REDCap status update failed: {redcap_status_result.get('error', 'Unknown error')}", err=True)
                except Exception as e:
                    click.echo(f"Warning: Failed to update REDCap status: {e}", err=True)
        except ImportError:
            click.echo("Error: Flywheel API uploader not available", err=True)
            sys.exit(1)
        
        if logger:
            log_operation(logger, "fwu_complete", {"success": True})
        _completed_at = datetime.now()
        with open(_TELEMETRY_DIR / f"NU_TELEMETRY_LOG_{_completed_at.strftime('%d%b%Y-%H%M%S').upper()}.json", "w", encoding="utf-8") as _f:
            json.dump({
                "run_id": _completed_at.strftime("%H%M%S"),
                "step": "nacc-uploader",
                "event_type": "NU",
                "user": initials,
                "started_at": started_at.isoformat(),
                "completed_at": _completed_at.isoformat(),
                "duration_s": round((_completed_at - started_at).total_seconds(), 1),
                "status": "success",
                "payload": {
                    "records_uploaded": _records_count,
                    "pipeline": pipeline,
                    "adcid": adcid,
                    "datatype": datatype,
                },
                "error": None,
            }, _f, indent=2, ensure_ascii=False)
        click.echo("Direct upload operation completed successfully!")

    except Exception as e:
        if logger:
            log_operation(logger, "fwu_error", {"error": str(e)})
        _completed_at = datetime.now()
        with open(_TELEMETRY_DIR / f"NU_TELEMETRY_LOG_{_completed_at.strftime('%d%b%Y-%H%M%S').upper()}.json", "w", encoding="utf-8") as _f:
            json.dump({
                "run_id": _completed_at.strftime("%H%M%S"),
                "step": "nacc-uploader",
                "event_type": "NU",
                "user": initials,
                "started_at": started_at.isoformat(),
                "completed_at": _completed_at.isoformat(),
                "duration_s": round((_completed_at - started_at).total_seconds(), 1),
                "status": "error",
                "payload": {
                    "records_uploaded": 0,
                    "pipeline": pipeline,
                    "adcid": adcid,
                    "datatype": datatype,
                },
                "error": str(e),
            }, _f, indent=2, ensure_ascii=False)
        click.echo(f"Error during direct upload: {e}", err=True)
        sys.exit(1)


def _handle_fetch(output):
    """Handle the fetch command."""
    output_path = Path(output)
    timestamp = get_timestamp()
    datestamp = get_datestamp()
    
    output_path.mkdir(parents=True, exist_ok=True)
    click.echo("Fetching REDCap data...")
    try:
        report_path = fetch_redcap_report([], output_path)
        click.echo(f"REDCap data fetched and saved to: {report_path}")
    except NameError:
        click.echo("Error: REDCap fetcher not yet implemented", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error fetching data: {e}", err=True)
        sys.exit(1)


def _handle_pull_errors(adcid, datatype, pipeline, output):
    """Handle the pull-errors command."""
    output_path = Path(output)
    timestamp = get_timestamp()
    datestamp = get_datestamp()
    subfolder = output_path / f"NACC_ERRORS_{datestamp}-{timestamp}"
    subfolder.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now()

    click.echo(f"Pulling errors for ADCID {adcid}...")
    click.echo(f"Output directory: {subfolder}")

    original_cwd = os.getcwd()
    try:
        os.chdir(str(subfolder))
        click.echo("Error pulling functionality will be implemented here")
        click.echo("This preserves the existing demo/pull_errors behavior")
        _completed_at = datetime.now()
        with open(_TELEMETRY_DIR / f"NR_TELEMETRY_LOG_{_completed_at.strftime('%d%b%Y-%H%M%S').upper()}.json", "w", encoding="utf-8") as _f:
            json.dump({
                "run_id": _completed_at.strftime("%H%M%S"),
                "step": "nacc-uploader",
                "event_type": "NR",
                "user": "",
                "started_at": started_at.isoformat(),
                "completed_at": _completed_at.isoformat(),
                "duration_s": round((_completed_at - started_at).total_seconds(), 1),
                "status": "success",
                "payload": {
                    "records_finalized": 0,
                    "pipeline": pipeline,
                    "adcid": adcid,
                    "datatype": datatype,
                    "operation": "pull_errors",
                },
                "error": None,
            }, _f, indent=2, ensure_ascii=False)
    except Exception as e:
        _completed_at = datetime.now()
        with open(_TELEMETRY_DIR / f"NR_TELEMETRY_LOG_{_completed_at.strftime('%d%b%Y-%H%M%S').upper()}.json", "w", encoding="utf-8") as _f:
            json.dump({
                "run_id": _completed_at.strftime("%H%M%S"),
                "step": "nacc-uploader",
                "event_type": "NR",
                "user": "",
                "started_at": started_at.isoformat(),
                "completed_at": _completed_at.isoformat(),
                "duration_s": round((_completed_at - started_at).total_seconds(), 1),
                "status": "error",
                "payload": {
                    "records_finalized": 0,
                    "pipeline": pipeline,
                    "adcid": adcid,
                    "datatype": datatype,
                    "operation": "pull_errors",
                },
                "error": str(e),
            }, _f, indent=2, ensure_ascii=False)
        click.echo(f"Error pulling errors: {e}", err=True)
        sys.exit(1)
    finally:
        os.chdir(original_cwd)


def _handle_pull_identifiers(adcid, pipeline, output):
    """Handle the pull-identifiers command."""
    output_path = Path(output)
    timestamp = get_timestamp()
    datestamp = get_datestamp()
    subfolder = output_path / f"NACC_IDENTIFIERS_{datestamp}-{timestamp}"
    subfolder.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now()

    click.echo(f"Pulling identifiers for ADCID {adcid}...")
    click.echo(f"Output directory: {subfolder}")

    original_cwd = os.getcwd()
    try:
        os.chdir(str(subfolder))
        click.echo("Identifier pulling functionality will be implemented here")
        click.echo("This preserves the existing demo/pull_identifiers behavior")
        _completed_at = datetime.now()
        with open(_TELEMETRY_DIR / f"NR_TELEMETRY_LOG_{_completed_at.strftime('%d%b%Y-%H%M%S').upper()}.json", "w", encoding="utf-8") as _f:
            json.dump({
                "run_id": _completed_at.strftime("%H%M%S"),
                "step": "nacc-uploader",
                "event_type": "NR",
                "user": "",
                "started_at": started_at.isoformat(),
                "completed_at": _completed_at.isoformat(),
                "duration_s": round((_completed_at - started_at).total_seconds(), 1),
                "status": "success",
                "payload": {
                    "records_finalized": 0,
                    "pipeline": pipeline,
                    "adcid": adcid,
                    "operation": "pull_identifiers",
                },
                "error": None,
            }, _f, indent=2, ensure_ascii=False)
    except Exception as e:
        _completed_at = datetime.now()
        with open(_TELEMETRY_DIR / f"NR_TELEMETRY_LOG_{_completed_at.strftime('%d%b%Y-%H%M%S').upper()}.json", "w", encoding="utf-8") as _f:
            json.dump({
                "run_id": _completed_at.strftime("%H%M%S"),
                "step": "nacc-uploader",
                "event_type": "NR",
                "user": "",
                "started_at": started_at.isoformat(),
                "completed_at": _completed_at.isoformat(),
                "duration_s": round((_completed_at - started_at).total_seconds(), 1),
                "status": "error",
                "payload": {
                    "records_finalized": 0,
                    "pipeline": pipeline,
                    "adcid": adcid,
                    "operation": "pull_identifiers",
                },
                "error": str(e),
            }, _f, indent=2, ensure_ascii=False)
        click.echo(f"Error pulling identifiers: {e}", err=True)
        sys.exit(1)
    finally:
        os.chdir(original_cwd)


def _handle_pull_status(adcid, datatype, pipeline, output):
    """Handle the pull-status command."""
    output_path = Path(output)
    timestamp = get_timestamp()
    datestamp = get_datestamp()
    subfolder = output_path / f"NACC_STATUS_{datestamp}-{timestamp}"
    subfolder.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now()

    click.echo(f"Pulling status for ADCID {adcid}...")
    click.echo(f"Output directory: {subfolder}")

    original_cwd = os.getcwd()
    try:
        os.chdir(str(subfolder))
        click.echo("Status pulling functionality will be implemented here")
        click.echo("This preserves the existing demo/pull_status behavior")
        _completed_at = datetime.now()
        with open(_TELEMETRY_DIR / f"NR_TELEMETRY_LOG_{_completed_at.strftime('%d%b%Y-%H%M%S').upper()}.json", "w", encoding="utf-8") as _f:
            json.dump({
                "run_id": _completed_at.strftime("%H%M%S"),
                "step": "nacc-uploader",
                "event_type": "NR",
                "user": "",
                "started_at": started_at.isoformat(),
                "completed_at": _completed_at.isoformat(),
                "duration_s": round((_completed_at - started_at).total_seconds(), 1),
                "status": "success",
                "payload": {
                    "records_finalized": 0,
                    "pipeline": pipeline,
                    "adcid": adcid,
                    "datatype": datatype,
                    "operation": "pull_status",
                },
                "error": None,
            }, _f, indent=2, ensure_ascii=False)
    except Exception as e:
        _completed_at = datetime.now()
        with open(_TELEMETRY_DIR / f"NR_TELEMETRY_LOG_{_completed_at.strftime('%d%b%Y-%H%M%S').upper()}.json", "w", encoding="utf-8") as _f:
            json.dump({
                "run_id": _completed_at.strftime("%H%M%S"),
                "step": "nacc-uploader",
                "event_type": "NR",
                "user": "",
                "started_at": started_at.isoformat(),
                "completed_at": _completed_at.isoformat(),
                "duration_s": round((_completed_at - started_at).total_seconds(), 1),
                "status": "error",
                "payload": {
                    "records_finalized": 0,
                    "pipeline": pipeline,
                    "adcid": adcid,
                    "datatype": datatype,
                    "operation": "pull_status",
                },
                "error": str(e),
            }, _f, indent=2, ensure_ascii=False)
        click.echo(f"Error pulling status: {e}", err=True)
        sys.exit(1)
    finally:
        os.chdir(original_cwd)


def _handle_packet_finalization(output):
    """Handle the packet-finalization command."""
    output_path = Path(output)
    timestamp = get_timestamp()
    datestamp = get_datestamp()
    subfolder = output_path / f"NACC_PACKET_FINALIZATION_{datestamp}-{timestamp}"
    subfolder.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now()

    click.echo("Running packet finalization...")
    click.echo(f"Output directory: {subfolder}")

    try:
        click.echo("Packet finalization functionality will be implemented here")
        _completed_at = datetime.now()
        with open(_TELEMETRY_DIR / f"NR_TELEMETRY_LOG_{_completed_at.strftime('%d%b%Y-%H%M%S').upper()}.json", "w", encoding="utf-8") as _f:
            json.dump({
                "run_id": _completed_at.strftime("%H%M%S"),
                "step": "nacc-uploader",
                "event_type": "NR",
                "user": "",
                "started_at": started_at.isoformat(),
                "completed_at": _completed_at.isoformat(),
                "duration_s": round((_completed_at - started_at).total_seconds(), 1),
                "status": "success",
                "payload": {
                    "records_finalized": 0,
                    "operation": "packet_finalization",
                },
                "error": None,
            }, _f, indent=2, ensure_ascii=False)
    except Exception as e:
        _completed_at = datetime.now()
        with open(_TELEMETRY_DIR / f"NR_TELEMETRY_LOG_{_completed_at.strftime('%d%b%Y-%H%M%S').upper()}.json", "w", encoding="utf-8") as _f:
            json.dump({
                "run_id": _completed_at.strftime("%H%M%S"),
                "step": "nacc-uploader",
                "event_type": "NR",
                "user": "",
                "started_at": started_at.isoformat(),
                "completed_at": _completed_at.isoformat(),
                "duration_s": round((_completed_at - started_at).total_seconds(), 1),
                "status": "error",
                "payload": {
                    "records_finalized": 0,
                    "operation": "packet_finalization",
                },
                "error": str(e),
            }, _f, indent=2, ensure_ascii=False)
        click.echo(f"Error during packet finalization: {e}", err=True)
        sys.exit(1)


def _find_latest_csv(output_path: Path, folder_prefix: str) -> Path | None:
    """Return the newest CSV inside the most recent matching output subfolder (by mtime)."""
    folders = sorted(
        output_path.glob(f"{folder_prefix}*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for folder in folders:
        csvs = sorted(folder.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        if csvs:
            return csvs[0]
    return None


def _find_latest_ready_records(output_path: Path) -> Path | None:
    """Return the most recent NACC_READYRECORDS_*.csv from any NACC_UPLOAD_* folder."""
    folders = sorted(
        [p for p in output_path.glob("NACC_UPLOAD_*") if p.is_dir() and "CHECKOUT" not in p.name],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for folder in folders:
        csvs = list(folder.glob("NACC_READYRECORDS_*.csv"))
        if csvs:
            return sorted(csvs, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    return None


def _pull_fw_errors_to_dir(client, group_id, datatype, pipeline, studyid, dest_dir: Path) -> Path:
    """Pull live errors from Flywheel and write to dest_dir/fw_errors/. Returns the CSV path."""
    from nacc_common.error_data import ERROR_HEADER_NAMES, get_error_data
    from nacc_common.pipeline import get_project
    from csv import DictWriter
    from datetime import date as _date

    project = get_project(client=client, group_id=group_id, datatype=datatype,
                          pipeline_type=pipeline, study_id=studyid)
    if not project:
        raise ValueError(f"No {pipeline} {datatype} project found for group {group_id}")

    fw_errors_dir = dest_dir / "fw_errors"
    fw_errors_dir.mkdir(parents=True, exist_ok=True)
    csv_path = fw_errors_dir / f"errors-{project.label}-{_date.today()}.csv"

    table = get_error_data(project) or []
    if table:
        # Collect all unique keys across all rows — different error types have different fields
        fieldnames = list(dict.fromkeys(k for row in table for k in row.keys()))
    else:
        fieldnames = list(ERROR_HEADER_NAMES)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = DictWriter(f, fieldnames=fieldnames, dialect="unix", extrasaction="ignore", restval="")
        writer.writeheader()
        writer.writerows(table)

    click.echo(f"  Pulled {len(table)} error rows -> {csv_path.name}")
    return csv_path


def _pull_fw_status_to_dir(client, group_id, datatype, pipeline, studyid, dest_dir: Path) -> Path:
    """Pull live QC status from Flywheel and write to dest_dir/fw_status/. Returns the CSV path."""
    from nacc_common.error_data import STATUS_HEADER_NAMES, get_status_data
    from nacc_common.pipeline import get_project
    from csv import DictWriter
    from datetime import date as _date

    project = get_project(client=client, group_id=group_id, datatype=datatype,
                          pipeline_type=pipeline, study_id=studyid)
    if not project:
        raise ValueError(f"No {pipeline} {datatype} project found for group {group_id}")

    fw_status_dir = dest_dir / "fw_status"
    fw_status_dir.mkdir(parents=True, exist_ok=True)
    csv_path = fw_status_dir / f"qc-status-{project.label}-{_date.today()}.csv"

    table = get_status_data(project) or []
    if table:
        fieldnames = list(dict.fromkeys(k for row in table for k in row.keys()))
    else:
        fieldnames = list(STATUS_HEADER_NAMES)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = DictWriter(f, fieldnames=fieldnames, dialect="unix", extrasaction="ignore", restval="")
        writer.writeheader()
        writer.writerows(table)

    click.echo(f"  Pulled {len(table)} status rows -> {csv_path.name}")
    return csv_path


def _handle_upload_checkout(initials, errors_csv_path, status_csv_path, redcap_csv_path,
                             adcid, pipeline, datatype, output):
    """Handle the --upload-checkout command.

    Pulls fresh errors and QC status from Flywheel, cross-references against
    the most recent upload's NACC_READYRECORDS snapshot, and produces:
      NACC_UPLOAD_CHECKOUT_{stamp}/
        fw_errors/errors-{label}-{date}.csv
        fw_status/qc-status-{label}-{date}.csv
        checkout-summary-{date}.csv
        NACC_UPLOAD_CHECKOUT_{stamp}_updates.json
      telemetry/NU_TELEMETRY_LOG_{stamp}.json

    --errors-csv / --status-csv override the live FW pull when provided.
    """
    import csv as csv_module

    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now()

    # Build the checkout output folder up front (fw_errors / fw_status go inside it)
    datestamp = datetime.now().strftime("%d%b%Y").upper()
    timestamp = datetime.now().strftime("%H%M%S")
    stamp = f"{datestamp}-{timestamp}"
    checkout_dir = output_path / f"NACC_UPLOAD_CHECKOUT_{stamp}"
    checkout_dir.mkdir(parents=True, exist_ok=True)

    try:
        from src.redcap_data.upload_checkout_processor import run_upload_checkout
    except ImportError:
        click.echo("Error: upload_checkout_processor module not available", err=True)
        sys.exit(1)

    # ---- Pull errors and status from Flywheel (or use overrides) ----
    if errors_csv_path and status_csv_path:
        click.echo(f"Using provided errors CSV : {errors_csv_path}")
        click.echo(f"Using provided status CSV : {status_csv_path}")
    else:
        # Require adcid for live FW pull
        if not adcid:
            adcid = os.getenv("PROJECT_ID")
            if adcid:
                adcid = int(adcid)
        if not adcid:
            click.echo("Error: --adcid is required for --upload-checkout (or set PROJECT_ID in .env)", err=True)
            sys.exit(1)

        try:
            from flywheel import Client
            from nacc_common.center_info import get_center_id, CenterError
        except ImportError:
            click.echo("Error: Flywheel SDK not available. Install with --extras flywheel or pass --errors-csv/--status-csv.", err=True)
            sys.exit(1)

        if "FW_API_KEY" not in os.environ:
            click.echo("Error: FW_API_KEY environment variable not found", err=True)
            sys.exit(1)

        client = Client(os.environ["FW_API_KEY"])
        try:
            group_id = get_center_id(client=client, adcid=str(adcid))
        except CenterError as e:
            click.echo(f"Error: Center lookup failed for adcid={adcid}: {e}", err=True)
            sys.exit(1)

        click.echo(f"Pulling fresh FW data for adcid={adcid} (group={group_id}, pipeline={pipeline})...")
        errors_csv_path = _pull_fw_errors_to_dir(client, group_id, datatype, pipeline, "adrc", checkout_dir)
        status_csv_path = _pull_fw_status_to_dir(client, group_id, datatype, pipeline, "adrc", checkout_dir)

    # ---- Load cross-reference records from the last upload's READYRECORDS ----
    redcap_records = []
    if redcap_csv_path:
        click.echo(f"Using provided REDCap CSV : {redcap_csv_path}")
        with open(redcap_csv_path, newline="", encoding="utf-8") as f:
            redcap_records = list(csv_module.DictReader(f))
        click.echo(f"Loaded {len(redcap_records)} records")
    else:
        ready_records_path = _find_latest_ready_records(output_path)
        if ready_records_path:
            click.echo(f"Cross-referencing against: {ready_records_path.parent.name}/{ready_records_path.name}")
            with open(ready_records_path, newline="", encoding="utf-8") as f:
                redcap_records = list(csv_module.DictReader(f))
            click.echo(f"Loaded {len(redcap_records)} records from upload snapshot")
        else:
            click.echo("Warning: No NACC_READYRECORDS snapshot found; cross-reference will be empty", err=True)

    # ---- Run checkout processor ----
    try:
        summary_path, updates_path, error_notes_path, stats = run_upload_checkout(
            errors_csv_path=errors_csv_path,
            status_csv_path=status_csv_path,
            redcap_records=redcap_records,
            initials=initials,
            output_dir=output_path,
        )
        click.echo(f"Checkout summary : {summary_path}")
        click.echo(f"Updates JSON     : {updates_path}")
        click.echo(f"Error notes JSON : {error_notes_path}")
        click.echo(f"  Queued for REDCap (PASS) : {stats.get('records_queued', 0)}")
        click.echo(f"  Blocked (errors)         : {stats.get('records_blocked_errors', 0)}")
        click.echo(f"  Skipped (PASS, no match) : {stats.get('records_skipped_pass', 0)}")
        click.echo(f"  Error notes to push      : {stats.get('records_error_notes', 0)}")

        # Push finalization updates (PASS records -> nacc_finalization_status=1)
        records_finalized_in_redcap = 0
        if stats.get("records_queued", 0) > 0:
            click.echo("Pushing finalization updates to REDCap...")
            try:
                result = upload_to_redcap(updates_path)
                if result.get("success"):
                    records_finalized_in_redcap = result.get("records_updated", 0)
                    click.echo(f"  Finalized: {records_finalized_in_redcap} records (nacc_finalization_status=1)")
                else:
                    click.echo(f"  Warning: finalization push failed: {result.get('error', 'unknown')}", err=True)
            except Exception as e:
                click.echo(f"  Warning: could not push finalization: {e}", err=True)

        # Push error notes (error records in NACC_READYRECORDS -> upload_notes updated)
        records_error_notes_pushed = 0
        if stats.get("records_error_notes", 0) > 0:
            click.echo("Pushing error notes to REDCap...")
            try:
                result = upload_to_redcap(error_notes_path)
                if result.get("success"):
                    records_error_notes_pushed = result.get("records_updated", 0)
                    click.echo(f"  Error notes written: {records_error_notes_pushed} records")
                else:
                    click.echo(f"  Warning: error notes push failed: {result.get('error', 'unknown')}", err=True)
            except Exception as e:
                click.echo(f"  Warning: could not push error notes: {e}", err=True)

        _completed_at = datetime.now()
        with open(_TELEMETRY_DIR / f"NR_TELEMETRY_LOG_{_completed_at.strftime('%d%b%Y-%H%M%S').upper()}.json", "w", encoding="utf-8") as _f:
            json.dump({
                "run_id": _completed_at.strftime("%H%M%S"),
                "step": "nacc-uploader",
                "event_type": "NR",
                "user": initials,
                "started_at": started_at.isoformat(),
                "completed_at": _completed_at.isoformat(),
                "duration_s": round((_completed_at - started_at).total_seconds(), 1),
                "status": "success",
                "payload": {
                    "operation": "upload_checkout",
                    "records_finalized_in_redcap": records_finalized_in_redcap,
                    "records_error_notes_pushed": records_error_notes_pushed,
                    "records_skipped_pass": stats.get("records_skipped_pass", 0),
                    "records_blocked_errors": stats.get("records_blocked_errors", 0),
                    "total_fw_finalized": stats.get("total_fw_finalized", 0),
                    "total_errors_in_fw": stats.get("total_errors", 0),
                    "pipeline": pipeline,
                    "adcid": adcid,
                },
                "error": None,
            }, _f, indent=2, ensure_ascii=False)

        click.echo("Upload checkout complete.")

    except Exception as e:
        _completed_at = datetime.now()
        with open(_TELEMETRY_DIR / f"NR_TELEMETRY_LOG_{_completed_at.strftime('%d%b%Y-%H%M%S').upper()}.json", "w", encoding="utf-8") as _f:
            json.dump({
                "run_id": _completed_at.strftime("%H%M%S"),
                "step": "nacc-uploader",
                "event_type": "NR",
                "user": initials,
                "started_at": started_at.isoformat(),
                "completed_at": _completed_at.isoformat(),
                "duration_s": round((_completed_at - started_at).total_seconds(), 1),
                "status": "error",
                "payload": {"operation": "upload_checkout", "pipeline": pipeline, "adcid": adcid},
                "error": str(e),
            }, _f, indent=2, ensure_ascii=False)
        click.echo(f"Error during upload checkout: {e}", err=True)
        sys.exit(1)


def main():
    """Main entry point for the CLI."""
    # Ensure required environment variables are available
    if not os.getenv('FW_API_KEY'):
        click.echo("Warning: FW_API_KEY environment variable not found", err=True)
        click.echo("Please set FW_API_KEY in your .env file or environment", err=True)
    
    cli(obj={})


if __name__ == '__main__':
    main()
