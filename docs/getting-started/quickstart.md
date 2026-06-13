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

## 4. Send one invoice in an online session

```bash
uv run ksef2 --env test --nip 5261040828 --test-cert \
  online send invoice.xml --wait
```

By default, `online send` opens a session, sends the invoice, and closes the
session. Add `--keep-open --save-state online-state.json` when you need to reuse
the session later.

## 5. Submit a batch

```bash
uv run ksef2 --env test --nip 5261040828 --test-cert \
  batch submit invoice-1.xml invoice-2.xml \
  --wait \
  --state-file batch-state.json
```

The saved state file can be reused with `batch status`, `batch list`, and
`batch upo`.

## Related pages

- [Authentication](../guides/authentication.md)
- [Configuration](../guides/configuration.md)
- [Invoice workflows](../guides/invoices.md)
- [Command reference](../reference/commands.md)
