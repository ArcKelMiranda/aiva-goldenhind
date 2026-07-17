# Bastion smoke test notes

## Scenario 1: Successful pull
- Set the bastion local root to a temp directory.
- Provide a mock SSM Parameter Store payload and a remote listing with one file.
- Expected: the file lands in `data/archive/`, the logs include `file_downloaded`, and the final summary is `success`.

## Scenario 2: No-file run
- Use the same setup, but return an empty remote listing.
- Expected: no archive file is created, the logs include `ingestion_no_file`, and the final summary is `no_file`.
