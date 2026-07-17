# aiva-goldenhind

Ingestion service for the Aiva bastion EC2.

## Runtime contract
- Downloads only the Aiva report families it understands.
- Archives them under `data/archive/GoldenHind/` and `data/archive/Davinci/`.
- Keeps legacy `data/archive/<filename>` files valid for dedupe.
- Boots from `28/06` on the first run, then keeps only the current month.

## Flow
1. Load config and SSM secret.
2. Connect to Aiva SFTP.
3. Download new target files only.
4. Promote them into the routed archive folders.
5. Apply retention after each run.

## Goal
Keep extraction isolated on the bastion without changing the manual fallback path.
