"""UDSv4 NACC Uploader - Windows-first tool for uploading data to NACC Data Platform.

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
    from redcap_data.fetcher import fetch_redcap_report
    from redcap_data.data_processor import process_data
    from redcap_data.uploader import upload_to_flywheel, upload_to_redcap
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

- upload TARGET
    - Uploads data to Flywheel, REDCap, or both (full-upload).
    - TARGET choices: 'flywheel', 'redcap', 'full-upload'.
    - Key options:
        - --initials (required): User initials for logging and REDCap variables.
        - --mode: 'all' (default), 'batch', or 'single'. When 'batch' or 'single', use --ptid.
        - --ptid: One or more PTIDs (multiple allowed). Required for batch/single modes.
        - --pipeline: 'sandbox' (default) or 'ingest'. Forced to 'sandbox' if --test used.
        - --adcid: Integer ADRC site ID (required for Flywheel uploads).
        - --datatype: 'dicom', 'enrollment', or 'form' (default: form).
        - --data-flywheel: Path to a CSV to use for Flywheel upload (optional override).
        - --data-redcap: Path to a JSON to use for REDCap upload (optional override).
        - --output: Output directory for logs and data files (defaults to cwd).
        - --test: Flag for test runs (uses sandbox and skips REDCap upload).

- pull-errors
    - Pulls pipeline file errors and writes results to a time-stamped output folder.
    - Key options:
        - --adcid (required): Center ADCID (integer).
        - --datatype: 'dicom', 'enrollment', or 'form' (default: form).
        - --pipeline: 'ingest' or 'sandbox' (default: sandbox).
        - --studyid: Study identifier (default: 'adrc').
        - --output: Output directory (defaults to cwd).

- pull-identifiers
    - Pulls enrollment identifiers and saves them to a time-stamped output folder.
    - Key options:
        - --adcid (required): Center ADCID (integer).
        - --pipeline: 'ingest' or 'sandbox' (default: sandbox).
        - --studyid: Study identifier (default: 'adrc').
        - --output: Output directory (defaults to cwd).

- pull-status
    - Pulls QC status information and saves output to a time-stamped folder.
    - Key options:
        - --adcid (required): Center ADCID (integer).
        - --datatype: 'dicom', 'enrollment', or 'form' (default: form).
        - --pipeline: 'ingest' or 'sandbox' (default: sandbox).
        - --studyid: Study identifier (default: 'adrc').
        - --output: Output directory (defaults to cwd).

- packet-finalization
    - Placeholder command for packet finalization workflow.
    - Key options:
        - --output: Output directory (defaults to cwd).

Other notes:
    - main() checks for the FW_API_KEY environment variable and prints a warning if missing.
    - Most commands create a dated/time-stamped subfolder under the provided --output path
        and preserve the calling working directory when invoking demo functionality.

This comment block replaces the shorter placeholder and documents the available commands
and important flags to help users and maintainers quickly understand `cli.py`.
"""


def get_timestamp():
    """Get current timestamp in HHMMSS format."""
    return datetime.now().strftime("%H%M%S")


def get_datestamp():
    """Get current date in DDMMYYYY format."""
    return datetime.now().strftime("%d%m%Y")


@click.group()
@click.version_option(version=CLI_VERSION, prog_name="udsv4-nacc-uploader")
@click.pass_context
def cli(ctx):
    """UDSv4 NACC Uploader - Windows-first tool for NACC Data Platform operations.
    
    This tool handles data fetching from REDCap, processing, and uploading to Flywheel
    with comprehensive logging and status tracking.
    
    Examples:
        # Upload all data to Flywheel sandbox
        udsv4-nacc-uploader upload flywheel --initials ABC --pipeline sandbox --adcid SITE123
        
        # Test run with specific PTIDs
        udsv4-nacc-uploader upload flywheel --test --initials ABC --mode batch --ptid PTID001 PTID002
        
        # Pull error reports
        udsv4-nacc-uploader pull-errors --adcid 0 --output ./reports
    """
    ctx.ensure_object(dict)


@cli.command()
@click.argument('target', type=click.Choice(['flywheel', 'redcap', 'full-upload']))
@click.option('--initials', required=True, help='User initials for logging and REDCap variables')
@click.option('--mode', type=click.Choice(['all', 'batch', 'single']), default='all', 
              help='Upload mode (default: all)')
@click.option('--ptid', multiple=True, help='PTID(s) for batch/single mode')
@click.option('--pipeline', type=click.Choice(['sandbox', 'ingest']), default='sandbox',
              help='Flywheel pipeline type (default: sandbox)')
@click.option('--adcid', type=int, help='ADRC site ID (required for Flywheel uploads)')
@click.option('--datatype', type=click.Choice(['dicom', 'enrollment', 'form']), default='form',
              help='Data type (default: form)')
@click.option('--data-flywheel', type=click.Path(), help='Path to CSV for Flywheel upload')
@click.option('--data-redcap', type=click.Path(), help='Path to JSON for REDCap upload')
@click.option('--output', type=click.Path(), default=str(DEFAULT_OUTPUT_DIR),
              help='Output directory for logs and data files')
