"""Local path conventions for the bastion runtime."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path, PurePosixPath


REPORT_ARCHIVE_FOLDERS: dict[str, str] = {
    "MainHoldersReport_RFSOLM_Daily_": "GoldenHind",
    "EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_": "Davinci",
}

DATE_FILENAME_PATTERN = re.compile(r"(?P<day>\d{2})-(?P<mon>[A-Za-z]{3})-(?P<year>\d{4})")


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


def archive_folder_for(remote_path: str) -> str | None:
    """Return the deterministic archive folder for a target remote file."""

    remote_name = remote_file_name(remote_path)
    for prefix, folder in REPORT_ARCHIVE_FOLDERS.items():
        if remote_name.startswith(prefix):
            return folder
    return None


def file_date_from_name(name: str) -> date | None:
    """Extract a report date from a filename when present."""

    match = DATE_FILENAME_PATTERN.search(name)
    if not match:
        return None

    try:
        return datetime.strptime(match.group(0), "%d-%b-%Y").date()
    except ValueError:
        return None
