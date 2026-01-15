"""UDSv4-NU (NACC Uploader) - Windows-first tool for uploading data to NACC Data Platform.

This CLI tool handles fetching REDCap reports, processing data, and uploading to
Flywheel with comprehensive logging and status tracking.

Based on code from https://github.com/naccdata/data-platform-demos
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import click
from dotenv import load_dotenv

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import modules (will be created later)
try:
    from demo.redcap_data.fetcher import fetch_redcap_report
    from demo.redcap_data.data_processor import process_data
    from demo.redcap_data.uploader import upload_to_flywheel, upload_to_redcap
    from demo.logger.logger import setup_logging, log_operation
    from demo.pull_errors.src.python.pull_errors import main as pull_errors_main
    from demo.pull_identifiers.src.python.pull_identifiers import main as pull_identifiers_main
    from demo.pull_status.src.python.pull_status import main as pull_status_main
except ImportError as e:
    # Modules will be created later, this is expected initially
    pass

# Load environment variables
load_dotenv()

# Global constants
CLI_VERSION = "1.0.0"
DEFAULT_OUTPUT_DIR = Path.cwd()

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
    - Output convention: REDCAP_NACC_UPLOAD_REPORT_{DDMMYYYY}_{HHMMSS}.csv

- pull-errors
    - Pulls pipeline file errors and writes results to a time-stamped output folder.

- pull-identifiers  
    - Pulls enrollment identifiers and saves them to a time-stamped output folder.

- pull-status
    - Pulls QC status information and saves output to a time-stamped folder.

- packet-finalization
    - Handles packet finalization workflow.

All commands create time-stamped subfolders under the output directory following the convention:
NACC_{COMMAND}_{DDMMYYYY}_{HHMMSS}/
"""


def get_timestamp():
    """Get current timestamp in HHMMSS format."""
    return datetime.now().strftime("%H%M%S")


def get_datestamp():
    """Get current date in DDMMYYYY format."""
    return datetime.now().strftime("%d%m%Y")


@click.group()
@click.version_option(version=CLI_VERSION, prog_name="udsv4-nu")
@click.pass_context
def cli(ctx):
    """UDSv4-NU (NACC Uploader) - Windows-first tool for NACC Data Platform operations.
    
    This tool handles data fetching from REDCap, processing, and uploading to Flywheel
    with comprehensive logging and status tracking.
    
    Examples:
        # Upload all eligible records to ingest pipeline (default)
        udsv4-nu --upload --initials JDT --pipeline ingest --adcid 123 --datatype form
        
        # Upload single record to sandbox
        udsv4-nu --upload --ptid 10001 --initials JDT --pipeline sandbox --adcid 123 --datatype form
        
        # Upload multiple records
        udsv4-nu --upload --ptid 10001,10002,10003 --initials JDT --pipeline ingest --adcid 123 --datatype form
        
        # Fetch new REDCap dataset
        udsv4-nu --fetch
    """
    ctx.ensure_object(dict)


@cli.command()
@click.option('--upload', is_flag=True, help='Run end-to-end upload pipeline')
@click.option('--fetch', is_flag=True, help='Fetch REDCap data and produce final dataset')
@click.option('--pull-errors', is_flag=True, help='Pull pipeline file errors')
@click.option('--pull-identifiers', is_flag=True, help='Pull enrollment identifiers')
@click.option('--pull-status', is_flag=True, help='Pull QC status information')
@click.option('--packet-finalization', is_flag=True, help='Handle packet finalization process')
@click.option('--initials', required=False, help='User initials for logging and REDCap variables (required for --upload)')
@click.option('--pipeline', type=click.Choice(['sandbox', 'ingest']), default='ingest',
              help='Flywheel pipeline type (default: ingest)')
@click.option('--adcid', type=int, help='ADRC site ID (required for --upload)')
@click.option('--datatype', type=click.Choice(['dicom', 'enrollment', 'form']), default='form',
              help='Data type (default: form)')
@click.option('--ptid', help='Record ID(s) - single value or comma-separated list (default: all records)')
@click.option('--output', type=click.Path(), default=str(DEFAULT_OUTPUT_DIR),
              help='Output directory for logs and data files')
