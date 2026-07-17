"""Pytest fixtures for bastion ingestion tests."""

from __future__ import annotations

import logging
import stat
import sys
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.logger import LOGGER_NAME
from src import sftp_client as sftp_module
from scripts import run_ingestion


class FakeSSMClient:
    def __init__(self, parameter_value: str) -> None:
        self.parameter_value = parameter_value

    def get_parameter(self, Name: str, WithDecryption: bool = True):  # noqa: N803 - boto3 contract
        return {"Parameter": {"Value": self.parameter_value}}


class FakeSftpSession:
    def __init__(self, files: dict[str, bytes]) -> None:
        self._files = files

    def listdir_attr(self, remote_dir: str):
        return [SimpleNamespace(filename=name, st_mode=stat.S_IFREG) for name in sorted(self._files)]

    def get(self, remote_path: str, destination: str) -> None:
        name = PurePosixPath(remote_path).name
        Path(destination).write_bytes(self._files[name])

    def close(self) -> None:
        return None


class FakeSSHClient:
    def __init__(self, files: dict[str, bytes] | None = None, auth_error: bool = False) -> None:
        self._files = files or {}
        self._auth_error = auth_error
        self.closed = False

    def load_system_host_keys(self) -> None:
        return None

    def set_missing_host_key_policy(self, policy) -> None:  # noqa: ANN001 - paramiko contract
        return None

    def connect(self, **kwargs) -> None:
        if self._auth_error:
            raise sftp_module.paramiko.AuthenticationException("auth failed")

    def open_sftp(self):
        return FakeSftpSession(self._files)

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def reset_runtime_logger():
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    yield
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


@pytest.fixture
def install_parameter_client(monkeypatch):
    def _install(parameter_value: str) -> FakeSSMClient:
        client = FakeSSMClient(parameter_value)
        def _client(service_name, *args, **kwargs):
            if service_name != "ssm":
                raise AssertionError(service_name)
            return client

        monkeypatch.setattr(run_ingestion.boto3, "client", _client)
        return client

    return _install


@pytest.fixture
def install_fake_ssh_client(monkeypatch):
    def _install(files: dict[str, bytes] | None = None, auth_error: bool = False) -> FakeSSHClient:
        client = FakeSSHClient(files=files, auth_error=auth_error)
        monkeypatch.setattr(sftp_module.paramiko, "SSHClient", lambda: client)
        return client

    return _install
