"""Paramiko-based SFTP client for bastion ingestion."""

from __future__ import annotations

import io
import json
import posixpath
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from types import SimpleNamespace

try:
    import paramiko
except ModuleNotFoundError:  # pragma: no cover - fallback for test-only environments
    class _MissingParamikoError(Exception):
        """Raised when the real paramiko dependency is unavailable."""

    class _MissingKeyLoader:
        @staticmethod
        def from_private_key(*args, **kwargs):
            raise _MissingParamikoError("paramiko is required for private key auth")

    class _MissingSSHClient:
        def load_system_host_keys(self):
            return None

        def set_missing_host_key_policy(self, policy):
            return None

        def connect(self, *args, **kwargs):
            raise _MissingParamikoError("paramiko is required for SSH connections")

        def open_sftp(self):
            raise _MissingParamikoError("paramiko is required for SSH connections")

        def close(self):
            return None

    paramiko = SimpleNamespace(
        AuthenticationException=_MissingParamikoError,
        SSHClient=_MissingSSHClient,
        RejectPolicy=object,
        RSAKey=_MissingKeyLoader,
        ECDSAKey=_MissingKeyLoader,
        Ed25519Key=_MissingKeyLoader,
        PKey=object,
    )


class SftpClientError(Exception):
    """Base error for SFTP operations."""


class SftpAuthError(SftpClientError):
    """Raised when the remote server rejects authentication."""


class SftpNoFileError(SftpClientError):
    """Raised when the remote directory has no downloadable files."""


@dataclass(frozen=True)
class SftpSecret:
    """Authentication material resolved from an SSM parameter payload."""

    password: str | None = None
    private_key: str | None = None
    passphrase: str | None = None


def parse_secret_payload(secret_payload: str) -> SftpSecret:
    """Normalize an SSM parameter payload into auth material."""

    raw = secret_payload.strip()
    if not raw:
        raise ValueError("Secret payload is empty")

    try:
        decoded: Any = json.loads(raw)
    except json.JSONDecodeError:
        return SftpSecret(password=raw)

    if isinstance(decoded, str):
        return SftpSecret(password=decoded)

    if isinstance(decoded, dict):
        password = decoded.get("password") or decoded.get("ssh_password") or decoded.get("sftp_password")
        private_key = decoded.get("private_key") or decoded.get("privateKey")
        passphrase = decoded.get("passphrase") or decoded.get("private_key_passphrase")
        return SftpSecret(
            password=str(password) if password is not None else None,
            private_key=str(private_key) if private_key is not None else None,
            passphrase=str(passphrase) if passphrase is not None else None,
        )

    raise ValueError("Unsupported secret payload shape")


def _load_private_key(secret: SftpSecret) -> paramiko.PKey | None:
    if not secret.private_key:
        return None

    loaders = (
        paramiko.RSAKey.from_private_key,
        paramiko.ECDSAKey.from_private_key,
        paramiko.Ed25519Key.from_private_key,
    )
    errors: list[Exception] = []
    for loader in loaders:
        key_stream = io.StringIO(secret.private_key)
        try:
            return loader(key_stream, password=secret.passphrase)
        except Exception as exc:  # pragma: no cover - only used for unsupported key types
            errors.append(exc)
    raise SftpAuthError("Unsupported private key format") from errors[-1]


class SftpClient:
    """Small SFTP helper with explicit auth and no-file failures."""

    def __init__(self, host: str, port: int, username: str, secret: SftpSecret, timeout: int = 30) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._secret = secret
        self._timeout = timeout

    def _connect(self) -> paramiko.SSHClient:
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.RejectPolicy())

        try:
            client.connect(
                hostname=self._host,
                port=self._port,
                username=self._username,
                password=self._secret.password,
                pkey=_load_private_key(self._secret),
                allow_agent=False,
                look_for_keys=False,
                timeout=self._timeout,
                banner_timeout=self._timeout,
                auth_timeout=self._timeout,
            )
        except paramiko.AuthenticationException as exc:
            client.close()
            raise SftpAuthError("BNY SFTP authentication failed") from exc
        except Exception as exc:
            client.close()
            raise SftpClientError(f"Unable to connect to BNY SFTP: {exc}") from exc

        return client

    def list_files(self, remote_dir: str) -> list[str]:
        """Return downloadable remote file names or raise if none exist."""

        client = self._connect()
        try:
            sftp = client.open_sftp()
            try:
                entries = sftp.listdir_attr(remote_dir)
            finally:
                sftp.close()
        except FileNotFoundError as exc:
            raise SftpNoFileError(f"Remote directory not found: {remote_dir}") from exc
        except SftpAuthError:
            raise
        except Exception as exc:
            raise SftpClientError(f"Failed to list remote files: {exc}") from exc
        finally:
            client.close()

        files = [entry.filename for entry in entries if stat.S_ISREG(entry.st_mode)]
        if not files:
            raise SftpNoFileError(f"No downloadable files found in {remote_dir}")
        return sorted(files)

    def download_file(self, remote_dir: str, remote_name: str, destination: str | Path) -> int:
        """Download one file and return the written byte count."""

        remote_path = posixpath.join(remote_dir.rstrip("/"), remote_name)
        destination_path = Path(destination)
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        client = self._connect()
        try:
            sftp = client.open_sftp()
            try:
                sftp.get(remote_path, str(destination_path))
            finally:
                sftp.close()
        except SftpAuthError:
            raise
        except Exception as exc:
            raise SftpClientError(f"Failed to download {remote_path}: {exc}") from exc
        finally:
            client.close()

        return destination_path.stat().st_size
