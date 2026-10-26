---
title: Collective Invoice Identifiers
description: Group submitted invoices under a collective identifier and query the grouping from both sides with KSeF2 CLI.
---

A collective identifier is a KSeF number that groups invoices which belong
together, for example invoices settled by one payment. The `collective` group
generates those identifiers and reads the grouping back in both directions. Every
command here names invoices by their KSeF number; nothing in this group accepts
local XML files, so submit the invoices first and keep their KSeF numbers from
the UPO or from `invoices metadata`.

## Generate an identifier

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  collective generate \
  --invoice "$KSEF_NUMBER_1" \
  --invoice "$KSEF_NUMBER_2"
```

`--invoice` repeats once per invoice to group. The output is the new
`collective_identifier_number`. The command fails when neither `--invoice` nor
`--invoices-file` provides at least one invoice.

## Attach payment and description

`--invoices-file` takes a JSON array, one object per invoice, and is the only way
to add the per-invoice payment and description:

```json
[
  {
    "ksef_number": "PASTE_A_KSEF_NUMBER",
    "payment": { "amount": 1230.0, "currency": "PLN" },
    "description": "March consulting"
  }
]
```

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  collective generate \
  --invoices-file invoices.json \
  --invoice "$KSEF_NUMBER_3"
```

Both sources are merged into one request: the file entries first, then the
`--invoice` values, which have no payment or description.

## List identifiers

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  collective list \
  --date-from 2026-03-01 \
  --date-to 2026-03-31 \
  --all
```

`--date-from` is required and filters on creation time; `--date-to` defaults to
now, so a date-only `--date-from` with no `--date-to` means "from that day until
now". KSeF wants one unambiguous instant for both bounds. A date with no time of
day, written `2026-03-01` or `01.03.2026`, is that day at midnight UTC, and a
datetime has to carry an offset, so `2026-03-01T08:00:00Z` or
`2026-03-01T08:00:00+01:00` are accepted while `2026-03-01T08:00:00` is rejected
before anything is sent. Narrow further with `--number` for one exact identifier,
`--invoice-count-min` and `--invoice-count-max` for the group size, and
`--current-context yes` for identifiers created in this context or `no` for the
rest.

## Follow the grouping

From one invoice to the identifiers that reference it:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  collective list-for-invoice --ksef-number "$KSEF_NUMBER_1"
```

From identifiers to the invoices under them, with several identifiers in one
request:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  collective list-invoices "$IDENTIFIER_1" "$IDENTIFIER_2"
```

KSeF accepts at most 10 identifier numbers per request. Passing more fails before
the call and tells you to run separate commands for the rest.

## Scripting notes

The three listing commands page the same way as the rest of the CLI: `--page-size`
between 10 and 200, `--all` to walk every page, and `--json` for machine-readable
rows. In text output, `list-invoices` prints `ksef_number`, `payment`,
`description`, and `hidden` per invoice, and `list` prints the identifier, its
creation time, and the grouped invoice count.

## Related pages

- [Invoice workflows](invoices.md)
- [FA(3) invoices locally](fa3.md)
- [Command reference](../reference/commands.md)