@click.option('--test', is_flag=True, help='Test run - uses Flywheel sandbox, no REDCap upload')
@click.pass_context
def upload(ctx, target, initials, mode, ptid, pipeline, adcid, datatype, 
           data_flywheel, data_redcap, output, test):
    """Upload data to Flywheel and/or REDCap.
    
    TARGET can be 'flywheel', 'redcap', or 'full-upload' for both.
    
    Examples:
        # Flywheel upload (all mode, default)
        udsv4-nacc-uploader upload flywheel --initials ABC --pipeline sandbox --adcid SITE123
        
        # REDCap upload (all mode, default)
        udsv4-nacc-uploader upload redcap --initials ABC
        
        # Test run with specific PTIDs
        udsv4-nacc-uploader upload flywheel --test --initials ABC --mode batch --ptid PTID001 PTID002
    """
    # Validate arguments
    if target in ['flywheel', 'full-upload'] and not adcid:
        click.echo("Error: --adcid is required for Flywheel uploads", err=True)
        sys.exit(1)
        
    if mode in ['batch', 'single'] and not ptid:
        click.echo(f"Error: --ptid is required for mode '{mode}'", err=True)
        sys.exit(1)
        
    if mode == 'single' and len(ptid) != 1:
        click.echo("Error: --mode single requires exactly one PTID", err=True)
        sys.exit(1)
        
    if test and target == 'redcap':
        click.echo("Warning: --test flag is not applicable to REDCap uploads", err=True)
    
    # Force sandbox for test runs
    if test:
        pipeline = 'sandbox'
    
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Setup logging
    try:
        logger = setup_logging(initials, output_path)
        log_operation(logger, "upload_start", {
            "target": target,
            "mode": mode,
            "ptids": list(ptid) if ptid else [],
            "pipeline": pipeline,
            "adcid": adcid,
            "datatype": datatype,
            "test_run": test
        })
    except NameError:
        click.echo("Warning: Logging module not yet implemented", err=True)
        logger = None
    
    try:
        if target in ['flywheel', 'full-upload']:
            # Fetch data from REDCap
            click.echo(f"Fetching REDCap data (mode: {mode})...")
            try:
                raw_data_path = fetch_redcap_report(mode, list(ptid) if ptid else [])
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
            click.echo(f"Uploading to Flywheel ({'TEST MODE' if test else 'LIVE MODE'})...")
            try:
                upload_result = upload_to_flywheel(
                    csv_path, adcid, datatype, pipeline, test
                )
                click.echo(f"Flywheel upload completed: {upload_result}")
            except NameError:
                click.echo("Error: Flywheel uploader not yet implemented", err=True)
                sys.exit(1)
        
        if target in ['redcap', 'full-upload'] and not test:
            # Upload to REDCap (not for test runs)
            click.echo("Uploading status to REDCap...")
            try:
                redcap_result = upload_to_redcap(json_path if 'json_path' in locals() else data_redcap)
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


@cli.command('pull-errors')
@click.option('--adcid', type=int, required=True, help='Center ADCID')
@click.option('--datatype', type=click.Choice(['dicom', 'enrollment', 'form']), 
              default='form', help='Data type (default: form)')
@click.option('--pipeline', type=click.Choice(['ingest', 'sandbox']), 
              default='sandbox', help='Pipeline type (default: sandbox)')
@click.option('--studyid', default='adrc', help='Study ID (default: adrc)')
@click.option('--output', type=click.Path(), default=str(DEFAULT_OUTPUT_DIR),
              help='Output directory')
def pull_errors(adcid, datatype, pipeline, studyid, output):
    """Pull pipeline file errors."""
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


@cli.command('pull-identifiers')
@click.option('--adcid', type=int, required=True, help='Center ADCID')
@click.option('--pipeline', type=click.Choice(['ingest', 'sandbox']), 
              default='sandbox', help='Pipeline type (default: sandbox)')
@click.option('--studyid', default='adrc', help='Study ID (default: adrc)')
@click.option('--output', type=click.Path(), default=str(DEFAULT_OUTPUT_DIR),
              help='Output directory')
def pull_identifiers(adcid, pipeline, studyid, output):
    """Pull enrollment identifiers."""
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


@cli.command('pull-status')
@click.option('--adcid', type=int, required=True, help='Center ADCID')
@click.option('--datatype', type=click.Choice(['dicom', 'enrollment', 'form']), 
              default='form', help='Data type (default: form)')
@click.option('--pipeline', type=click.Choice(['ingest', 'sandbox']), 
              default='sandbox', help='Pipeline type (default: sandbox)')
@click.option('--studyid', default='adrc', help='Study ID (default: adrc)')
@click.option('--output', type=click.Path(), default=str(DEFAULT_OUTPUT_DIR),
              help='Output directory')
def pull_status(adcid, datatype, pipeline, studyid, output):
    """Pull QC status information."""
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


@cli.command('packet-finalization')
@click.option('--output', type=click.Path(), default=str(DEFAULT_OUTPUT_DIR),
              help='Output directory')
def packet_finalization(output):
    """Handle packet finalization process."""
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
