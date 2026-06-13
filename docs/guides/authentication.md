---
title: Authentication
description: Configure KSeF2 CLI authentication with tokens, TEST certificates, PEM XAdES credentials, or PKCS#12 archives.
---

Authenticated commands create an SDK client for one operation, authenticate it
with the selected method, run the command, and close the client. Authentication
settings are global options, so they must appear before the command group.

## Choose one method

Provide exactly one authentication method:

| Method | Options | Environment variables |
| --- | --- | --- |
| KSeF token | `--token`, `--ksef-token` | `KSEF2_TOKEN` |
| TEST certificate | `--test-cert` | `KSEF2_TEST_CERT` |
| PEM XAdES credentials | `--cert`, `--key`, optional `--key-password` | `KSEF2_CERT`, `KSEF2_KEY`, `KSEF2_KEY_PASSWORD` |
| PKCS#12/PFX XAdES archive | `--p12`, optional `--p12-password` | `KSEF2_P12`, `KSEF2_P12_PASSWORD` |

All authenticated methods also need a taxpayer or context NIP:

```bash
--nip 5261040828
```

or:

```bash
export KSEF2_NIP=5261040828
```

## Token authentication

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices metadata --role seller --date-from 2026-01-01T00:00:00Z
```

Use `--context-type` or `KSEF2_CONTEXT_TYPE` when token authentication needs a
context other than the default `nip`.

## TEST certificate authentication

```bash
uv run ksef2 --env test --nip 5261040828 --test-cert auth login --json
```

This method is for TEST environment workflows only.

## PEM XAdES credentials

```bash
uv run ksef2 --nip "$KSEF2_NIP" \
  --cert cert.pem \
  --key private-key.pem \
  invoices metadata --role seller --date-from 2026-01-01T00:00:00Z
```

For encrypted private keys, pass `--key-password` or set
`KSEF2_KEY_PASSWORD`.

## PKCS#12/PFX credentials

```bash
uv run ksef2 --nip "$KSEF2_NIP" \
  --p12 signing-credentials.p12 \
  --p12-password "$KSEF2_P12_PASSWORD" \
  auth login --json
```

## Refresh an access token

```bash
uv run ksef2 auth refresh --refresh-token "$KSEF2_REFRESH_TOKEN" --json
```

`auth refresh` does not require the other global authentication method options.

## Polling options

Authentication commands use polling while KSeF processes authentication:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  --auth-poll-interval 2 \
  --auth-max-poll-attempts 90 \
  auth login
```

## Precedence

When a setting is available in multiple places, the CLI resolves it in this
order:

1. CLI option
2. Environment variable
3. Local config file

Use `--no-config` to ignore local config defaults for one invocation.
