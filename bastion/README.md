# Bastion ingestion service

## Purpose
This service runs on the bastion EC2 and pulls files from the Aiva SFTP source into the bastion for later processing.

The goal is simple:
- extract only the `EnhancedTransactionReportInclFX...` files from Aiva
- land them safely on the bastion
- keep them local only
- make them available for downstream processing without exposing credentials or changing the manual fallback process
- bootstrap from `28/06` onward
- keep only the current month after that

## Data flow
1. Trigger the runner manually or by schedule.
2. Load runtime config from environment variables.
3. Read the SFTP credential reference from SSM Parameter Store.
4. Connect to the remote SFTP source.
5. List files and download only the ones that are not already present in `data/archive/`.
6. Stage them under `data/work/` and promote them to `data/archive/`.
7. Remove files from previous months and keep only the current month.
8. Emit JSON logs for each run.

## How it runs
- Entry point: `python -m scripts.run_ingestion`
- Config: environment variables + SSM parameter name in `BNY_SFTP_SECRET_ID`
- AWS region: use `AWS_REGION` or `AWS_DEFAULT_REGION` (defaults to `us-east-1`)
- Host keys: Paramiko reads `~/.ssh/known_hosts` by default; override with `BNY_SSH_KNOWN_HOSTS` if needed
- Storage: `data/work/` for staging, `data/archive/` for retained files
- Retention: only the current month is kept on each run

## Inputs
- `BNY_SFTP_HOST`
- `BNY_SFTP_PORT`
- `BNY_SFTP_USERNAME`
- `BNY_SFTP_SECRET_ID` (SSM parameter name)
- `BNY_SFTP_REMOTE_DIR`
- `YHAT_BNY_LOCAL_ROOT`

## Behavior
- No downloadable files or all files already archived: the run exits cleanly.
- Files outside the `EnhancedTransactionReportInclFX...` prefix are ignored.
- Auth or connection failure: the run fails closed and logs the error.
- All operational events are emitted as JSON logs.

## Output on the bastion
- `data/work/` for temporary staging
- `data/archive/` for retained files
- logs for execution status and retention

## Rollback
- Disable the cron/manual trigger for `scripts/run_ingestion.py`.
- The existing manual process remains available.

## Smoke checks
- See `tests/smoke_test_notes.md`.
