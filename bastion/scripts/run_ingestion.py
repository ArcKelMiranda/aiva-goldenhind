"""Entry point for the BNY secure SFTP ingestion bastion runtime."""

from __future__ import annotations

import sys
import os
from datetime import date, datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

BASTION_ROOT = Path(__file__).resolve().parents[1]
if str(BASTION_ROOT) not in sys.path:
    sys.path.insert(0, str(BASTION_ROOT))

from src.config import load_config
from src.contracts import IngestionResult, new_correlation_id
from src.logger import configure_logger, emit_event
from src.paths import archive_folder_for, file_date_from_name
from src.retention import purge_previous_month_files
from src.sftp_client import SftpAuthError, SftpClient, SftpClientError, SftpNoFileError, parse_secret_payload
from src.storage import archive_candidate_paths, archive_path_for, bootstrap_marker_path, ensure_storage_layout, local_only_directories, promote_staged_file, staged_download_path

BOOTSTRAP_CUTOFF = date(2026, 6, 28)


def _read_parameter_string(parameter_name: str) -> str:
    region_name = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
    client = boto3.client("ssm", region_name=region_name)
    response = client.get_parameter(Name=parameter_name, WithDecryption=True)
    parameter = response.get("Parameter", {})
    value = parameter.get("Value")
    if value:
        return value

    raise ValueError(f"Parameter {parameter_name} did not contain a usable value")


def _is_target_file(remote_name: str) -> bool:
    return archive_folder_for(remote_name) is not None and not remote_name.startswith("~$") and not remote_name.startswith(".")


def _remote_file_date(remote_name: str) -> date | None:
    return file_date_from_name(remote_name)


def _bootstrap_complete(local_root: str | Path) -> bool:
    return bootstrap_marker_path(local_root).exists()


def _mark_bootstrap_complete(local_root: str | Path) -> None:
    marker = bootstrap_marker_path(local_root)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(datetime.now(timezone.utc).isoformat())


def _selection_cutoff(local_root: str | Path, now: date | None = None) -> date:
    current = now or datetime.now(timezone.utc).date()
    if _bootstrap_complete(local_root):
        return date(current.year, current.month, 1)
    return BOOTSTRAP_CUTOFF


def _should_download_file(local_root: str | Path, remote_name: str, now: date | None = None) -> bool:
    file_date = _remote_file_date(remote_name)
    if file_date is None:
        return False
    return file_date >= _selection_cutoff(local_root, now=now)


def _is_already_archived(local_root: str | Path, remote_name: str) -> bool:
    return any(candidate.exists() for candidate in archive_candidate_paths(local_root, remote_name))


def _emit_summary(logger, correlation_id: str, status: str, downloaded_files: list[str], deleted_files: list[str]) -> None:
    emit_event(
        logger,
        event="ingestion_complete",
        status=status,
        correlationId=correlation_id,
        downloadedFiles=downloaded_files,
        deletedFiles=deleted_files,
        downloadedCount=len(downloaded_files),
        deletedCount=len(deleted_files),
    )


def main() -> int:
    config = load_config()
    logger = configure_logger()
    layout = ensure_storage_layout(config.local_root)
    bootstrap_active = not _bootstrap_complete(config.local_root)
    correlation_id = new_correlation_id()
    downloaded_files: list[str] = []
    deleted_files: list[str] = []
    status = "success"
    exit_code = 0

    emit_event(
        logger,
        event="runtime_bootstrap",
        status="starting",
        correlationId=correlation_id,
        localRoot=str(layout.root),
        retentionDays=config.retention_days,
        localPath=str(layout.archive),
        directories=local_only_directories(config.local_root),
    )

    try:
        secret = parse_secret_payload(_read_parameter_string(config.secret_id))
        client = SftpClient(config.sftp_host, config.sftp_port, config.username, secret)
        target_files = [remote_name for remote_name in client.list_files(config.remote_dir) if _is_target_file(remote_name)]
        target_files = [remote_name for remote_name in target_files if _should_download_file(config.local_root, remote_name)]
        target_files = [remote_name for remote_name in target_files if not _is_already_archived(config.local_root, remote_name)]
        if not target_files:
            raise SftpNoFileError(f"No new target files found in {config.remote_dir}")

        for remote_name in target_files:
            staged_path = staged_download_path(config.local_root, remote_name, correlation_id)
            bytes_written = client.download_file(config.remote_dir, remote_name, staged_path)
            archived_path = promote_staged_file(config.local_root, staged_path, remote_name)
            downloaded_files.append(str(archived_path))
            emit_event(
                logger,
                event="file_downloaded",
                status="success",
                correlationId=correlation_id,
                remoteFile=remote_name,
                localPath=str(archived_path),
                bytes=bytes_written,
            )
    except SftpNoFileError as exc:
        status = "no_file"
        emit_event(
            logger,
            event="ingestion_no_file",
            status=status,
            correlationId=correlation_id,
            error=str(exc),
        )
    except SftpAuthError as exc:
        status = "failure"
        exit_code = 1
        emit_event(
            logger,
            event="ingestion_failed",
            status=status,
            correlationId=correlation_id,
            error=str(exc),
        )
    except (SftpClientError, ValueError, BotoCoreError, ClientError) as exc:
        status = "failure"
        exit_code = 1
        emit_event(
            logger,
            event="ingestion_failed",
            status=status,
            correlationId=correlation_id,
            error=str(exc),
        )
    finally:
        try:
            deleted_files = purge_previous_month_files(
                config.local_root,
                bootstrap_floor_date=BOOTSTRAP_CUTOFF if bootstrap_active else None,
            )
            emit_event(
                logger,
                event="retention_complete",
                status="success",
                correlationId=correlation_id,
                retentionCutoff="current-month",
                deletedFiles=deleted_files,
                deletedCount=len(deleted_files),
            )
        except Exception as exc:  # pragma: no cover - defensive operational logging
            status = "failure"
            exit_code = 1
            emit_event(
                logger,
                event="retention_failed",
                status=status,
                correlationId=correlation_id,
                retentionDays=config.retention_days,
                error=str(exc),
            )
    
    _emit_summary(logger, correlation_id, status, downloaded_files, deleted_files)
    _result = IngestionResult(
        status=status,
        downloaded_files=downloaded_files,
        deleted_files=deleted_files,
        correlation_id=correlation_id,
    )
    if status in {"success", "no_file"} and not _bootstrap_complete(config.local_root):
        _mark_bootstrap_complete(config.local_root)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
