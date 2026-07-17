# Bastion ingestion service

## Purpose
This service runs on the bastion EC2 and pulls files from the Aiva SFTP source into the bastion for later processing.

The goal is simple:
- extract the files from Aiva
- land them safely on the bastion
- keep them local only
- make them available for downstream processing without exposing credentials or changing the manual fallback process

## Data flow
1. Trigger the runner manually or by schedule.
2. Load runtime config from environment variables.
3. Read the SFTP credential reference from SSM Parameter Store.
4. Connect to the remote SFTP source.
5. List files and download new ones.
6. Stage them under `data/work/` and promote them to `data/archive/`.
7. Remove local files older than 90 days.
8. Emit JSON logs for each run.

## How it runs
- Entry point: `python -m scripts.run_ingestion`
- Config: environment variables + SSM parameter name in `BNY_SFTP_SECRET_ID`
- AWS region: use `AWS_REGION` or `AWS_DEFAULT_REGION` (defaults to `us-east-1`)
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
- No downloadable files: the run exits cleanly.
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
