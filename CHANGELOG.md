# Changelog

All notable changes to the UDSv4 NACC Uploader project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.1] - 2026-06-12

### Fixed
- **`--upload-checkout` double-folder split** (#1): `run_upload_checkout` now writes
  all artifacts (checkout summary, updates JSON, error-notes JSON) into the same
  `NACC_UPLOAD_CHECKOUT_{stamp}` folder that the CLI created for FW pulls, instead
  of creating a second, differently-stamped sibling folder.
- **Silent checkout note drop** (#3): PASS records with no prior `upload_notes` now
  receive the checkout note (`[DATE] Upload checkout PASS | Processed by {initials}`)
  instead of silently omitting the `upload_notes` key from the REDCap update payload.
- **Error message always "unknown" on credential failure** (#3): CLI warning for a
  failed finalization or error-notes push now reads `result["message"]` (the key
  `upload_to_redcap` actually returns) instead of the non-existent `result["error"]`.
- **Flywheel test fixture silently broken without extras** (#5): Added module-level
  `None` sentinels (`Client`, `get_center_id`, `CenterError`, `get_project`) in
  `uploader.py` when flywheel extras are absent, so `monkeypatch.setattr` no longer
  silently no-ops and test setup failures surface immediately.
- **`test_upload_validation` never exercised app logic**: Fixed test invocation from
  the invalid `['main-command', '--upload']` to `[]`, which correctly reaches the
  no-command guard and asserts exit code 2.

### Added
- **`checkout-run-stats.json`** (#5): `--upload-checkout` now writes a
  `checkout-run-stats.json` file directly into the checkout folder alongside the
  summary CSV, so each run is self-documenting without having to open telemetry logs.

## [1.1.0] - 2026-06-11

### Added

- **Orchestration contract compliance** (pipeline-orchestrator `STEP_CONTRACT.md` v1):
  `--result-json` writes a machine-readable step result for every mode (upload,
  fetch, pull-errors, pull-identifiers, pull-status, packet-finalization,
  upload-checkout); telemetry consolidated into `src/logger/telemetry.py`
  (`RunRecorder`) and now written on failure paths with status `failure` for
  both NU and NR events.
- `--pull-errors` and `--pull-status` now perform the live Flywheel pulls
  (reusing the same helpers `--upload-checkout` uses) instead of stub output,
  so their `errors_csv` / `status_csv` artifacts are real.
- Upload runs with zero eligible records exit 0 with status `no_op` and skip
  the Flywheel upload instead of submitting an empty CSV.

### Changed

- Exit codes rationalized: usage/config errors (missing command, conflicting
  flags, missing `--adcid`/`FW_API_KEY`/SDK, failed center lookup) exit 2;
  runtime failures exit 1.

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
