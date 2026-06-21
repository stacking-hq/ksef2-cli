---
title: Quickstart
description: Authenticate in TEST, query invoice metadata, and send an invoice with KSeF2 CLI.
---

This quickstart uses the TEST environment and the SDK-generated TEST
certificate. Use a real XAdES certificate or KSeF token for DEMO and PRODUCTION.

## 1. Check the CLI

```bash
uv run ksef2 --help
```

## 2. Authenticate

Global authentication options must appear before the command group:

```bash
uv run ksef2 --env test --nip 5261040828 --test-cert auth login --json
```

The command authenticates with a TEST certificate and prints the SDK auth token
payload. Use `--json` for scripts.

## 3. Query invoice metadata

```bash
uv run ksef2 --env test --nip 5261040828 --test-cert \
  invoices metadata \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --all \
  --json
```

For token authentication, replace `--test-cert` with `--token "$KSEF2_TOKEN"`.

## 4. Send one invoice and get a UPO

```bash
uv run ksef2 --env test --nip 5261040828 --test-cert \
  invoices send invoice.xml \
  --wait \
  --upo-dir upos \
  --receipt invoice-receipt.json
```

By default, `invoices send` uses online mode. The receipt file lets you check
status or download the UPO later without managing the underlying session:

```bash
uv run ksef2 --env test --nip 5261040828 --test-cert \
  invoices status --receipt invoice-receipt.json --wait

uv run ksef2 --env test --nip 5261040828 --test-cert \
  invoices upo --receipt invoice-receipt.json --out invoice-upo.xml
```

## 5. Send a directory or batch

```bash
uv run ksef2 --env test --nip 5261040828 --test-cert \
  invoices send invoices/ --receipt-dir receipts
```

Directory input includes direct child `*.xml` files. Add `--recursive` for nested
directories. Use `--mode batch` when the files should be submitted as one batch:

```bash
uv run ksef2 --env test --nip 5261040828 --test-cert \
  invoices send invoices/ --mode batch --wait --upo-dir upos
```

## Related pages

- [Authentication](../guides/authentication.md)
- [Configuration](../guides/configuration.md)
- [Invoice workflows](../guides/invoices.md)
- [Command reference](../reference/commands.md)
