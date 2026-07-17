"""Local retention cleanup for bastion-ingested files."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from .storage import resolve_storage_layout


def purge_expired_files(local_root: str | Path, retention_days: int, now: datetime | None = None) -> list[str]:
    """Delete archived and staged files older than the retention window."""

    layout = resolve_storage_layout(local_root)
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=retention_days)
    deleted: list[str] = []

    for folder in (layout.work, layout.archive):
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            if not path.is_file():
                continue
            modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if modified < cutoff:
                path.unlink()
                deleted.append(str(path))

    return sorted(deleted)
