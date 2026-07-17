"""Integration coverage for the bastion ingestion entrypoint."""

from __future__ import annotations

import json

from scripts import run_ingestion


def _set_runtime_env(monkeypatch, root):
    monkeypatch.setenv("BNY_SFTP_HOST", "sftp.example.test")
    monkeypatch.setenv("BNY_SFTP_PORT", "22")
    monkeypatch.setenv("BNY_SFTP_USERNAME", "bny-user")
    monkeypatch.setenv("BNY_SFTP_SECRET_ID", "secret-id")
    monkeypatch.setenv("BNY_SFTP_REMOTE_DIR", "/incoming")
    monkeypatch.setenv("YHAT_BNY_LOCAL_ROOT", str(root))
    monkeypatch.setenv("YHAT_BNY_RETENTION_DAYS", "90")


def test_main_success_pulls_and_archives_file(tmp_path, monkeypatch, capsys, install_parameter_client, install_fake_ssh_client):
    root = tmp_path / "bastion"
    _set_runtime_env(monkeypatch, root)
    install_parameter_client('{"password":"secret"}')
    install_fake_ssh_client({
        "EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_01-Jul-2026.XLSX": b"alpha,beta\n1,2\n",
        "salesrepOLP20260717070010.csv": b"ignore-me",
    })

    exit_code = run_ingestion.main()

    output = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert exit_code == 0
    assert (root / "data" / "archive" / "EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_01-Jul-2026.XLSX").read_bytes() == b"alpha,beta\n1,2\n"
    assert not (root / "data" / "archive" / "salesrepOLP20260717070010.csv").exists()
    assert any(event["event"] == "file_downloaded" and event["localPath"].endswith("EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_01-Jul-2026.XLSX") for event in output)
    assert any(event["event"] == "retention_complete" and event["deletedCount"] == 0 for event in output)
    assert any(event["event"] == "ingestion_complete" and event["status"] == "success" for event in output)


def test_main_direct_manual_operator_path_runs_without_scheduler(tmp_path, monkeypatch, capsys, install_parameter_client, install_fake_ssh_client):
    root = tmp_path / "bastion"
    _set_runtime_env(monkeypatch, root)
    monkeypatch.delenv("BNY_SFTP_SCHEDULE", raising=False)
    monkeypatch.delenv("YHAT_BNY_SCHEDULE", raising=False)
    install_parameter_client('{"password":"secret"}')
    install_fake_ssh_client({"EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_01-Jul-2026.XLSX": b"alpha,beta\n1,2\n"})

    manual_operator_main = run_ingestion.main
    exit_code = manual_operator_main()

    output = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert exit_code == 0
    assert (root / "data" / "archive" / "EnhancedTransactionReportInclFX_RFSOLM_MonthToDate_01-Jul-2026.XLSX").read_bytes() == b"alpha,beta\n1,2\n"
    assert any(event["event"] == "runtime_bootstrap" and event["status"] == "starting" for event in output)
    assert any(event["event"] == "ingestion_complete" and event["status"] == "success" for event in output)


def test_main_no_file_reports_no_file_and_stays_clean(tmp_path, monkeypatch, capsys, install_parameter_client, install_fake_ssh_client):
    root = tmp_path / "bastion"
    _set_runtime_env(monkeypatch, root)
    install_parameter_client('{"password":"secret"}')
    install_fake_ssh_client({"salesrepOLP20260717070010.csv": b"ignore-me"})

    exit_code = run_ingestion.main()

    output = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert exit_code == 0
    assert not (root / "data" / "archive").joinpath("report.csv").exists()
    assert any(event["event"] == "ingestion_no_file" and event["status"] == "no_file" for event in output)
    assert any(event["event"] == "ingestion_complete" and event["status"] == "no_file" for event in output)


def test_main_auth_failure_returns_nonzero(tmp_path, monkeypatch, capsys, install_parameter_client, install_fake_ssh_client):
    root = tmp_path / "bastion"
    _set_runtime_env(monkeypatch, root)
    install_parameter_client('{"password":"secret"}')
    install_fake_ssh_client(auth_error=True)

    exit_code = run_ingestion.main()

    output = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert exit_code == 1
    assert any(event["event"] == "ingestion_failed" and event["status"] == "failure" for event in output)
    assert any(event["event"] == "ingestion_complete" and event["status"] == "failure" for event in output)
