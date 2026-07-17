"""Local retention cleanup for bastion-ingested files."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from .storage import resolve_storage_layout

MONTH_DATE_PATTERN = re.compile(r"(?P<day>\d{2})-(?P<mon>[A-Za-z]{3})-(?P<year>\d{4})")


def _file_timestamp(path: Path) -> datetime | None:
    match = MONTH_DATE_PATTERN.search(path.name)
    if match:
        try:
            return datetime.strptime(match.group(0), "%d-%b-%Y").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def purge_previous_month_files(local_root: str | Path, now: datetime | None = None) -> list[str]:
    """Delete archived and staged files that are older than the current month."""

    layout = resolve_storage_layout(local_root)
    current = now or datetime.now(timezone.utc)
    cutoff = datetime(current.year, current.month, 1, tzinfo=timezone.utc)
    deleted: list[str] = []

    for folder in (layout.work, layout.archive):
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            if not path.is_file():
                continue
            modified = _file_timestamp(path) or datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if modified < cutoff:
                path.unlink()
                deleted.append(str(path))

    return sorted(deleted)


def purge_expired_files(local_root: str | Path, retention_days: int, now: datetime | None = None) -> list[str]:
    """Backward-compatible wrapper for the current-month retention policy."""

    _ = retention_days
    return purge_previous_month_files(local_root, now=now)
