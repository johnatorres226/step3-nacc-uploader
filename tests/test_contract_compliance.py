"""Orchestration contract conformance (pipeline-orchestrator/docs/STEP_CONTRACT.md).

Covers --result-json for the upload and upload-checkout modes plus exit-code
rationalization (usage/config -> 2, runtime -> 1) and failure telemetry for
NU and NR events. All REDCap/Flywheel interaction is faked.
"""

import json
from pathlib import Path

import jsonschema
import pytest
from click.testing import CliRunner

from src.cli import cli as cli_module

SCHEMA = json.loads(
    (Path(__file__).parent / "fixtures" / "step_result.schema.json").read_text(encoding="utf-8")
)


@pytest.fixture
def telemetry_dir(tmp_path, monkeypatch):
    directory = tmp_path / "telemetry"
    monkeypatch.setenv("TELEMETRY_PATH", str(directory))
    return directory


@pytest.fixture
def quiet_logger(monkeypatch):
    monkeypatch.setattr(cli_module, "setup_logging", lambda *a, **k: None)
    monkeypatch.setattr(cli_module, "log_operation", lambda *a, **k: None)


def _invoke(tmp_path, args):
    result_path = tmp_path / "result.json"
    cli_result = CliRunner().invoke(
        cli_module.cli,
        [*args, "--output", str(tmp_path / "output"), "--result-json", str(result_path)],
    )
    doc = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else None
    return cli_result, doc


def _fake_upload_pipeline(tmp_path, monkeypatch, data_rows, upload_raises=None):
    def fake_fetch(ptids, output_dir):
        raw = Path(output_dir) / "REDCAP_NACC_UPLOAD_REPORT_10JUN2026-120000.csv"
        raw.write_text("ptid\n", encoding="utf-8")
        return raw

    def fake_process(raw_path, initials, output_dir, run_dir=None):
        base = Path(run_dir or output_dir)
        csv_path = base / "10JUN2026-120000-uds.csv"
        csv_path.write_text("ptid,visitdate\n" + "".join(f"P{i},2026-01-01\n" for i in range(data_rows)), encoding="utf-8")
        json_path = base / "NACC_UPLOAD_10JUN2026-120000_status.json"
        json_path.write_text("[]", encoding="utf-8")
        (base / "NACC_READYRECORDS_10JUN2026-120000.csv").write_text("ptid\n", encoding="utf-8")
        return csv_path, json_path

    calls = {"uploaded": False}

    def fake_upload_api(csv_path, adcid, datatype, pipeline):
        if upload_raises:
            raise upload_raises
        calls["uploaded"] = True
        return "ok"

    monkeypatch.setattr(cli_module, "fetch_redcap_report", fake_fetch)
    monkeypatch.setattr(cli_module, "process_data", fake_process)
    import src.redcap_data.uploader as uploader_module
    monkeypatch.setattr(uploader_module, "upload_to_flywheel_api", fake_upload_api, raising=False)
    return calls


def test_upload_success(tmp_path, monkeypatch, telemetry_dir, quiet_logger):
    calls = _fake_upload_pipeline(tmp_path, monkeypatch, data_rows=3)

    cli_result, doc = _invoke(tmp_path, ["-i", "JDT", "--adcid", "99", "--pipeline", "sandbox"])

    assert cli_result.exit_code == 0
    jsonschema.validate(doc, SCHEMA)
    assert doc["status"] == "success"
    assert doc["mode"] == "upload"
    assert doc["metrics"]["records_uploaded"] == 3
    assert calls["uploaded"]
    assert Path(doc["artifacts"]["uds_csv"]).is_file()
    assert Path(doc["artifacts"]["redcap_status_json"]).is_file()
    assert Path(doc["artifacts"]["ready_records_csv"]).is_file()
    telemetry = json.loads(next(telemetry_dir.glob("NU_TELEMETRY_LOG_*.json")).read_text(encoding="utf-8"))
    assert telemetry["status"] == "success"
    assert telemetry["payload"]["records_uploaded"] == 3


def test_upload_zero_eligible_records_is_no_op_and_skips_flywheel(
    tmp_path, monkeypatch, telemetry_dir, quiet_logger
):
    calls = _fake_upload_pipeline(tmp_path, monkeypatch, data_rows=0)

    cli_result, doc = _invoke(tmp_path, ["-i", "JDT", "--adcid", "99"])

    assert cli_result.exit_code == 0
    jsonschema.validate(doc, SCHEMA)
    assert doc["status"] == "no_op"
    assert doc["artifacts"] == {}
    assert not calls["uploaded"]


