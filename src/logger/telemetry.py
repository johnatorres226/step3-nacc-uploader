"""Telemetry and step-result writers shared by every CLI mode.

Implements the orchestration contract (pipeline-orchestrator/docs/STEP_CONTRACT.md):
telemetry on every terminal path, --result-json conforming to
step_result.schema.json, and exit codes 0/1/2.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

STEP_NAME = "nacc-uploader"

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def telemetry_dir() -> Path:
    return Path(os.getenv("TELEMETRY_PATH") or str(_PROJECT_ROOT / "telemetry")).resolve()


def classify_error(exc: BaseException) -> str:
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return "network"
    name = type(exc).__name__.lower()
    if any(token in name for token in ("connection", "timeout", "http", "request", "api")):
        return "network"
    if isinstance(exc, (KeyError, ValueError, TypeError)):
        return "data"
    return "unknown"


class RunRecorder:
    """One per CLI invocation: writes telemetry and the contract result document."""

    def __init__(
        self,
        *,
        mode: str,
        event_type: str,
        user: str,
        result_json: Optional[str],
        base_payload: Optional[dict] = None,
    ):
        self.mode = mode
        self.event_type = event_type
        self.user = user
        self.result_json = Path(result_json).resolve() if result_json else None
        self.base_payload = base_payload or {}
        self.started_at = datetime.now()
        self.run_id = self.started_at.strftime("%H%M%S")

    def success(
        self,
        *,
        artifacts: Optional[dict] = None,
        metrics: Optional[dict] = None,
        payload: Optional[dict] = None,
        no_op: bool = False,
    ) -> None:
        completed_at = datetime.now()
        self._write_telemetry(
            completed_at,
            status="success",
            payload={**self.base_payload, **(payload or metrics or {})},
            error=None,
        )
        self._write_result(
            completed_at,
            status="no_op" if no_op else "success",
            artifacts={} if no_op else (artifacts or {}),
            metrics=metrics or {},
            error=None,
        )

    def failure(
        self,
        *,
        error_type: str,
        message: str,
        category: str,
        exit_code: int = 1,
        payload: Optional[dict] = None,
    ) -> None:
        """Record the failure on both channels and exit. Does not return."""
        completed_at = datetime.now()
        self._write_telemetry(
            completed_at,
            status="failure",
            payload={**self.base_payload, **(payload or {})},
            error=f"{error_type}: {message}",
        )
        self._write_result(
            completed_at,
            status="failure",
            artifacts={},
            metrics={},
            error={"type": error_type, "message": message, "category": category},
        )
        sys.exit(exit_code)

    def _write_telemetry(
        self, completed_at: datetime, *, status: str, payload: dict, error: Optional[str]
    ) -> None:
        directory = telemetry_dir()
        directory.mkdir(parents=True, exist_ok=True)
        stamp = completed_at.strftime("%d%b%Y-%H%M%S").upper()
        path = directory / f"{self.event_type}_TELEMETRY_LOG_{stamp}.json"
        document = {
            "run_id": self.run_id,
            "step": STEP_NAME,
            "event_type": self.event_type,
            "user": self.user,
            "started_at": self.started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_s": round((completed_at - self.started_at).total_seconds(), 1),
            "status": status,
            "payload": payload,
            "error": error,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(document, f, indent=2, ensure_ascii=False)

    def _write_result(
        self,
        completed_at: datetime,
        *,
        status: str,
        artifacts: dict,
        metrics: dict,
        error: Optional[dict],
    ) -> None:
        if self.result_json is None:
            return
        self.result_json.parent.mkdir(parents=True, exist_ok=True)
        document = {
            "schema_version": 1,
            "step": STEP_NAME,
            "mode": self.mode,
            "run_id": self.run_id,
            "status": status,
            "started_at": self.started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_s": round((completed_at - self.started_at).total_seconds(), 1),
            "artifacts": {name: str(Path(p).resolve()) for name, p in artifacts.items()},
            "metrics": metrics,
            "error": error,
        }
        with open(self.result_json, "w", encoding="utf-8") as f:
            json.dump(document, f, indent=2, ensure_ascii=False)
