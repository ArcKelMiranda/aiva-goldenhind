"""Typed contracts for the ingestion runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class IngestConfig:
    """Runtime configuration for the bastion ingestion job."""

    sftp_host: str
    sftp_port: int
    username: str
    secret_id: str
    remote_dir: str
    local_root: str
    retention_days: int = 90


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """Outcome emitted by the ingestion runtime."""

    status: str
    downloaded_files: list[str]
    deleted_files: list[str]
    correlation_id: str


def new_correlation_id() -> str:
    """Generate a stable correlation identifier for one runtime invocation."""

    return uuid4().hex


def bootstrap_result(correlation_id: str | None = None) -> IngestionResult:
    """Build the initial runtime result envelope for the scaffolded entrypoint."""

    return IngestionResult(
        status="success",
        downloaded_files=[],
        deleted_files=[],
        correlation_id=correlation_id or new_correlation_id(),
    )


def local_root_path(config: IngestConfig) -> Path:
    """Return the configured local root as a path object."""

    return Path(config.local_root).expanduser()
