---
title: Invoice Workflows
description: Query, download, export, send, and batch invoices with KSeF2 CLI.
---

Invoice workflows use the `invoices`, `online`, and `batch` command groups.
Use `--json` when commands are part of a script or CI job.

## Query metadata

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices metadata \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --date-to 2026-01-31T23:59:59Z \
  --all \
  --json
```

Useful filters include:

- `--role`
- `--date-type`
- `--amount-type`
- `--seller-nip`
- `--buyer-nip`
- `--invoice-number`
- `--ksef-number`
- `--form`
- `--attachment yes|no`
- `--self-invoicing yes|no`

## Download one processed invoice

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices download \
  --ksef-number "$KSEF_NUMBER" \
  --out invoice.xml
```

Add `--wait` when the invoice may not be ready yet:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices download \
  --ksef-number "$KSEF_NUMBER" \
  --wait \
  --timeout 120 \
  --poll-interval 2
```

## Schedule and fetch an export

First schedule the export and save its decryption handle:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices export \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --handle-file export-handle.json \
  --json
```

Check status:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices export-status --reference "$EXPORT_REFERENCE"
```

Fetch and decrypt the package:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices export-fetch \
  --handle-file export-handle.json \
  --wait \
  --out-dir downloads
```

For a one-command export/download flow:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices export-download \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --wait \
  --out-dir downloads
```

## Send invoices through an online session

The short path opens a session, sends invoices, and closes the session:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  online send invoice.xml --wait
```

To reuse a session, save its state:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  online send invoice-1.xml invoice-2.xml \
  --keep-open \
  --save-state online-state.json
```

Then inspect or close it:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  online status --state-file online-state.json

uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  online close --state-file online-state.json
```

## Submit and inspect a batch

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  batch submit invoice-1.xml invoice-2.xml \
  --wait \
  --state-file batch-state.json
```

Check status or list invoices:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  batch status --state-file batch-state.json

uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  batch list --state-file batch-state.json --failed
```

Download a batch UPO page:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  batch upo \
  --state-file batch-state.json \
  --upo-reference "$UPO_REFERENCE" \
  --out batch-upo.xml
```
