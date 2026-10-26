---
title: Sessions and UPO
description: Check what happened to submitted invoices, download the UPO that proves them, and find sessions and authentication sessions again with KSeF2 CLI.
---

Sending is only half of the workflow. Afterwards you need two answers: what KSeF
did with the invoices, and the UPO document that proves each accepted invoice. The
`sessions` group is what you use once the sending process is gone. It reads the UPO
of any past session, lists online and batch sessions KSeF still remembers, and shows
the authentication sessions your credential holds open.

Status answers are safe to log. Session state files, receipts, and prepared batch
directories carry session keys, so keep them like credentials and never paste them
into a report. See [Invoice workflows](invoices.md#advanced-session-commands).

## Which UPO command fits

Pick by what you kept when you sent the invoice:

| What you have | Command |
| --- | --- |
| A receipt from `invoices send` | `invoices upo --receipt FILE --out FILE` for one online invoice, `--upo-dir DIR` for a batch |
| The online session state file | `online upo --state-file FILE --out FILE` |
| A batch session and one of its UPO page references | `batch upo (--reference R \| --state-file FILE) --upo-reference R --out FILE` |
| Only references: the session plus an invoice, KSeF, or UPO reference | `sessions upo --session R --out FILE` |

The first three need something the sending process produced. `sessions upo` needs
nothing but references, so it works after a restart, on another machine, or from a
cron job that only knows the numbers your database kept.

### UPO from references alone

```bash
uv run ksef2 --profile prod-token \
  sessions upo --session "$SESSION_REFERENCE" \
  --ksef-number "$KSEF_NUMBER" \
  --out invoice-upo.xml
```

`--session` and `--out` are required, and exactly one of these selects the
document:

- `--ksef-number` reads the invoice UPO for one accepted invoice, once KSeF has
  assigned the number.
- `--invoice-reference` reads the same document, selected by the reference the
  session gave when the invoice was submitted. Use it while the KSeF number is
  still unknown to you.
- `--upo-reference` reads one session UPO page, the collective confirmation for the
  whole session. Session status lists these references under
  `upo.pages[].reference_number`.

The command works for online and batch sessions alike and still authenticates,
because it asks KSeF for the document. It never waits: processing unfinished means
a non-zero exit under the heading `KSeF has not finished processing yet`, with the
hint to retry later.

### Check status before retrying

Asking again is only the right move while KSeF is still working. An invoice KSeF
rejected will never receive a UPO, so read the status once and let it settle the
question:

```bash
uv run ksef2 --profile prod-token invoices status --receipt invoice-receipt.json --wait
uv run ksef2 --profile prod-token batch status --state-file batch-state.json --wait
uv run ksef2 --profile prod-token online invoice-status \
  --state-file online-state.json --invoice-reference "$INVOICE_REFERENCE" --wait
```

A rejected invoice reports a status code of 400 or above, while an accepted one has
a `ksef_number`. A `--timeout` that expires is not a rejection either: it only
means KSeF had not finished inside your deadline, so the references stay valid and
you ask again later. `batch status` is the one command here that needs the session
state file rather than a reference: see
[Batch sessions](batch-sessions.md#read-status-and-per-invoice-results).

## Find sessions after a restart

`sessions invoice-list` reads the history of past invoice sessions and is how you
get a session reference back when the sending process is long gone:

```bash
uv run ksef2 --profile prod-token \
  sessions invoice-list \
  --type online \
  --status in_progress \
  --created-from 2026-03-01T00:00:00Z \
  --all
```

- `--type online` or `--type batch` is required; the two histories are separate.
- `--status` filters on `in_progress`, `succeeded`, `failed`, or `cancelled`, and
  repeats for several at once.
- `--reference` looks up one exact session.
- `--created-from`, `--created-to`, `--closed-from`, `--closed-to`,
  `--modified-from`, and `--modified-to` take an ISO 8601 date or datetime. A bare
  date becomes midnight with no UTC offset, so prefer the explicit
  `2026-03-01T00:00:00Z` form when the window matters.
- `--page-size` takes 10 to 100 and defaults to 10, and `--all` walks every page in
  one command.

Text output prints one block per session:

```text
reference_number: 20260302-BATCH-...
status: {"code":200,"description":"Processed","details":null}
date_created: 2026-03-02T09:00:00Z
date_updated: 2026-03-02T09:05:00Z
total_invoice_count: 2
successful_invoice_count: 2
failed_invoice_count: 0
```

Take `reference_number` from here into `sessions upo`. A session that is still
`in_progress` has no UPO pages yet, and one that finished with failures has fewer
accepted invoices than the `invoices send` run submitted, so compare
`total_invoice_count` with `failed_invoice_count` before believing a batch went
through.

## Close authentication sessions

Authenticating opens an authentication session on the KSeF side, and a workstation
or job that logs in often can collect several.

```bash
uv run ksef2 --profile prod-token sessions auth-list --all
```

One block per active session, with `reference_number`, `start_date`, the
authentication method, `status_description`, and `is_current` for the session this
credential is using right now. `--page-size` takes 10 to 100; ksef2 1.0 pages this
listing internally, so `--continuation-token` is rejected and `--all` is how you
see everything.

To retire one:

```bash
uv run ksef2 --profile prod-token \
  sessions auth-close --reference "$AUTH_SESSION_REFERENCE"

uv run ksef2 --profile prod-token sessions auth-terminate-current
```

`auth-close` ends the session you name, including one left open by a laptop that
went away; closing the session you are authenticated with ends your own access, and
the next command simply authenticates again. `auth-terminate-current` ends the
session behind the credentials in use and keeps those credentials on disk. To end
the session and delete the saved auth state file with it, use
`auth logout --state-file FILE`, described in
[Authentication](authentication.md#reuse-a-saved-authentication).

## What to keep

Send once, then keep enough to answer later without the original process:

- the session reference, from a receipt, a state file, or
  `sessions invoice-list`;
- the invoice reference for each submission, and the KSeF number once assigned;
- the UPO references from a session status, and the UPO XML itself;
- for a batch, the invoice file names KSeF reported back, which is how a rejected
  part maps to a file on your disk;
- the last status you observed, for audit.

Store the downloaded UPO XML, not KSeF's download URL: the URL behind a UPO
reference carries an expiry, and the XML is the document the ministry signed.

## Related pages

- [Invoice workflows](invoices.md)
- [Online sessions](online-sessions.md)
- [Batch sessions](batch-sessions.md)
- [Authentication](authentication.md)
- [Command reference](../reference/commands.md)
