---
title: Online Sessions
description: Open, send into, watch, and close an online KSeF invoice session with the online command group and its resumable session state.
---

An online session is the interactive sending path. KSeF opens it, you submit
invoice XML into it one at a time, then close it so KSeF can process the invoices
and issue their UPO documents. Use the `online` group when the session has to
outlive a single command: you keep adding invoices while someone checks a draft,
or a second process has to finish what the first one started. When one command can
do the whole job, `invoices send` opens a session, sends, closes it, and hands you
a receipt instead. See [Invoice workflows](invoices.md#send-invoices).

The CLI never holds a session open between commands. Each command authenticates,
resumes the session from its state file, does one thing, and exits, so the state
file is the whole handle. Every command in this group authenticates and therefore
needs credentials; see [Authentication](authentication.md).

## Open a session and keep its state

```bash
uv run ksef2 --profile test-company \
  online open --state-file online-state.json
```

Text output names the file and prints the state with its key material masked:

```text
state_file: online-state.json
state: {"format_version":1,"reference_number":"20260302-...","aes_key":"**********","iv":"**********","form_code":["FA (3)","1-0E","FA"],"valid_until":"2026-03-02T10:00:00Z"}
```

`--state-file` is optional here, but a session opened without it cannot be
resumed: the state reaches stdout and the process ends. `online send` is the only
other command that may open its own session; the rest require the file.

The state file holds the session AES key and IV **in plain text**, so the CLI creates
it with owner-only permissions (`0600`) and never prints those values. That mode is a
permission and not encryption: anyone reading as the file's owner, and anything that
copies the bytes with them, gets a usable session. Keep the file out of the repository
and out of logs, and delete it when the session is done.

`valid_until` is KSeF's deadline for the session: once it passes, the
session stops accepting anything, so open a new one rather than retrying the old
state.

## Send invoices into a session

```bash
uv run ksef2 --profile test-company \
  online send invoice-1.xml invoice-2.xml \
  --keep-open \
  --save-state online-state.json
```

| Option | Effect |
| --- | --- |
| `--state-file FILE` | Resume that session instead of opening a new one. The file must exist, and `--form` is ignored because the state already carries the form. |
| `--save-state FILE` | Write the state of the session used, opened or resumed. This is how a session started without `--state-file` becomes resumable. |
| `--form` | Schema for a newly opened session: `FA2`, `FA3` (default), `FA_RR1`, `PEF3`, `PEF_KOR3`. |
| `--wait` | Wait for each invoice to finish processing before sending the next. |
| `--keep-open` | Keep a session that this command opened for the next command. Without it a newly opened session closes. A session resumed with `--state-file` is already left open, so the flag changes nothing there. |
| `--close` | Close the session when the command ends, including one resumed with `--state-file`. This is how a resumed session finishes without a separate `online close`. |
| `--timeout`, `--poll-interval` | Waiting budget: 60 seconds, checked every 2 seconds by default. |

A session this command opened closes by default, because that command owned the whole
send. A session resumed with `--state-file` is left open by default, because the file is
the handle and the next command is expected to use it; add `--close` to finish it. The
`closed` field in the output tells you which happened, and `--close` together with
`--keep-open` stops with an error instead of picking one.

Invoice paths are files, not directories, and every path must exist. Unlike
`invoices send`, this command has no directory walk and no `--recursive`.

Text output prints one line per file:

```text
file=invoice-1.xml result={"reference_number":"20260302-ABCD-EF1234567890"}
```

That is all KSeF has promised at that moment: it accepted the encrypted payload
into the session. Add `--wait` and the same line carries the processed result,
including the assigned `ksef_number`:

```text
file=invoice-1.xml result={"ordinal_number":1,"invoice_number":"FV/42/2026","ksef_number":"5261040828-20260302-...","reference_number":"20260302-ABCD-EF1234567890",...,"status":{"code":200,"description":"Processed",...}}
```

With `--json` you get the full payload: `state_file`, `closed`, and a `results`
array with one `{file, result}` object per invoice. The `closed` flag tells you
whether KSeF may start processing yet.

Stopping this command after KSeF accepted an invoice does not take the invoice back.
Ctrl-C exits `130`, and a `--wait` that runs out of time exits `1`, while what was
already sent stays in the session.

What survived the stop depends on how the session started. A session resumed with
`--state-file` still has that file, so `online list --state-file FILE` reads it. A
session this command opened writes `--save-state` only after the whole send finished, so
an interrupted send leaves no state file at all: find the session again with
`sessions invoice-list --type online`, and take the invoice references from whatever the
command managed to print. Read the session before sending any of those files a second
time. See
[An interrupted send is not an unsubmitted invoice](invoices.md#an-interrupted-send-is-not-an-unsubmitted-invoice).

## Check where the session stands

```bash
uv run ksef2 --profile test-company \
  online status --state-file online-state.json
```

One request, no waiting. The answer is KSeF's summary of the session: `status`,
`date_created`, `date_updated`, `valid_until`, `invoice_count`,
`successful_invoice_count`, `failed_invoice_count`, and `upo` once the closed
session has UPO pages.

Read those counters as a summary, not a verdict. A session reports its own status,
so it can be complete while some invoice inside it failed. To find which ones,
list them.

For one invoice, ask its reference and let the command poll:

```bash
uv run ksef2 --profile test-company \
  online invoice-status \
  --state-file online-state.json \
  --invoice-reference "$INVOICE_REFERENCE" \
  --wait \
  --timeout 120 \
  --poll-interval 2
```

Without `--wait` this is a single read. With it, the command returns when KSeF
gives the invoice a result or the local `--timeout` expires. An expiring timeout
says nothing about KSeF: the invoice may still be processing, so check again later
instead of sending the file a second time.

## List what the session took

```bash
uv run ksef2 --profile test-company \
  online list --state-file online-state.json --page-size 100

uv run ksef2 --profile test-company \
  online list --state-file online-state.json --failed
```

`--page-size` accepts 10 to 1000 and defaults to 10. One call returns one page;
pass the `continuation_token` from the previous page to `--continuation-token` to
walk further. `--failed` switches from accepted invoices to rejected ones, which is
where the reason for a rejection appears.

## Close the session

```bash
uv run ksef2 --profile test-company \
  online close --state-file online-state.json
```

```text
reference_number: 20260302-...
closed: yes
```

Closing tells KSeF that no more invoices will arrive, which is what lets it
produce the collective UPO for the session. Closing a session that is already
closed does nothing: a resumed client asks KSeF first and skips a second close.

## Download an invoice UPO

```bash
uv run ksef2 --profile test-company \
  online upo \
  --state-file online-state.json \
  --ksef-number "$KSEF_NUMBER" \
  --out invoice-upo.xml
```

`--out` is required, and so is exactly one of `--ksef-number` or
`--invoice-reference`. The command asks once and never waits, so run
`online invoice-status --wait` first. If KSeF has not issued the UPO yet, the
command exits `1` under the heading `KSeF has not finished processing yet`
and tells you to retry later; an invoice KSeF rejected never gets a UPO at all, so
read its status before retrying forever.

You do not need the session state to fetch a UPO, only its reference. With the
session reference and the invoice reference or KSeF number, `sessions upo` reads
the same document from a fresh login, which is the command to reach for when the
state file is gone or belongs to another machine. See
[Sessions and UPO](sessions-and-upo.md#which-upo-command-fits).

## Related pages

- [Invoice workflows](invoices.md)
- [Batch sessions](batch-sessions.md)
- [Sessions and UPO](sessions-and-upo.md)
- [Authentication](authentication.md)
- [Command reference](../reference/commands.md)
