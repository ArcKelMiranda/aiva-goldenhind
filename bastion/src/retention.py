"""Local retention cleanup for bastion-ingested files."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from .paths import file_date_from_name
from .storage import resolve_storage_layout


def _file_timestamp(path: Path) -> datetime | None:
    file_date = file_date_from_name(path.name)
    if file_date is None:
        return None
    return datetime.combine(file_date, datetime.min.time(), tzinfo=timezone.utc)


def purge_previous_month_files(
    local_root: str | Path,
    now: datetime | None = None,
    bootstrap_floor_date: date | None = None,
) -> list[str]:
    """Delete archived and staged files that are older than the current month."""

    layout = resolve_storage_layout(local_root)
    current = now or datetime.now(timezone.utc)
    cutoff = date(current.year, current.month, 1)
    deleted: list[str] = []

    for folder in (layout.work, layout.archive):
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            if not path.is_file():
                continue
            file_timestamp = _file_timestamp(path)
            modified = (file_timestamp or datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)).date()
            if modified < cutoff:
                if bootstrap_floor_date is not None and file_timestamp is not None and bootstrap_floor_date <= file_timestamp.date() < cutoff:
                    continue
                path.unlink()
                deleted.append(str(path))

    return sorted(deleted)


def purge_expired_files(
    local_root: str | Path,
    retention_days: int,
    now: datetime | None = None,
    bootstrap_floor_date: date | None = None,
) -> list[str]:
    """Backward-compatible wrapper for the current-month retention policy."""

    _ = retention_days
    return purge_previous_month_files(local_root, now=now, bootstrap_floor_date=bootstrap_floor_date)
