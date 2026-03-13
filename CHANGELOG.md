# Changelog

All notable changes to the UDSv4 NACC Uploader project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- REDCap status update integration: automatically update record status in REDCap after successful Flywheel upload
- REDCap locking API integration for packet finalization workflow
- Documentation for redcap-locking-api-master feature to lock UDS-related events once records are finalized
- Default site ID from PROJECT_ID environment variable
- Default pipeline set to 'ingest' and datatype to 'form'
- **Ultra-simplified CLI**: `poetry run udsv4-nu -i JDT` for complete upload workflow
  - `-i` flag now accepts initials directly (no `--initials` needed)
  - Providing initials automatically triggers upload workflow
  - No command flags needed for default upload behavior

### Changed
- Restructured project: renamed `demo/` directory to `src/`
- Moved `cli/` directory into `src/` for better organization
- CLI now uses single-command structure (removed subcommands)
- **BREAKING**: `-i` changed from `--ingest` flag to `--initials` shorthand
- **BREAKING**: Removed `--upload` and `--fwu` flags - use `-i` with initials instead
- Simplified command invocation: `udsv4-nu -i JDT` instead of `udsv4-nu --fwu --initials JDT`

### Fixed
- Flywheel upload success confirmation now properly integrated

## [0.1.0] - 2026-01-16

### Added
- Initial project structure
- REDCap data fetcher
- REDCap data processor
- Flywheel uploader functionality
- CLI interface for UDSv4 NACC uploads
- Environment-based configuration
- Comprehensive logging system
- Batch upload support
- Dry-run mode for testing
- Validation pipeline
