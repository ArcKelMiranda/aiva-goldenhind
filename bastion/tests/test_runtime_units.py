"""Unit coverage for bastion ingestion helpers."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import date, datetime, timezone

from src.config import DEFAULT_LOCAL_ROOT, DEFAULT_RETENTION_DAYS, load_config
from src.logger import JsonFormatter
from src.paths import archive_dir, archive_folder_for, remote_file_name, work_dir
from src.retention import purge_expired_files, purge_previous_month_files
from src.storage import archive_candidate_paths, archive_path_for, staged_download_path, work_path_for
from scripts.run_ingestion import _is_already_archived, _is_target_file, _should_download_file


def test_load_config_parses_environment(monkeypatch):
    monkeypatch.setenv("BNY_SFTP_HOST", "sftp.example.test")
    monkeypatch.setenv("BNY_SFTP_PORT", "2222")
    monkeypatch.setenv("BNY_SFTP_USERNAME", "bny-user")
    monkeypatch.setenv("BNY_SFTP_SECRET_ID", "secret-id")
    monkeypatch.setenv("BNY_SFTP_REMOTE_DIR", "/incoming")
    monkeypatch.setenv("YHAT_BNY_LOCAL_ROOT", "C:/tmp/yhat")
    monkeypatch.setenv("YHAT_BNY_RETENTION_DAYS", "120")

    config = load_config()

    assert config.sftp_host == "sftp.example.test"
    assert config.sftp_port == 2222
    assert config.username == "bny-user"
    assert config.secret_id == "secret-id"
    assert config.remote_dir == "/incoming"
    assert config.local_root == "C:/tmp/yhat"
    assert config.retention_days == 120


def test_load_config_uses_defaults(monkeypatch):
    for name in (
        "BNY_SFTP_HOST",
        "BNY_SFTP_PORT",
        "BNY_SFTP_USERNAME",
        "BNY_SFTP_SECRET_ID",
        "BNY_SFTP_REMOTE_DIR",
        "YHAT_BNY_LOCAL_ROOT",
        "YHAT_BNY_RETENTION_DAYS",
    ):
        monkeypatch.delenv(name, raising=False)

    config = load_config()

    assert config.sftp_host == ""
    assert config.sftp_port == 22
    assert config.username == ""
    assert config.secret_id == ""
    assert config.remote_dir == "/"
    assert config.local_root == str(DEFAULT_LOCAL_ROOT)
    assert config.retention_days == DEFAULT_RETENTION_DAYS


def test_path_mapping_uses_remote_filename_and_bastion_layout(tmp_path):
    root = tmp_path / "bastion"

    assert remote_file_name("/bnY/inbound/report.csv") == "report.csv"
    assert remote_file_name("/") == "downloaded-file"
    assert work_dir(root) == root / "data" / "work"
    assert archive_dir(root) == root / "data" / "archive"
    assert work_path_for(root, "/bnY/inbound/report.csv") == root / "data" / "work" / "report.csv"
    assert archive_path_for(root, "/bnY/inbound/report.csv") == root / "data" / "archive" / "report.csv"
    assert archive_folder_for("MainHoldersReport_RFSOLM_Daily_01-Jul-2026.XLSX") == "GoldenHind"
    assert archive_folder_for("EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_01-Jul-2026.XLSX") == "Davinci"
    assert archive_path_for(root, "MainHoldersReport_RFSOLM_Daily_01-Jul-2026.XLSX") == root / "data" / "archive" / "GoldenHind" / "MainHoldersReport_RFSOLM_Daily_01-Jul-2026.XLSX"
    assert archive_path_for(root, "EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_01-Jul-2026.XLSX") == root / "data" / "archive" / "Davinci" / "EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_01-Jul-2026.XLSX"
    staged = staged_download_path(root, "/bnY/inbound/report.csv", "corr-123")
    assert staged.name == "report.csv.corr-123.part"


def test_retention_purges_only_expired_files(tmp_path):
    root = tmp_path / "bastion"
    work = root / "data" / "work"
    archive = root / "data" / "archive"
    work.mkdir(parents=True)
    archive.mkdir(parents=True)

    old_file = work / "old.csv"
    new_file = archive / "new.csv"
    old_file.write_text("old")
    new_file.write_text("new")

    now = datetime(2026, 7, 16, tzinfo=timezone.utc)
    expired = now.timestamp() - (91 * 24 * 60 * 60)
    fresh = now.timestamp() - (5 * 24 * 60 * 60)
    os.utime(old_file, (expired, expired))
    os.utime(new_file, (fresh, fresh))

    deleted = purge_expired_files(root, 90, now=now)

    assert deleted == [str(old_file)]
    assert not old_file.exists()
    assert new_file.exists()


def test_retention_preserves_bootstrap_window_on_first_run(tmp_path):
    root = tmp_path / "bastion"
    work = root / "data" / "work"
    archive = root / "data" / "archive"
    work.mkdir(parents=True)
    archive.mkdir(parents=True)

    old_file = archive / "EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_26-Jun-2026.XLSX"
    bootstrap_work_file = work / "EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_28-Jun-2026.XLSX"
    bootstrap_archive_file = archive / "EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_30-Jun-2026.XLSX"
    july_file = archive / "EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_01-Jul-2026.XLSX"
    for file_path in (old_file, bootstrap_work_file, bootstrap_archive_file, july_file):
        file_path.write_text("x")

    now = datetime(2026, 7, 16, tzinfo=timezone.utc)

    deleted = purge_previous_month_files(root, now=now, bootstrap_floor_date=date(2026, 6, 28))

    assert deleted == [str(old_file)]
    assert not old_file.exists()
    assert bootstrap_work_file.exists()
    assert bootstrap_archive_file.exists()
    assert july_file.exists()


def test_retention_purges_june_files_after_bootstrap_completes(tmp_path):
    root = tmp_path / "bastion"
    archive = root / "data" / "archive"
    archive.mkdir(parents=True)

    june_file = archive / "EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_30-Jun-2026.XLSX"
    july_file = archive / "EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_01-Jul-2026.XLSX"
    june_file.write_text("old")
    july_file.write_text("new")

    now = datetime(2026, 7, 16, tzinfo=timezone.utc)

    deleted = purge_previous_month_files(root, now=now)

    assert deleted == [str(june_file)]
    assert not june_file.exists()
    assert july_file.exists()


def test_json_log_payload_shape_with_fixed_timestamp():
    formatter = JsonFormatter()
    formatter.converter = time.gmtime
    record = logging.LogRecord(
        name="yhat_bny_secure_sftp_ingestion",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="file_downloaded",
        args=(),
        exc_info=None,
    )
    record.created = 1_700_000_000.0
    record.msecs = 0.0
    record.event = "file_downloaded"
    record.status = "success"
    record.remoteFile = "report.csv"
    record.localPath = "/tmp/report.csv"
    record.bytes = 128
    record.correlationId = "corr-123"

    payload = json.loads(formatter.format(record))

    assert payload["timestamp"].startswith("2023-11-14T22:13:20")
    assert payload["timestamp"][-5] in {"+", "-"}
    assert payload["level"] == "info"
    assert payload["logger"] == "yhat_bny_secure_sftp_ingestion"
    assert payload["message"] == "file_downloaded"
    assert payload["event"] == "file_downloaded"
    assert payload["status"] == "success"
    assert payload["remoteFile"] == "report.csv"
    assert payload["localPath"] == "/tmp/report.csv"
    assert payload["bytes"] == 128
    assert payload["correlationId"] == "corr-123"


def test_target_file_filter_only_accepts_enhanced_transaction_reports():
    assert _is_target_file("EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_01-Jul-2026.XLSX") is True
    assert _is_target_file("MainHoldersReport_RFSOLM_Daily_01-Jul-2026.XLSX") is True
    assert _is_target_file("salesrepOLP20260717070010.csv") is False
    assert _is_target_file("~$EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_01-Jul-2026.XLSX") is False


def test_archive_dedup_check_detects_existing_files(tmp_path):
    root = tmp_path / "bastion"
    archive = root / "data" / "archive" / "Davinci"
    archive.mkdir(parents=True)
    existing = archive / "EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_01-Jul-2026.XLSX"
    existing.write_text("present")

    legacy = root / "data" / "archive" / "EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_02-Jul-2026.XLSX"
    legacy.write_text("present-legacy")

    assert _is_already_archived(root, "EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_01-Jul-2026.XLSX") is True
    assert _is_already_archived(root, "EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_02-Jul-2026.XLSX") is True
    assert _is_already_archived(root, "EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_03-Jul-2026.XLSX") is False


def test_archive_candidate_paths_include_routed_and_legacy_locations(tmp_path):
    root = tmp_path / "bastion"

    candidates = archive_candidate_paths(root, "EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_01-Jul-2026.XLSX")

    assert candidates == (
        root / "data" / "archive" / "Davinci" / "EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_01-Jul-2026.XLSX",
        root / "data" / "archive" / "EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_01-Jul-2026.XLSX",
    )


def test_download_selection_uses_bootstrap_cutoff_until_marker_exists(tmp_path):
    root = tmp_path / "bastion"
    assert _should_download_file(root, "EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_27-Jun-2026.XLSX") is False
    assert _should_download_file(root, "EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_28-Jun-2026.XLSX") is True
    assert _should_download_file(root, "MainHoldersReport_RFSOLM_Daily_27-Jun-2026.XLSX") is False
    assert _should_download_file(root, "MainHoldersReport_RFSOLM_Daily_28-Jun-2026.XLSX") is True


def test_download_selection_switches_to_current_month_after_bootstrap(tmp_path):
    root = tmp_path / "bastion"
    marker = root / "data" / ".registry" / "bootstrap.complete"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("done")

    assert _should_download_file(root, "EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_30-Jun-2026.XLSX") is False
    assert _should_download_file(root, "EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_01-Jul-2026.XLSX") is True
    assert _should_download_file(root, "MainHoldersReport_RFSOLM_Daily_30-Jun-2026.XLSX") is False
    assert _should_download_file(root, "MainHoldersReport_RFSOLM_Daily_01-Jul-2026.XLSX") is True
