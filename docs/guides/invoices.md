---
title: Invoice Workflows
description: Query, download, export, send, and batch invoices with KSeF2 CLI.
---

Invoice workflows usually start with the `invoices` command group. Use the
lower-level [Online sessions](online-sessions.md) and
[Batch sessions](batch-sessions.md) guides only when you need explicit session
control. Use `--json` when commands are part of a script or CI job.

See [FA(3) invoices locally](fa3.md) to build invoice XML without contacting
KSeF, and [Collective identifiers](collective.md) to group invoices that are
already in KSeF.

## Query metadata

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  invoices metadata \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --date-to 2026-01-31T23:59:59Z \
  --all
```

`invoices metadata --page-size 12` returns one page of up to 12 items.
Add `--all` to fetch every page, with up to 12 items per API request.
`--all` requires `--page-offset` to be 0, its default. A nonzero offset
selects a single page and cannot be combined with `--all`.

`invoices metadata`, `invoices export`, `invoices export-download`, and
`invoices export-pdf` accept the same filters, so a query you tuned against
metadata replays unchanged on an export:

- Window: `--date-from` (required) and `--date-to` over the field named by
  `--date-type` (`issue_date`, `invoicing_date`, `permanent_storage`)
- Counterparty: `--seller-nip`, `--buyer-nip`, `--buyer-vat-ue`, `--buyer-other-id`
- Identity: `--invoice-number`, `--ksef-number`, `--form`, `--invoice-type`,
  `--currency`, `--invoicing-mode`
- Money: `--amount-type` with `--amount-min` and `--amount-max`
- Flags: `--role`, `--attachment yes|no`, `--self-invoicing yes|no`

Date options also accept day-first `DD.MM.YYYY` or `DD-MM-YYYY` dates, with one or
two digits for the day and month. A value with no offset here is wall-clock time in
`Europe/Warsaw`, which is how the SDK reads it, so a bare `2026-01-01` is that day at
midnight Polish time. Write the `Z` or `+HH:MM` form when the window has to mean UTC.

`--restrict-hwm` (short for `--restrict-to-permanent-storage-hwm-date`) restricts
the result set to the permanent-storage high-water mark, so repeated requests
return the same invoices. Without it the query runs against whatever KSeF holds
when it processes the request, and repeating a query while invoices arrive gives a
different set each time. Add the flag when rows must stay stable across requests,
such as a paged metadata walk or an export you retry after a failure.

## Download one processed invoice

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices download \
  --ksef-number "$KSEF_NUMBER" \
  --out invoice.xml
```

Without `--out`, the command saves `NUMBER.xml` in the current directory, where
`NUMBER` is the KSeF number. Characters unsafe for filenames are replaced with
underscores. Use `--out PATH` or the local `-o PATH` to choose a file. File downloads
print the saved path and byte count, or the existing JSON result with `--json`.

Use `--out -` or the local `-o -` to pipe the original XML bytes to another command:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices download --ksef-number "$KSEF_NUMBER" --out - \
  | xmllint --format -
```

Stdout contains exactly the downloaded bytes, preserving their encoding with no
added newline or summary. This mode creates no file. Errors and any progress stay
on stderr. Do not combine `--out -` with global `--json`, `--output json`, or
`-o json`. The command rejects that combination with exit code 2 before
authentication or download, with a JSON error on stderr and empty stdout.

Add `--wait` when the invoice may not be ready yet:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices download \
  --ksef-number "$KSEF_NUMBER" \
  --wait \
  --timeout 120 \
  --poll-interval 2
```

## Schedule and fetch an export

The filters above carry over. Export adds `--only-metadata` to skip the invoice
payloads, `--compression-type zip|tar_gz` for the package format, and
`--handle-file` to save the decryption handle. First schedule the export and save
that handle:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  invoices export \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --handle-file export-handle.json
```

Check status:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices export-status --reference "$EXPORT_REFERENCE"
```

Fetch and decrypt the package:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices export-fetch \
  --handle-file export-handle.json \
  --wait \
  --out-dir downloads
```

For a one-command flow that waits for the export on its own:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices export-download \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --timeout 300 \
  --out-dir downloads
```

