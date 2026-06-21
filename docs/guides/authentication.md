---
title: Authentication
description: Configure KSeF2 CLI authentication with profiles, tokens, TEST certificates, PEM XAdES credentials, or PKCS#12 archives.
---

Authenticated commands create an SDK client for one operation, authenticate it
with the selected method, run the command, and close the client. For developer
workstations, prefer profiles. For CI and one-off scripts, pass direct root
options or environment variables.

Root options must appear before the command group:

```bash
ksef2 [ROOT OPTIONS] invoices metadata [COMMAND OPTIONS]
```

## Profiles for local work

Create one profile per KSeF subject or context. Profiles store non-secret
defaults such as environment, NIP, auth method, certificate paths, polling
settings, and the names of secret environment variables.

For TEST work with the SDK-generated certificate:

```bash
uv run ksef2 profile create test-company \
  --env test \
  --nip 5261040828 \
  --test-cert
```

For token auth, store the environment variable name, not the token value:

```bash
uv run ksef2 profile create prod-token \
  --env production \
  --nip "$KSEF2_NIP" \
  --token-env KSEF2_TOKEN
```

For PEM XAdES credentials:

```bash
uv run ksef2 profile create demo-pem \
  --env demo \
  --nip "$KSEF2_NIP" \
  --cert company.pem \
  --key company.key \
  --key-password-env KSEF2_KEY_PASSWORD
```

For PKCS#12/PFX credentials:

```bash
uv run ksef2 profile create prod-p12 \
  --env production \
  --nip "$KSEF2_NIP" \
  --p12 signing-credentials.p12 \
  --p12-password-env KSEF2_P12_PASSWORD
```

`profile create` selects the new profile by default. Use a different profile for
one command with `--profile`, or for the current shell with `KSEF2_PROFILE`:

```bash
uv run ksef2 --profile prod-token --json auth login

export KSEF2_PROFILE=test-company
uv run ksef2 --json invoices metadata \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --all
```

`KSEF2_PROFILE` selects runtime settings. It does not rewrite the saved
`active_profile`; use `ksef2 profile use NAME` when you want to persist the
selection in the config file.

## Direct auth for scripts

Provide exactly one authentication method in root options or environment
variables:

| Method | Root options | Environment variables |
| --- | --- | --- |
| KSeF token | `--token`, `--ksef-token` | `KSEF2_TOKEN` |
| TEST certificate | `--test-cert` | `KSEF2_TEST_CERT` |
| PEM XAdES credentials | `--cert`, `--key`, optional `--key-password` | `KSEF2_CERT`, `KSEF2_KEY`, `KSEF2_KEY_PASSWORD` |
| PKCS#12/PFX archive | `--p12`, optional `--p12-password` | `KSEF2_P12`, `KSEF2_P12_PASSWORD` |

Most authenticated methods also need a taxpayer or context NIP:

```bash
export KSEF2_NIP=5261040828
```

## Token authentication

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  invoices metadata \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --all
```

Use `--context-type` or `KSEF2_CONTEXT_TYPE` when token authentication needs a
context other than the default `nip`.

## TEST certificate authentication

```bash
uv run ksef2 --env test --nip 5261040828 --test-cert --json auth login
```

This method is only for TEST environment workflows.

## PEM XAdES credentials

```bash
uv run ksef2 --nip "$KSEF2_NIP" \
  --cert cert.pem \
  --key private-key.pem \
  --json auth login
```

For encrypted private keys, pass `--key-password` or set
`KSEF2_KEY_PASSWORD`.

## PKCS#12/PFX credentials

```bash
uv run ksef2 --nip "$KSEF2_NIP" \
  --p12 signing-credentials.p12 \
  --p12-password "$KSEF2_P12_PASSWORD" \
  --json auth login
```

## Refresh an access token

```bash
uv run ksef2 --json auth refresh --refresh-token "$KSEF2_REFRESH_TOKEN"
```

`auth refresh` does not require the other root authentication method options.

## Polling options

Authentication commands poll while KSeF processes authentication. Use root
options to override the profile or default polling settings:

```bash
uv run ksef2 --profile prod-token \
  --auth-poll-interval 2 \
  --auth-max-poll-attempts 90 \
  --json auth login
```

## Precedence

When a setting is available in multiple places, the CLI resolves it in this
order:

1. CLI option.
2. Environment variable.
3. Selected profile.
4. Built-in default.

Use `--no-config` to ignore profiles for one invocation.
