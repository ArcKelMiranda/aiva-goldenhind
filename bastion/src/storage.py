"""Local-only storage helpers for the bastion runtime."""

from __future__ import annotations

from os import replace
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .paths import archive_dir, bastion_root, logs_dir, registry_dir, remote_file_name, work_dir


@dataclass(frozen=True, slots=True)
class StorageLayout:
    """Resolved local storage directories for one bastion host."""

    root: Path
    data: Path
    work: Path
    archive: Path
    registry: Path
    logs: Path


def resolve_storage_layout(local_root: str | Path) -> StorageLayout:
    root = bastion_root(local_root)
    return StorageLayout(
        root=root,
        data=root / "data",
        work=work_dir(root),
        archive=archive_dir(root),
        registry=registry_dir(root),
        logs=logs_dir(root),
    )


def ensure_storage_layout(local_root: str | Path) -> StorageLayout:
    """Create the bastion directories if they do not already exist."""

    layout = resolve_storage_layout(local_root)
    for path in (layout.data, layout.work, layout.archive, layout.registry, layout.logs):
        path.mkdir(parents=True, exist_ok=True)
    return layout


def work_path_for(local_root: str | Path, remote_path: str) -> Path:
    return resolve_storage_layout(local_root).work / remote_file_name(remote_path)


def archive_path_for(local_root: str | Path, remote_path: str) -> Path:
    return resolve_storage_layout(local_root).archive / remote_file_name(remote_path)


def staged_download_path(local_root: str | Path, remote_path: str, correlation_id: str | None = None) -> Path:
    """Return a unique work-path for a downloaded file before promotion."""

    layout = resolve_storage_layout(local_root)
    token = correlation_id or uuid4().hex
    safe_name = remote_file_name(remote_path)
    return layout.work / f"{safe_name}.{token}.part"


def promote_staged_file(local_root: str | Path, staged_path: str | Path, remote_path: str) -> Path:
    """Atomically move a staged file into the archive directory."""

    layout = resolve_storage_layout(local_root)
    destination = layout.archive / remote_file_name(remote_path)
    source = Path(staged_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    replace(source, destination)
    return destination


def local_only_directories(local_root: str | Path) -> dict[str, str]:
    """Return the canonical directory conventions as strings for logging."""

    layout = resolve_storage_layout(local_root)
    return {
        "root": str(layout.root),
        "data": str(layout.data),
        "work": str(layout.work),
        "archive": str(layout.archive),
        "registry": str(layout.registry),
        "logs": str(layout.logs),
    }
