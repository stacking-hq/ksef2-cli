---
title: Batch Sessions
description: Submit invoice XML as one KSeF batch session, prepare the package once and upload it again, and read batch status, failed invoices, and UPO pages with KSeF2 CLI.
---

A batch session carries many invoices as one KSeF workflow. The unit KSeF
receives is not an XML file but a ZIP package of them, split into parts and
encrypted before upload, so the batch path has stages the online path does not:
prepare, upload, close, wait, then read the per-invoice results. Use
`invoices send --mode batch` when one command should run all of them; use the
`batch` group when you need the session state, want to prepare the package once
and upload it more than once, or need to recover an upload KSeF rejected. See
[Invoice workflows](invoices.md#send-invoices-as-a-batch).

Check the ceiling before you pick a package size. `limits get context` reports
`batch_session.max_invoices` and the per-invoice size cap for the current context,
and KSeF enforces both. See [Limits](limits.md#read-effective-limits).

## Submit a batch in one command

```bash
uv run ksef2 --profile prod-token \
  batch submit invoice-1.xml invoice-2.xml \
  --wait \
  --state-file batch-state.json
```

This prepares the package, opens the batch session, uploads every part, closes the
session, and then waits if you asked it to. The invoice paths are files and they
must exist; there is no directory walk here, so pass a directory of files to
`invoices send` instead. Other options:

| Option | Effect |
| --- | --- |
| `--state-file FILE` | Where to write the resumable session state. On a failed upload, this is where the interrupted session's state is saved. |
| `--form` | Schema declared for the session: `FA2`, `FA3` (default), `FA_RR1`, `PEF3`, `PEF_KOR3`. |
| `--offline` | Declare offline invoicing mode for the package. |
| `--max-part-size BYTES` | Split the ZIP into smaller parts, capped at this size before encryption. Omit to use the SDK default. |
| `--wait` | Wait for KSeF to finish processing the closed session. |
| `--timeout`, `--poll-interval` | Waiting budget: 120 seconds, checked every 2 seconds by default. |

`--wait` returns the session status, so the output carries both the state summary
and the verdict:

```text
state_file: batch-state.json
state: {"format_version":1,"reference_number":"20260302-BATCH-...","aes_key":"**********","iv":"**********","form_code":["FA (3)","1-0E","FA"],"prepared_batch_digest":null}
status: {"status":{"code":200,"description":"Processed","details":null},...,"upo":{"pages":[{"reference_number":"upo-page-1","download_url_expiration_date":"2026-03-03T00:00:00Z"}]},"invoice_count":2,"successful_invoice_count":2,"failed_invoice_count":0}
```

Without `--wait` nothing polls the session: JSON output reports `status` as `null`
and text output leaves that line out. The state file holds the session AES key and IV
**in plain text**, so the CLI creates it with owner-only permissions (`0600`) and prints
those values masked, like every other state file in the CLI. `0600` decides who may open
the file and encrypts nothing, so it is a credential wherever it is copied to.

## Prepare once, upload more than once

Packing and encrypting the parts costs more than posting them, and none of it
depends on a session. `batch prepare` writes the finished package to a directory,
so a rejected upload retries against the parts that already exist:

```bash
uv run ksef2 --profile prod-token \
  batch prepare invoice-1.xml invoice-2.xml \
  --out batch-parts
```

```text
path: batch-parts
invoices: 2
parts: 2
digest: e6c4f3f11decada4ab73c73d9f788a13d357a3471f4439b4a354ae70ff7caff3
```

`--out` (`-o`) is required, and `--form`, `--offline`, and `--max-part-size` mean
what they mean on `submit`. The digest covers the parts, so you can tell two
packages apart without opening them.

Upload the stored package to a new session with `--prepared`:

```bash
uv run ksef2 --profile prod-token \
  batch submit --prepared batch-parts \
  --wait \
  --state-file batch-state.json
```

A prepared package is uploaded exactly as it was built, so `--form`, `--offline`,
and `--max-part-size` do not apply alongside `--prepared`, and passing invoice
files with it fails before anything is sent.

The artifact holds a session key and the invoice payloads, both **in plain text** at
that path. Treat `batch-parts` the way you treat a credential file and remove it when
the batch is done.

## Recover an upload KSeF rejected

When KSeF's storage rejects an upload, the same two files carry the fix: the
failed `submit` leaves the interrupted session state in `--state-file`, and
`batch upload` sends the stored parts to that session instead of opening a new
one:

```bash
uv run ksef2 --profile prod-token \
  batch upload --prepared batch-parts \
  --state-file batch-state.json \
  --wait
```

Both options are required. The state file names the session and its presigned
upload URLs, the artifact carries the exact parts KSeF expects, and the payload
digest is checked against them, so recovery needs neither new invoices nor a new
package. Attaching a different package to that session fails before uploading.
Re-running `batch submit --prepared` starts a new session instead, which is also a
valid answer when the old one has already expired.

Without `--state-file` there is nothing to reattach to, and the failure names the
other way out: prepare the invoices once, then submit the stored package.

## An interrupted batch is not an unsubmitted batch

`batch submit` writes the session reference to `--state-file` before it starts polling,
and `invoices send --mode batch` writes its receipt at that same moment. So Ctrl-C, an
exhausted `--timeout`, and a dropped connection end the command with the batch already
submitted, and the CLI says so (`Batch session ... was submitted, but waiting stopped:
... do not submit the invoices again`) and exits `130` for Ctrl-C or `1` otherwise.

Read what KSeF holds before you upload anything again:

```bash
uv run ksef2 --profile prod-token --json \
  batch status --state-file batch-state.json --wait

uv run ksef2 --profile prod-token --json \
  batch list --state-file batch-state.json --failed
```

`batch upload --prepared DIR --state-file FILE` posts the stored parts to that same
session again, so a stalled batch is normally finished rather than restarted, and no
invoice has to be encrypted a second time. Starting the same invoices in a new session
puts a second copy of every invoice into KSeF. `batch list --failed` says which invoices
the session rejected, as distinct from the parts its storage refused.

## Read status and per-invoice results

Status and listing accept exactly one handle, `--reference` or `--state-file`:

```bash
uv run ksef2 --profile prod-token \
  batch status --reference "$BATCH_REFERENCE" --wait

uv run ksef2 --profile prod-token \
  batch list --state-file batch-state.json --page-size 100

uv run ksef2 --profile prod-token \
  batch list --state-file batch-state.json --failed
```

`batch status` reads the same summary as `submit --wait` and can wait on the same
terms (`--wait`, `--timeout` 120, `--poll-interval` 2). Its counters are the
session's, so a completed session can still report failed invoices. `batch list`
answers which ones: accepted invoices by default, `--failed` for the rejected
ones, where the KSeF status code and details explain each rejection. Accepted and
failed invoices are separate pages: read both when reconciling a batch.
`--page-size` takes 10 to 1000 and defaults to 10; pass the previous page's
`continuation_token` to `--continuation-token` to walk further.

For batch results, correlate by `invoice_file_name` and `invoice_hash` rather than
by position: those are the fields KSeF reports back per invoice, and a KSeF number
appears only once the invoice is accepted.

## Download a batch UPO page

A batch gets its UPO as pages, listed under `upo.pages[].reference_number` in the
session status, and each page is downloaded by its own reference:

```bash
uv run ksef2 --profile prod-token \
  batch upo \
  --state-file batch-state.json \
  --upo-reference "$UPO_REFERENCE" \
  --out batch-upo-1.xml
```

`--upo-reference` and `--out` are required, plus one session handle. A session UPO
page exists only after the session is closed and processed, and the command never
waits: run `batch status --wait` first. If KSeF has not produced the page yet, the
command exits `1` under the heading `KSeF has not finished processing yet` and
tells you to retry later. `download_url_expiration_date` next to each reference is
KSeF's own deadline for the URL behind that reference, so store the downloaded XML
rather than the reference.

`invoices upo --upo-dir` downloads every page of a batch in one call when you have
a receipt, and `sessions upo --upo-reference` reads one page from a fresh login
without any session state. See [Sessions and UPO](sessions-and-upo.md).

## Offline invoicing mode

`--offline` declares the package as issued in offline invoicing mode: the invoices
were created away from KSeF and reach it late. The CLI forwards the declaration and
the SDK puts it into the batch session request; what KSeF makes of it is KSeF's
decision. The declaration is baked into a prepared package, which is why
`submit --prepared` ignores the flag. To find such invoices afterwards, filter
metadata with `--invoicing-mode offline`.

## Related pages

- [Invoice workflows](invoices.md)
- [Online sessions](online-sessions.md)
- [Sessions and UPO](sessions-and-upo.md)
- [Limits](limits.md)
- [Command reference](../reference/commands.md)
