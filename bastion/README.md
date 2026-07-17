# Bastion ingestion runtime

## Ownership
- The bastion ops team owns everything under `bastion/`.
- This slice is intentionally local-only and does not change downstream systems.

## Rollback / off switch
- Disable the cron/manual trigger for `scripts/run_ingestion.py`.
- Leave the manual BNY process in place; rollback is a config/off switch, not a data migration.

## Local-only retention
- Downloads are stored only under the bastion `data/work/` and `data/archive/` directories.
- `src/retention.py` removes files older than 90 days on every run.

## Operational note
- The trigger mode is still unresolved: schedule, on-demand, or both must be decided before the next apply slice.
- Manual operator path: invoke `python -m scripts.run_ingestion` or call `scripts.run_ingestion.main()` directly.
- The runtime reads the SFTP credential from SSM Parameter Store; `BNY_SFTP_SECRET_ID` is the parameter name, not a Secrets Manager identifier.

## Smoke checks
- See `tests/smoke_test_notes.md` for the two lightweight bastion smoke scenarios.
