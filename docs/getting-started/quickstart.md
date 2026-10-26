---
title: Quickstart
description: Authenticate in TEST, query invoice metadata, and send an invoice with KSeF2 CLI.
---

This quickstart uses the TEST environment and the SDK-generated TEST
certificate. Use a real XAdES certificate or KSeF token for DEMO and PRODUCTION.
The default environment is `test` already, so the `--env test` below is explicit
rather than required: a command that names no environment and no profile now talks to
TEST, never to production. An explicit `--env production`, or a profile with
`environment = "production"`, still means production.

## 1. Check the CLI

```bash
uv run ksef2 --help
uv run ksef2 --version
```

`--version` prints the CLI version and the `ksef2` SDK version it resolved, one per
line. It reads no config file and no credentials.

## 2. Create a TEST profile

Profiles keep repeated non-secret options in one local config file. The TEST
certificate auth method is useful for local development:

```bash
uv run ksef2 profile create test-company \
  --env test \
  --nip 5261040828 \
  --test-cert
```

Authenticate with that profile and print the token expiry times:

```bash
uv run ksef2 --profile test-company --json auth login
```

Neither token value is in that output. Text mode prints `access_token: **********`
and JSON mode prints `"token": "**********"`, each with its `valid_until`, so there is
nothing to scrub from a log and nothing to reuse. To keep the credential for later
commands, save it:

```bash
uv run ksef2 --profile test-company --json auth login --save-state ksef2-auth.json
```

The saved file holds the bearer tokens in plain text and is written with mode `0600`.
That mode keeps other users out; it does not encrypt the file, so keep it outside the
repository and out of any commit.

Global options such as `--profile`, `--env`, `--nip`, `--test-cert`, and
`--json` must appear before the command group.

To reuse that state instead of logging in per command, point the global `--auth-state`
option at the file, as in `ksef2 --profile test-company --auth-state ksef2-auth.json
--json auth logout`. See
[Authentication](../guides/authentication.md#reuse-a-saved-authentication).

## 3. Query invoice metadata

```bash
uv run ksef2 --profile test-company --json \
  invoices metadata \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --all
```

For token authentication in CI, skip the profile and pass direct root options, with
the environment named explicitly:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  invoices metadata \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --all
```

## 4. Send one invoice and get a UPO

Need an invoice XML to send? `fa3 draft-example` and `fa3 build` create one
locally, without any credentials. See [FA(3) invoices locally](../guides/fa3.md).

```bash
uv run ksef2 --profile test-company \
  invoices send invoice.xml \
  --wait \
  --upo-dir upos \
  --receipt invoice-receipt.json
```

By default, `invoices send` uses online mode. The receipt file lets you check
status or download the UPO later without managing the underlying session:

```bash
uv run ksef2 --profile test-company \
  invoices status --receipt invoice-receipt.json --wait

uv run ksef2 --profile test-company \
  invoices upo --receipt invoice-receipt.json --out invoice-upo.xml
```

## 5. Send a directory or batch

```bash
uv run ksef2 --profile test-company \
  invoices send invoices/ --receipt-dir receipts
```

Directory input includes direct child `*.xml` files. Add `--recursive` for nested
directories. Use `--mode batch` when the files should be submitted as one batch:

```bash
uv run ksef2 --profile test-company \
  invoices send invoices/ --mode batch --wait --upo-dir upos
```

A receipt file is continuation state, not a log: an online receipt carries the session
AES key and IV in plain text, so the CLI writes receipts with mode `0600` and they
belong outside the repository, like auth state.

If a send is interrupted, or `--wait` runs out of time, that is not proof the invoice
was not submitted: KSeF may already hold it. Read the receipt, or ask with `invoices
status --receipt FILE`, before sending the same XML again.

## What the CLI prints

A successful command writes to stdout: plain text by default, one JSON document with
`--json`. Command errors go to stderr and leave stdout empty. A completed
`invoices send` with rejected items writes its result to stdout and exits 1.
In JSON mode a command error is one object:

```json
{"error": {"code": "RemoteServiceError", "message": "...", "ksef_code": 21405, "trace_id": "..."}}
```

`code` names the CLI error class, or `USAGE_ERROR` when the command line itself was
rejected. `ksef_code` and `trace_id` are KSeF's own numbers, and both are `null` when
the request never reached KSeF. API failures add `status_code`; `details` and `hints`
are present only when the CLI has them.

| Exit code | Meaning |
| --- | --- |
| `0` | Success. |
| `1` | Runtime failure: a rejected request, a KSeF timeout, missing or contradictory credentials, a bad file. |
| `2` | Usage failure: unknown option, missing argument, or an invalid value such as a bad NIP checksum. |
| `130` | Interrupted with Ctrl-C, which does not roll back anything KSeF already accepted. |

`invoices send` exits `1` when any file failed, after printing every per-file result.

## Related pages

- [Authentication](../guides/authentication.md)
- [Configuration](../guides/configuration.md)
- [Invoice workflows](../guides/invoices.md)
- [FA(3) invoices locally](../guides/fa3.md)
- [Collective identifiers](../guides/collective.md)
- [Command reference](../reference/commands.md)