`export-download` has no `--wait`: it always waits, for `--timeout` seconds
(default `120`) checked every `--poll-interval` seconds. Use the separate
`export` and `export-fetch` commands when you need to walk away between
scheduling and downloading.

## Render an export to PDF

`invoices export-pdf` is `export-download` plus a rendering step: it schedules the
export, waits, decrypts the package into `--out-dir`, and renders each invoice XML
to PDF.

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  invoices export-pdf \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --out-dir downloads \
  --pdf-dir pdfs
```

| Option | Purpose |
| --- | --- |
| `--out-dir DIR` | Where the decrypted invoice XML goes. Default `downloads`. |
| `--pdf-dir DIR` | Where the PDFs go. Defaults to `--out-dir`, so the PDFs sit beside their XML. |
| `--paper-size` | `a4`, `a4-landscape`, `a3`, `a3-landscape`, `letter`, or `letter-landscape`. Omit to keep the stylesheet paper, normally A4 landscape. |

PDF rendering uses WeasyPrint, which arrives through the optional `pdf` extra, so
install the CLI as `ksef2-cli[pdf]` before running this command. Without the extra
the command names the install command and stops; every other command keeps
working. See [Installation](../getting-started/installation.md#pdf-rendering).

To render a file you already have, without contacting KSeF, use
[`fa3 render`](fa3.md) instead.

## Send invoices

By default, `invoices send` opens an online session, sends the XML file, closes
the session, and prints one line per invoice:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  invoices send invoice.xml
```

Wait for final processing and download the UPO into a directory:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  invoices send invoice.xml \
  --wait \
  --upo-dir upos
```

Save a receipt when you need to check status or download the UPO later:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  invoices send invoice.xml \
  --receipt invoice-receipt.json

uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  invoices status --receipt invoice-receipt.json --wait

uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  invoices upo --receipt invoice-receipt.json --out invoice-upo.xml
```

Send every XML file directly inside a directory:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  invoices send invoices/ --receipt-dir receipts
```

Add `--recursive` to include nested directories. If any file fails in online
mode, the command still attempts the remaining files and exits non-zero after
printing the per-file results.

Two combinations stop before anything is sent: `--upo-dir` requires `--wait`,
because there is no UPO to download until processing finished, and `--receipt` names
one file, so several invoices need `--receipt-dir`.

When one command should not own the session, because you keep it open or another
process finishes the sends, work in the session itself with
[Online sessions](online-sessions.md).

## Send invoices as a batch

Use `--mode batch` when the input files should be prepared and submitted as one
batch session:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices send invoices/ \
  --mode batch \
  --wait \
  --upo-dir upos \
  --receipt batch-receipt.json
```

A batch receipt can be reused for status and UPO downloads:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices status --receipt batch-receipt.json --wait

uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices upo --receipt batch-receipt.json --upo-dir upos
```

`invoices upo` needs `--upo-dir` for a batch receipt: KSeF returns its confirmation
as pages, and `--out` holds one file. `--offline` and `--max-part-size` belong to
this mode and fail with `--mode online`.

To hold the session state yourself, prepare the package once and upload it more than
once, or recover an upload KSeF rejected, use [Batch sessions](batch-sessions.md).

## Advanced session commands

Everything above wraps a session that `invoices send` opens and closes for you.
When you need the session itself, two lower-level groups operate on it directly and
a third decides which UPO command fits:

- [Online sessions](online-sessions.md): `online open`, `send`, `status`, `list`,
  `invoice-status`, `upo`, and `close`, with `--state-file` and `--keep-open` for a
  session that has to outlive one command.
- [Batch sessions](batch-sessions.md): `batch submit`, `prepare`, `upload`,
  `status`, `list`, and `upo`, including offline invoicing mode and recovering an
  upload KSeF rejected.
- [Sessions and UPO](sessions-and-upo.md): the UPO of any past session from its
  reference alone, invoice session history, and authentication sessions.

Session state files (`--state-file`, `--save-state`) and invoice workflow receipt
files (`--receipt`, `--receipt-dir`) carry the session AES key and IV, so the CLI
writes them with owner-only permissions (`0600`). A directory written by
`batch prepare` holds that key together with the invoice payloads. Treat all of them
like credentials: do not commit them or paste them into issues.
