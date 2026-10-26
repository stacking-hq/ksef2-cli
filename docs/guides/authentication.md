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

## Which environment a login lands on

The default environment is `test`. A selected profile supplies the environment when
you do not pass `--env`, and `--env` overrides the profile, so nothing here changed for
production work: `--env production` still authenticates against production, and so does
a profile with `environment = "production"`. What changed is the fallback, so a
credential that was aimed at production by omission now reaches TEST. Name the
environment, or the profile that carries it, in any command you script or paste.

A TEST certificate is valid in TEST only. Asking for `--test-cert` against another
environment fails with exit `2` before any request is sent, and so does a profile that
combines `test_certificate` auth with a non-TEST environment. Pass a real credential
to displace that profile method and keep its other defaults.

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
| Saved auth state | `--auth-state` | `KSEF2_AUTH_STATE` |

Most authenticated methods also need a taxpayer or context NIP:

```bash
export KSEF2_NIP=5261040828
```

## Token authentication

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
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
uv run ksef2 --env production --nip "$KSEF2_NIP" \
  --cert cert.pem \
  --key private-key.pem \
  --json auth login
```

For encrypted private keys, pass `--key-password` or set
`KSEF2_KEY_PASSWORD`.

## PKCS#12/PFX credentials

```bash
uv run ksef2 --env production --nip "$KSEF2_NIP" \
  --p12 signing-credentials.p12 \
  --p12-password "$KSEF2_P12_PASSWORD" \
  --json auth login
```

## Refresh an access token

Point the global `--auth-state` option at a saved state file and the CLI takes the
refresh token from the file:

```bash
uv run ksef2 --env production --auth-state "$XDG_RUNTIME_DIR/ksef2-auth.json" --json auth refresh
```

That is the form to use in a script. `auth refresh` also accepts
`--refresh-token`, and the environment variable `KSEF2_REFRESH_TOKEN`, for a state file
you do not have; a token in a command line is visible to every process on the machine
and lands in your shell history, so prefer the file. The two sources are exclusive,
and the check runs before any request is sent.

The answer is masked in both output modes, the same way `auth login` masks it: the new
access token reads `**********` in text and in JSON, with its `valid_until` beside it,
which is why `--save-state FILE` exists to keep the refreshed value. With `--auth-state`
and no `--save-state`, the refreshed state replaces the source file in place. A copy
written anywhere else needs that same state file, because only it still carries the
refresh token and its expiry; `--save-state` without `--auth-state` stops with an error
rather than saving state that would lose that expiry:

```bash
uv run ksef2 --env production --auth-state "$XDG_RUNTIME_DIR/ksef2-auth.json" --json \
  auth refresh --save-state ./refreshed.json
```

`auth refresh` does not require the other root authentication method options.

## Reuse a saved authentication

`auth login` reports expiries and masks both token values in both output modes: text
prints `access_token: **********` and `refresh_token: **********`, and JSON prints
`"token": "**********"` inside each object. The masked fields are the whole answer, so
a captured login output is useless as a credential.

`auth login --save-state` is what keeps the credential. It writes the SDK authentication
resume state, which holds the access and refresh tokens as **plain-text bearer tokens**
plus their expiry times. The CLI creates the file with mode `0600` and treats it as
credential material: that mode keeps other users on the machine from opening it and
encrypts nothing, so a readable copy on a shared volume, in a backup, in a container
layer, or in a commit is a leaked credential whatever its permissions were on the way
there. Store it somewhere private, `"$XDG_RUNTIME_DIR"` on a shared workstation, and
outside any repository:

```bash
uv run ksef2 --profile prod-token --json \
  auth login --save-state "$XDG_RUNTIME_DIR/ksef2-auth.json"
```

`auth resume` reads that file back. It exchanges the access token for a new one
through the refresh endpoint when the saved access token expired while the
refresh token is still valid:

```bash
uv run ksef2 --env production --json auth resume --state-file "$XDG_RUNTIME_DIR/ksef2-auth.json"
```

Like `auth login`, `auth resume` masks both token values in text and in JSON and
reports only the expiries, so use `--save-state` when a script needs the refreshed
state. Written back to the file it read, it keeps mode `0600`.

Any other command can reuse the same state by pointing the global `--auth-state`
option, or `KSEF2_AUTH_STATE`, at it instead of naming an authentication method:

```bash
uv run ksef2 --env production --auth-state "$XDG_RUNTIME_DIR/ksef2-auth.json" --json \
  invoices metadata \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --all
```

A state file records tokens, not the environment those tokens were issued in. The
environment still comes from `--env` or a profile, so a reused state needs the same
environment it was logged in with, and with neither named that is now TEST.

`--auth-state` is one authentication method among the others, so combining it
with `--token`, `--test-cert`, `--cert`/`--key`, or `--p12` fails. A command that
reuses the state refreshes its own access token and writes the state it ends with
back to the same file, so the file stays current and keeps mode `0600`; a command
that fails leaves the file as it was. When the saved refresh token has also
expired, the command stops and asks for a new `auth login --save-state`.

`auth logout` ends the KSeF session behind a state file and deletes the file:

```bash
uv run ksef2 --env production --auth-state "$XDG_RUNTIME_DIR/ksef2-auth.json" --json auth logout
```

KSeF has to accept the termination first, so a state it rejects or reports as
expired keeps its file on disk for you to remove yourself. The command speaks for
that one authentication session, which is what it asks KSeF to end; it is not a
statement about any other token or session the same subject holds.

## Polling options

Authentication commands poll while KSeF processes authentication. Use root
options to override the profile or default polling settings:

```bash
uv run ksef2 --profile prod-token \
  --auth-poll-interval 2 \
  --auth-timeout 180 \
  --json auth login
```

`--auth-timeout` is the total number of seconds to wait for authentication to
finish; `--auth-poll-interval` is the delay between checks. Without them, a
profile's own `poll_interval` and `max_poll_attempts` decide both values, and a
profile without either waits the default `60` seconds in `1`-second checks.

## Precedence

When a setting is available in multiple places, the CLI resolves it in this
order:

1. CLI option.
2. Environment variable.
3. Selected profile.
4. Built-in default, which for the environment is `test`.

Use `--no-config` to ignore profiles for one invocation. It conflicts with
`--profile`, which exits `2` rather than silently dropping the profile.
