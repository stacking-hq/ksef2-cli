---
title: Tokens
description: Generate, list, check, and revoke KSeF authorization tokens with KSeF2 CLI, then store the result for token authentication.
---

A KSeF token is a reusable credential with a fixed permission set. Automation
prefers tokens because the machine that runs the job needs neither a certificate
nor a private key. The `tokens` group covers the lifecycle: generate, list,
check one token, revoke. Using a token to authenticate is a different job and
belongs to [Authentication](authentication.md).

KSeF issues a token to a context that authenticated with a certificate, so
`tokens generate` runs with XAdES credentials or a TEST certificate. The value it
returns is what your scripts authenticate with afterwards. The permission set is
fixed at generation: to change what a token can do, generate a new one and
revoke the old one.

## Generate a token

```bash
uv run ksef2 --env test --nip 5261040828 --test-cert --json \
  tokens generate \
  --description "nightly invoice export" \
  --permission invoice_read
```

```json
{
  "reference_number": "20260625-TOKEN-...",
  "token": "ONE_TIME_VALUE",
  "status": null
}
```

`--description` and at least one `--permission` are required. Repeat
`--permission` for a wider set. The eight accepted values are the API's own
names:

```text
invoice_read       invoice_write          introspection        credentials_read
credentials_manage subunit_manage         enforcement_operations
collective_identifier_manage
```

What each one opens is KSeF's decision, and the name is all the CLI can tell you
about it, so start from the single operation the job must perform and grant the
narrowest name that covers it. Some names line up with command groups in this
CLI, which helps when you are choosing: `invoice_read` and `invoice_write` with
`invoices`, `collective_identifier_manage` with `collective`,
`credentials_read` and `credentials_manage` with `tokens` and `certificates`.

A token that authenticates correctly still fails a call outside its set.

The `token` value is KSeF's only delivery of the secret. Later commands
identify the token by `reference_number` and cannot recover the value, so write
it down as the output appears. Treat stdout as secret material for this command:
keep it out of logs, transcripts, and issue threads.

In text mode the same fields print one per line. The `status` line is missing
until you wait for activation, because text output leaves out empty fields:

```text
reference_number: 20260625-TOKEN-...
token: ONE_TIME_VALUE
```

## Wait for activation

A new token is not active the instant it is returned. `--wait` polls until KSeF
reports it active:

```bash
uv run ksef2 --profile prod-xades --auth-timeout 120 --auth-poll-interval 2 \
  tokens generate \
  --description "billing worker" \
  --permission invoice_read \
  --permission invoice_write \
  --wait
```

The wait budget is `--auth-timeout` seconds, default `60`, checked every
`--auth-poll-interval` seconds, default `1`. A profile that sets
`max_poll_attempts` supplies a budget of `max_poll_attempts` times its
`poll_interval` when you leave `--auth-timeout` out. See
[Polling options](authentication.md#polling-options).

Polling happens after KSeF returned the credential and before the CLI prints
anything, so a timeout, or a status of `failed` or `revoked`, ends the command
with an error and the token value never reaches your terminal. When losing that
value matters, split the work in two: generate without `--wait`, store the
secret, then poll with `tokens status`.

## Check one token

```bash
uv run ksef2 --profile prod-token --json \
  tokens status --reference "$TOKEN_REFERENCE"
```

```json
{
  "reference_number": "20260625-TOKEN-...",
  "status": "active"
}
```

Statuses are `pending`, `active`, `revoking`, `revoked`, and `failed`.

## List tokens

```bash
uv run ksef2 --profile prod-token tokens list \
  --status active \
  --page-size 50
```

Filters: `--status` (repeat for several statuses), `--description`, and
`--author-identifier` combined with `--author-identifier-type` of `nip`,
`pesel`, or `fingerprint`. `--page-size` accepts 10 to 100 and `--all` walks
every page. Unlike other listing commands, this one has no `--page-offset`, so
you get the first page or, with `--all`, the whole result.

Text output prints one `key=value` row per token:

```text
reference_number=20260625-TOKEN-... status=active description=nightly invoice export author_identifier=nip:5261040828 context_identifier=nip:5261040828 requested_permissions=invoice_read date_created=2026-06-25T10:00:00+00:00
```

Empty fields disappear from the row rather than printing blanks, and
`last_use_date` is often absent for a token that has never been used. Add
`--json` when a script reads these fields.

## Revoke a token

```bash
uv run ksef2 --profile prod-token --json \
  tokens revoke --reference "$TOKEN_REFERENCE"
```

```json
{
  "reference_number": "20260625-TOKEN-...",
  "revoked": true
}
```

The response means KSeF accepted the revocation. Run `tokens status` and wait
for `revoked` before you delete the last copy of the secret.

## Store a token for later commands

Keep the two halves apart. The value goes to a secret store or an environment
variable, and the reference goes wherever you keep the job's configuration.

```bash
export KSEF2_TOKEN='ONE_TIME_VALUE'

uv run ksef2 profile create billing-worker \
  --env production \
  --nip "$KSEF2_NIP" \
  --token-env KSEF2_TOKEN
```

The profile stores the variable name `KSEF2_TOKEN`, never the value, so nothing
secret lands in the config file. To use the token for one command only, skip the
profile:

```bash
uv run ksef2 --env production --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  invoices metadata \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --all
```

A `context_type` other than `nip` needs the root `--context-type` option or the
`KSEF2_CONTEXT_TYPE` variable, as described in
[Token authentication](authentication.md#token-authentication).

Save the reference number as soon as you have it. `tokens status` and
`tokens revoke` need it, and nothing in the CLI turns a reference back into a
token or a token back into a reference.

## Related pages

- [Authentication](authentication.md)
- [Permissions](permissions.md)
- [Configuration](configuration.md)
- [Command reference](../reference/commands.md)
