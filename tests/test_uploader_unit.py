"""Offline tests for src/redcap_data/uploader.py — all SDK/API calls mocked."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.redcap_data import uploader


class FakeCenterError(Exception):
    pass


class FakeProject:
    group = "test-group"
    label = "ingest-form-project"

    def __init__(self):
        self.uploaded = []

    def upload_file(self, path):
        self.uploaded.append(path)
        return [{"size": 123}]


@pytest.fixture
def fw_mocks(monkeypatch, tmp_path):
    project = FakeProject()
    monkeypatch.setattr(uploader, "FLYWHEEL_AVAILABLE", True)
    monkeypatch.setattr(uploader, "Client", lambda key: SimpleNamespace(key=key), raising=False)
    monkeypatch.setattr(uploader, "CenterError", FakeCenterError, raising=False)
    monkeypatch.setattr(
        uploader, "get_center_id", lambda client, adcid: f"group-{adcid}", raising=False
    )
    monkeypatch.setattr(uploader, "get_project", lambda **kwargs: project, raising=False)
    monkeypatch.setenv("FW_API_KEY", "test-key")
    csv_path = tmp_path / "upload-uds.csv"
    csv_path.write_text("ptid,visitdate\nP001,2026-01-01\n", encoding="utf-8")
    return SimpleNamespace(project=project, csv_path=csv_path)


class TestUploadToFlywheelApi:
    def test_uploads_csv_and_reports_project(self, fw_mocks):
        result = uploader.upload_to_flywheel_api(fw_mocks.csv_path, adcid=48)

        assert result["success"] is True
        assert result["project"] == "test-group/ingest-form-project"
        assert fw_mocks.project.uploaded == [str(fw_mocks.csv_path)]

    def test_missing_csv_raises(self, fw_mocks, tmp_path):
        with pytest.raises(FileNotFoundError):
            uploader.upload_to_flywheel_api(tmp_path / "nope.csv", adcid=48)

    def test_empty_csv_raises(self, fw_mocks, tmp_path):
        empty = tmp_path / "empty.csv"
        empty.write_text("", encoding="utf-8")
        with pytest.raises(ValueError):
            uploader.upload_to_flywheel_api(empty, adcid=48)

    def test_missing_api_key_raises_connection_error(self, fw_mocks, monkeypatch):
        monkeypatch.delenv("FW_API_KEY")
        with pytest.raises(ConnectionError):
            uploader.upload_to_flywheel_api(fw_mocks.csv_path, adcid=48)

    def test_center_lookup_failure_raises_value_error(self, fw_mocks, monkeypatch):
        def boom(client, adcid):
            raise FakeCenterError("no such center")

        monkeypatch.setattr(uploader, "get_center_id", boom, raising=False)
        with pytest.raises(ValueError, match="Center lookup failed"):
            uploader.upload_to_flywheel_api(fw_mocks.csv_path, adcid=48)

    def test_missing_project_raises_value_error(self, fw_mocks, monkeypatch):
        monkeypatch.setattr(uploader, "get_project", lambda **kwargs: None, raising=False)
        with pytest.raises(ValueError, match="No ingest form project"):
            uploader.upload_to_flywheel_api(fw_mocks.csv_path, adcid=48)


def _fake_post(monkeypatch, status_code=200, payload=None, capture=None):
    def post(url, data=None, timeout=None):
        if capture is not None:
            capture.update({"url": url, "data": data})
        return SimpleNamespace(
            status_code=status_code,
            json=lambda: payload or {},
            text=json.dumps(payload or {}),
        )

    monkeypatch.setattr(uploader.requests, "post", post)


class TestUploadToRedcap:
    @pytest.fixture
    def updates_json(self, tmp_path):
        path = tmp_path / "updates.json"
        path.write_text(
            json.dumps({"metadata": {}, "records": [
                {"ptid": "P001", "nacc_finalization_status": "1"},
                {"ptid": "P002", "nacc_finalization_status": "1"},
            ]}),
            encoding="utf-8",
        )
        return path

    @pytest.fixture
    def redcap_env(self, monkeypatch):
        monkeypatch.setenv("REDCAP_API_TOKEN", "tok")
        monkeypatch.setenv("REDCAP_API_URL", "https://redcap.example/api/")

    def test_success_returns_count(self, updates_json, redcap_env, monkeypatch):
        captured = {}
        _fake_post(monkeypatch, payload={"count": 2}, capture=captured)

        result = uploader.upload_to_redcap(updates_json)

        assert result == {
            "success": True,
            "records_updated": 2,
            "json_path": str(updates_json),
            "message": "Status updated successfully",
        }
        sent = json.loads(captured["data"]["data"])
        assert [r["ptid"] for r in sent] == ["P001", "P002"]
        assert captured["data"]["overwriteBehavior"] == "normal"

    def test_empty_records_is_success_noop(self, tmp_path, redcap_env, monkeypatch):
        path = tmp_path / "empty.json"
        path.write_text(json.dumps({"records": []}), encoding="utf-8")
        _fake_post(monkeypatch)

        result = uploader.upload_to_redcap(path)

        assert result["success"] is True
        assert result["records_updated"] == 0

    def test_http_error_reports_failure(self, updates_json, redcap_env, monkeypatch):
        _fake_post(monkeypatch, status_code=403, payload={"error": "bad token"})

        result = uploader.upload_to_redcap(updates_json)

        assert result["success"] is False
        assert "403" in result["error"]

    def test_missing_credentials_reports_failure(self, updates_json, monkeypatch):
        monkeypatch.delenv("REDCAP_API_TOKEN", raising=False)
        monkeypatch.delenv("REDCAP_API_KEY", raising=False)
        monkeypatch.delenv("REDCAP_API_URL", raising=False)

        result = uploader.upload_to_redcap(updates_json)

        assert result["success"] is False
        assert result["records_updated"] == 0

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            uploader.upload_to_redcap(tmp_path / "nope.json")

    def test_invalid_json_raises_value_error(self, tmp_path, redcap_env):
        path = tmp_path / "bad.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(ValueError):
            uploader.upload_to_redcap(path)


class TestUpdateRedcapStatus:
    def test_builds_per_ptid_payload(self, monkeypatch):
        monkeypatch.setenv("REDCAP_API_TOKEN", "tok")
        monkeypatch.setenv("REDCAP_API_URL", "https://redcap.example/api/")
        captured = {}
        _fake_post(monkeypatch, payload={"count": 2}, capture=captured)

        result = uploader.update_redcap_status(
            ["P001", "P002"], adcid=48,
            upload_result={"project": "g/p", "pipeline": "sandbox"},
        )

        assert result["success"] is True
        sent = json.loads(captured["data"]["data"])
        assert {r["ptid"] for r in sent} == {"P001", "P002"}
        assert all(r["nacc_upload_pipeline"] == "sandbox" for r in sent)
        assert all(r["nacc_upload_adcid"] == "48" for r in sent)