def test_upload_runtime_failure_exits_1_with_nu_failure_telemetry(
    tmp_path, monkeypatch, telemetry_dir, quiet_logger
):
    _fake_upload_pipeline(tmp_path, monkeypatch, data_rows=2, upload_raises=ConnectionError("fw down"))

    cli_result, doc = _invoke(tmp_path, ["-i", "JDT", "--adcid", "99"])

    assert cli_result.exit_code == 1
    jsonschema.validate(doc, SCHEMA)
    assert doc["status"] == "failure"
    assert doc["error"]["category"] == "network"
    telemetry = json.loads(next(telemetry_dir.glob("NU_TELEMETRY_LOG_*.json")).read_text(encoding="utf-8"))
    assert telemetry["status"] == "failure"
    assert "fw down" in telemetry["error"]


def test_no_command_is_usage_error_exit_2(tmp_path, telemetry_dir):
    cli_result = CliRunner().invoke(cli_module.cli, [])
    assert cli_result.exit_code == 2


def test_combining_initials_with_fetch_exits_2(tmp_path, telemetry_dir):
    cli_result = CliRunner().invoke(cli_module.cli, ["-i", "JDT", "--fetch"])
    assert cli_result.exit_code == 2


def test_pull_errors_without_adcid_is_config_error_exit_2(tmp_path, monkeypatch, telemetry_dir):
    monkeypatch.delenv("PROJECT_ID", raising=False)

    cli_result, doc = _invoke(tmp_path, ["--pull-errors"])

    assert cli_result.exit_code == 2
    jsonschema.validate(doc, SCHEMA)
    assert doc["mode"] == "pull-errors"
    assert doc["error"]["category"] == "config"
    telemetry = json.loads(next(telemetry_dir.glob("NR_TELEMETRY_LOG_*.json")).read_text(encoding="utf-8"))
    assert telemetry["status"] == "failure"


def test_fetch_success_reports_report_artifact(tmp_path, monkeypatch, telemetry_dir):
    def fake_fetch(ptids, output_dir):
        raw = Path(output_dir) / "REDCAP_NACC_UPLOAD_REPORT_10JUN2026-120000.csv"
        raw.write_text("ptid\n", encoding="utf-8")
        return raw

    monkeypatch.setattr(cli_module, "fetch_redcap_report", fake_fetch)

    cli_result, doc = _invoke(tmp_path, ["--fetch"])

    assert cli_result.exit_code == 0
    jsonschema.validate(doc, SCHEMA)
    assert doc["mode"] == "fetch"
    assert Path(doc["artifacts"]["redcap_report_csv"]).is_file()


def test_upload_checkout_with_explicit_csvs(tmp_path, monkeypatch, telemetry_dir):
    errors_csv = tmp_path / "errors.csv"
    status_csv = tmp_path / "status.csv"
    redcap_csv = tmp_path / "redcap.csv"
    errors_csv.write_text("ptid,date,error_description\n", encoding="utf-8")
    status_csv.write_text("ptid,visitdate,stage,status\n", encoding="utf-8")
    redcap_csv.write_text("ptid,visitdate\n", encoding="utf-8")

    out_root = tmp_path / "output"
    out_root.mkdir()
    summary = out_root / "checkout-summary.csv"
    updates = out_root / "updates.json"
    notes = out_root / "notes.json"
    for f in (summary, updates, notes):
        f.write_text("{}", encoding="utf-8")

    import src.redcap_data.upload_checkout_processor as checkout_module

    def fake_checkout(**kwargs):
        stats = {
            "records_queued": 2,
            "records_blocked_errors": 1,
            "records_skipped_pass": 0,
            "records_error_notes": 0,
            "total_fw_finalized": 2,
            "total_errors": 1,
        }
        return summary, updates, notes, stats

    monkeypatch.setattr(checkout_module, "run_upload_checkout", fake_checkout)
    monkeypatch.setattr(
        cli_module, "upload_to_redcap", lambda path: {"success": True, "records_updated": 2}
    )

    cli_result, doc = _invoke(
        tmp_path,
        ["--upload-checkout", "-i", "JDT", "--adcid", "99",
         "--errors-csv", str(errors_csv), "--status-csv", str(status_csv),
         "--redcap-csv", str(redcap_csv)],
    )

    assert cli_result.exit_code == 0
    jsonschema.validate(doc, SCHEMA)
    assert doc["mode"] == "upload-checkout"
    assert doc["metrics"]["records_finalized"] == 2
    assert doc["metrics"]["records_blocked_by_errors"] == 1
    assert Path(doc["artifacts"]["checkout_summary_csv"]).is_file()
    assert Path(doc["artifacts"]["checkout_updates_json"]).is_file()
    telemetry = json.loads(next(telemetry_dir.glob("NR_TELEMETRY_LOG_*.json")).read_text(encoding="utf-8"))
    assert telemetry["payload"]["operation"] == "upload_checkout"
