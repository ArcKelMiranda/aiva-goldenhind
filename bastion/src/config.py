"""Configuration loading for the bastion ingestion runtime."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

from .contracts import IngestConfig

DEFAULT_LOCAL_ROOT = Path.home() / "yhat_bny"
DEFAULT_RETENTION_DAYS = 90


def _read_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def load_config() -> IngestConfig:
    """Load the runtime configuration from environment variables."""

    return IngestConfig(
        sftp_host=os.getenv("BNY_SFTP_HOST", ""),
        sftp_port=_read_int("BNY_SFTP_PORT", 22),
        username=os.getenv("BNY_SFTP_USERNAME", ""),
        secret_id=os.getenv("BNY_SFTP_SECRET_ID", ""),
        remote_dir=os.getenv("BNY_SFTP_REMOTE_DIR", "/"),
        local_root=os.getenv("YHAT_BNY_LOCAL_ROOT", str(DEFAULT_LOCAL_ROOT)),
        retention_days=_read_int("YHAT_BNY_RETENTION_DAYS", DEFAULT_RETENTION_DAYS),
    )


def with_local_root(config: IngestConfig, local_root: str) -> IngestConfig:
    """Return a copy of the config with an overridden local root."""

    return replace(config, local_root=local_root)
