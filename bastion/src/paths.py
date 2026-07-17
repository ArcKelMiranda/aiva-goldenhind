"""Local path conventions for the bastion runtime."""

from __future__ import annotations

from pathlib import Path, PurePosixPath


def bastion_root(local_root: str | Path) -> Path:
    return Path(local_root).expanduser().resolve()


def data_root(local_root: str | Path) -> Path:
    return bastion_root(local_root) / "data"


def work_dir(local_root: str | Path) -> Path:
    return data_root(local_root) / "work"


def archive_dir(local_root: str | Path) -> Path:
    return data_root(local_root) / "archive"


def registry_dir(local_root: str | Path) -> Path:
    return data_root(local_root) / ".registry"


def logs_dir(local_root: str | Path) -> Path:
    return bastion_root(local_root) / "logs"


def storage_dirs(local_root: str | Path) -> dict[str, Path]:
    root = bastion_root(local_root)
    return {
        "root": root,
        "data": root / "data",
        "work": work_dir(root),
        "archive": archive_dir(root),
        "registry": registry_dir(root),
        "logs": logs_dir(root),
    }


def remote_file_name(remote_path: str) -> str:
    """Return a safe local filename from a remote POSIX path."""

    candidate = PurePosixPath(remote_path).name
    return candidate or "downloaded-file"
