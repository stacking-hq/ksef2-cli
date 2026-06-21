---
title: Invoice Workflows
description: Query, download, export, send, and batch invoices with KSeF2 CLI.
---

Invoice workflows usually start with the `invoices` command group. Use the
lower-level `online` and `batch` groups only when you need explicit session
control. Use `--json` when commands are part of a script or CI job.

## Query metadata

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  invoices metadata \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --date-to 2026-01-31T23:59:59Z \
  --all
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
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  invoices export \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --handle-file export-handle.json
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

## Send invoices

By default, `invoices send` opens an online session, sends the XML file, closes
the session, and prints one line per invoice:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  invoices send invoice.xml
```

Wait for final processing and download the UPO into a directory:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  invoices send invoice.xml \
  --wait \
  --upo-dir upos
```

Save a receipt when you need to check status or download the UPO later:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  invoices send invoice.xml \
  --receipt invoice-receipt.json

uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  invoices status --receipt invoice-receipt.json --wait

uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  invoices upo --receipt invoice-receipt.json --out invoice-upo.xml
```

Send every XML file directly inside a directory:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  invoices send invoices/ --receipt-dir receipts
```

Add `--recursive` to include nested directories. If any file fails in online
mode, the command still attempts the remaining files and exits non-zero after
printing the per-file results.

## Send invoices as a batch

Use `--mode batch` when the input files should be prepared and submitted as one
batch session:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices send invoices/ \
  --mode batch \
  --wait \
  --upo-dir upos \
  --receipt batch-receipt.json
```

A batch receipt can be reused for status and UPO downloads:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices status --receipt batch-receipt.json --wait

uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices upo --receipt batch-receipt.json --upo-dir upos
```

## Advanced session commands

Use the `online` group when you need to keep an online session open:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  online send invoice-1.xml invoice-2.xml \
  --keep-open \
  --save-state online-state.json

uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  online status --state-file online-state.json

uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  online close --state-file online-state.json
```

Use the `batch` group when you need direct access to batch session state:

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