@click.pass_context
def main_command(ctx, upload, fetch, pull_errors, pull_identifiers, pull_status, 
                packet_finalization, initials, pipeline, adcid, datatype, ptid, output):
    """Main command handler for UDSv4-NU operations.
    
    Examples:
        # Upload all eligible records (default)
        udsv4-nu --upload --initials JDT --pipeline ingest --adcid 123 --datatype form
        
        # Upload single record
        udsv4-nu --upload --ptid 10001 --initials JDT --pipeline sandbox --adcid 123 --datatype form
        
        # Upload multiple records
        udsv4-nu --upload --ptid 10001,10002,10003 --initials JDT --pipeline ingest --adcid 123 --datatype form
        
        # Fetch new REDCap dataset
        udsv4-nu --fetch
        
        # Check packet finalization
        udsv4-nu --packet-finalization
    """
    # Count how many command flags are set
    commands = [upload, fetch, pull_errors, pull_identifiers, pull_status, packet_finalization]
    command_count = sum(bool(cmd) for cmd in commands)
    
    if command_count == 0:
        click.echo("Error: No command specified. Use --help for available commands.", err=True)
        sys.exit(1)
    elif command_count > 1:
        click.echo("Error: Only one command can be specified at a time.", err=True)
        sys.exit(1)
    
    # Validate upload command requirements
    if upload:
        if not initials:
            click.echo("Error: --initials is required for --upload command", err=True)
            sys.exit(1)
        if not adcid:
            click.echo("Error: --adcid is required for --upload command", err=True)
            sys.exit(1)
        
        # Handle record selection logic - defaults to all records
        ptids = []
        if ptid:
            # Split by comma and strip whitespace
            ptids = [p.strip() for p in ptid.split(',')]
        # If not specified, defaults to all eligible records (empty list)
        
        _handle_upload(initials, pipeline, adcid, datatype, ptids, output)
    
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
            raw_data_path = fetch_redcap_report(ptids)
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


def _handle_fetch(output):
    """Handle the fetch command."""
    output_path = Path(output)
    timestamp = get_timestamp()
    datestamp = get_datestamp()
    
    click.echo("Fetching REDCap data...")
    try:
        report_path = fetch_redcap_report([])  # Empty list means all records
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
    subfolder = output_path / f"NACC_ERRORS_{datestamp}_{timestamp}"
    subfolder.mkdir(parents=True, exist_ok=True)
    
    click.echo(f"Pulling errors for ADCID {adcid}...")
    click.echo(f"Output directory: {subfolder}")
    
    # Change to the subfolder and run the original pull_errors logic
    original_cwd = os.getcwd()
    try:
        os.chdir(str(subfolder))
        # This would call the existing pull_errors functionality
        # For now, we'll create a placeholder
        click.echo("Error pulling functionality will be implemented here")
        click.echo("This preserves the existing demo/pull_errors behavior")
    except Exception as e:
        click.echo(f"Error pulling errors: {e}", err=True)
        sys.exit(1)
    finally:
        os.chdir(original_cwd)


def _handle_pull_identifiers(adcid, pipeline, output):
    """Handle the pull-identifiers command."""
    output_path = Path(output)
    timestamp = get_timestamp()
    datestamp = get_datestamp()
    subfolder = output_path / f"NACC_IDENTIFIERS_{datestamp}_{timestamp}"
    subfolder.mkdir(parents=True, exist_ok=True)
    
    click.echo(f"Pulling identifiers for ADCID {adcid}...")
    click.echo(f"Output directory: {subfolder}")
    
    # Change to the subfolder and run the original pull_identifiers logic
    original_cwd = os.getcwd()
    try:
        os.chdir(str(subfolder))
        # This would call the existing pull_identifiers functionality
        click.echo("Identifier pulling functionality will be implemented here")
        click.echo("This preserves the existing demo/pull_identifiers behavior")
    except Exception as e:
        click.echo(f"Error pulling identifiers: {e}", err=True)
        sys.exit(1)
    finally:
        os.chdir(original_cwd)


def _handle_pull_status(adcid, datatype, pipeline, output):
    """Handle the pull-status command."""
    output_path = Path(output)
    timestamp = get_timestamp()
    datestamp = get_datestamp()
    subfolder = output_path / f"NACC_STATUS_{datestamp}_{timestamp}"
    subfolder.mkdir(parents=True, exist_ok=True)
    
    click.echo(f"Pulling status for ADCID {adcid}...")
    click.echo(f"Output directory: {subfolder}")
    
    # Change to the subfolder and run the original pull_status logic
    original_cwd = os.getcwd()
    try:
        os.chdir(str(subfolder))
        # This would call the existing pull_status functionality
        click.echo("Status pulling functionality will be implemented here")
        click.echo("This preserves the existing demo/pull_status behavior")
    except Exception as e:
        click.echo(f"Error pulling status: {e}", err=True)
        sys.exit(1)
    finally:
        os.chdir(original_cwd)


def _handle_packet_finalization(output):
    """Handle the packet-finalization command."""
    output_path = Path(output)
    timestamp = get_timestamp()
    datestamp = get_datestamp()
    subfolder = output_path / f"NACC_PACKET_FINALIZATION_{datestamp}_{timestamp}"
    subfolder.mkdir(parents=True, exist_ok=True)
    
    click.echo("Running packet finalization...")
    click.echo(f"Output directory: {subfolder}")
    
    # Placeholder for packet finalization logic
    click.echo("Packet finalization functionality will be implemented here")

def main():
    """Main entry point for the CLI."""
    # Ensure required environment variables are available
    if not os.getenv('FW_API_KEY'):
        click.echo("Warning: FW_API_KEY environment variable not found", err=True)
        click.echo("Please set FW_API_KEY in your .env file or environment", err=True)
    
    cli()


if __name__ == '__main__':
    main()
