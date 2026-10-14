---
title: Limits
description: Read the KSeF context, subject, and API rate limits that apply to you, and manage the TEST-environment limit overrides with KSeF2 CLI.
---

Limits decide how big a batch you may send, how often you may call, and how many
certificates you may hold. The `limits` group reads the numbers KSeF applies to
the current context and, in TEST only, overrides them. Read the effective values
before you choose a batch size or a retry interval, because hard-coding the
defaults from documentation breaks the day a context gets different ones.

Three kinds exist, and the same three words name them everywhere in this group:

| Kind | Covers |
| --- | --- |
| `context` | Session size caps for online and batch sending, plus collective identifier caps. |
| `subject` | Certificate and enrollment counts for this subject. |
| `api` | Request rates per endpoint group, per second, minute, and hour. |

## Read effective limits

```bash
uv run ksef2 --profile prod-token --json limits get context
```

```json
{
  "online_session": {
    "max_invoice_size_mb": 10,
    "max_invoice_with_attachment_size_mb": 20,
    "max_invoices": 100
  },
  "batch_session": {
    "max_invoice_size_mb": 10,
    "max_invoice_with_attachment_size_mb": 20,
    "max_invoices": 1000
  },
  "collective_identifier": {
    "max_invoices": 10
  }
}
```

`batch_session.max_invoices` is the number of invoices one batch session may
carry and `max_invoice_size_mb` is the per-invoice ceiling, so those two numbers
set the package size for `invoices send --mode batch` and the `batch` group.

The other two reads:

```bash
uv run ksef2 --profile prod-token --json limits get subject
```

```json
{
  "certificate": {
    "max_certificates": 5
  },
  "enrollment": {
    "max_enrollments": 3
  }
}
```

Both objects are optional in the response, so a subject that has no per-subject
cap reports neither of them. `certificates limits` reports what KSeF will let you
do right now, including what is already used, which makes it the better check
before an enrollment run.

```bash
uv run ksef2 --profile prod-token --json limits get api
```

The API read returns one object per endpoint group, each with `per_second`,
`per_minute`, and `per_hour`. This is the shape; the numbers are yours to read:

```json
{
  "invoice_send": { "per_second": 2, "per_minute": 60, "per_hour": 2000 }
}
```

Every one of these groups appears in the response: `online_session`,
`online_session_close`, `batch_session`, `batch_session_close`, `invoice_send`,
`invoice_status`, `session_list`, `session_invoice_list`, `session_misc`,
`invoice_metadata`, `invoice_export`, `invoice_export_status`,
`invoice_download`, `collective_identifier`, `other`, `anonymous`, and
`global_`. The last one is the ceiling over the rest, so raising a single group
gets you that far and no further.

In text mode each nested object prints as one compact JSON value on its own line,
which is enough to read but awkward to parse. Use `--json` and `jq` when a script
needs a number:

```bash
uv run ksef2 --profile prod-token --json limits get api | jq '.invoice_send.per_minute'
```

## Override limits in TEST

`limits set` and `limits reset` change the numbers KSeF applies to your TEST
context. They are administrative operations, and they hold for every other
process using that context. KSeF accepts them only from a context allowed to
manage limits, so an ordinary TEST subject gets an error back. Keep them in the
runbook next to the step that resets them, and never call them from
invoice-sending code.

`limits set` reads the new values from a JSON file named by `--payload`. The file
must satisfy the same model the read command returns, which means a partial
payload fails rather than patching a single field.

Context overrides need all three groups. In `context.json`:

```json
{
  "online_session": {
    "max_invoice_size_mb": 10,
    "max_invoice_with_attachment_size_mb": 20,
    "max_invoices": 100
  },
  "batch_session": {
    "max_invoice_size_mb": 10,
    "max_invoice_with_attachment_size_mb": 20,
    "max_invoices": 1000
  },
  "collective_identifier": {
    "max_invoices": 10
  }
}
```

```bash
uv run ksef2 --env test --profile test-admin --json \
  limits set context --payload context.json
```

```json
{
  "kind": "context",
  "updated": true
}
```

Subject overrides are the least demanding, because both objects are optional. In
`subject.json`:

```json
{
  "certificate": { "max_certificates": 5 },
  "enrollment": { "max_enrollments": 3 }
}
```

```bash
uv run ksef2 --env test --profile test-admin --json \
  limits set subject --payload subject.json
```

API overrides need every group listed above, each with all three windows, so the
practical way to build that file is to read the current values and edit them:

```bash
uv run ksef2 --env test --profile test-admin --json \
  limits get api > api.json

uv run ksef2 --env test --profile test-admin --json \
  limits set api --payload api.json
```

## Read a limit back after setting it

`limits set` reports that the call succeeded, nothing more. Always confirm with
the matching read:

```bash
uv run ksef2 --env test --profile test-admin --json limits get context
```

If the override did not take, the read returns the value KSeF applies anyway, so
this is also how you find out your subject cannot override at all.

## Reset overrides

Reset drops the override and goes back to the environment default:

```bash
uv run ksef2 --env test --profile test-admin --json limits reset subject
```

```json
{
  "kind": "subject",
  "reset": true
}
```

The reset command takes `api`, `session`, and `subject`, while `limits get` and
`limits set` take `api`, `context`, and `subject`. Session and context name the
same thing under two different words, so `limits set context` pairs with
`limits reset session`. Reading the wrong kind in the wrong command fails on the
choice list before anything is sent.

## Copy production rates into TEST

Rate-limit tests need production-like numbers, and typing them by hand is how you
end up testing something else. This command asks KSeF to apply the production
defaults to the TEST API limits in one call:

```bash
uv run ksef2 --env test --profile test-admin --json \
  limits production-rate-limits
```

```json
{
  "api_rate_limits": "production"
}
```

It replaces the API overrides only. Context and subject limits keep whatever you
set for them, and `limits reset api` moves them back again.

## Related pages

- [Certificates](certificates.md)
- [Invoice workflows](invoices.md)
- [Configuration](configuration.md)
- [Command reference](../reference/commands.md)
