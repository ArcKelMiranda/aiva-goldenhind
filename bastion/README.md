# Bastion ingestion runtime

## Purpose
Pull BNY files from the remote SFTP source and keep them only on the bastion.

## How it runs
- Entry point: `python -m scripts.run_ingestion`
- Config: environment variables + SSM parameter name in `BNY_SFTP_SECRET_ID`
- Storage: `data/work/` for staging, `data/archive/` for retained files
- Retention: files older than 90 days are removed on each run

## Inputs
- `BNY_SFTP_HOST`
- `BNY_SFTP_PORT`
- `BNY_SFTP_USERNAME`
- `BNY_SFTP_SECRET_ID` (SSM parameter name)
- `BNY_SFTP_REMOTE_DIR`
- `YHAT_BNY_LOCAL_ROOT`

## Behavior
- If the remote directory has no downloadable files, the run exits cleanly.
- If authentication or retrieval fails, the run fails closed and logs the error.
- Logs are JSON and written for bootstrap, file download, retention, and completion.

## Rollback
- Disable the cron/manual trigger for `scripts/run_ingestion.py`.
- Existing manual handling is unchanged.

## Smoke checks
- See `tests/smoke_test_notes.md`.
