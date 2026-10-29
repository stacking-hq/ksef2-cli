---
title: FA(3) Invoices Locally
description: Build, inspect, and render FA(3) invoice XML with KSeF2 CLI, without contacting KSeF.
---

The `fa3` group wraps the SDK's public builder and renderer. It never opens a
client, so none of these commands need a NIP, token, or certificate. Use them to
turn a JSON draft into schema-valid FA(3) XML, to read an invoice someone handed
you, and to produce a printable view. Building an invoice here does not send it;
submit the resulting XML with [invoices send](invoices.md#send-invoices).

## 1. Start from a draft

```bash
uv run ksef2 fa3 draft-example --out draft.json
```

Without `--out` the draft prints to stdout. The draft is a plain JSON object with
`header`, `seller`, `buyer`, and `body`; `body.rows` holds the line items, and the
builder computes the amounts and the VAT summary, so the draft has no totals to
keep in sync.

## Consult the draft schema

```bash
uv run ksef2 fa3 schema
uv run ksef2 fa3 schema --out schema.json
```

`schema` exports the installed SDK's public `KsefInvoiceDraft` validation schema.
Stdout is a JSON Schema object, including with the global `--json` option.
`--out` writes that object to a UTF-8 file and reports its path and byte count,
just like `draft-example`.

Consult `properties` and `$defs` for additional fields, nested payment and
correction data, required fields, constraints, and accepted enum values such as
VAT rates. The CLI exports the SDK schema without modifying it. Schema details
and validation behavior follow the installed SDK version. A draft can match the
JSON Schema and still fail builder or XML validation, for example when required
invoice parties are missing. SDK 1.1.0 also accepts unknown nested fields;
upstream fixes are tracked in [SDK #334](https://github.com/stacking-hq/ksef2/issues/334)
and [SDK #335](https://github.com/stacking-hq/ksef2/issues/335).

When an assistant prepares a draft, start with `draft-example`, consult `schema`
before adding fields, then run `build` and `inspect`. Compare every position,
quantity, VAT rate, and computed total with the user's request before sending
anything. Schema validation does not replace that comparison or runtime
validation.

## 2. Build the XML

```bash
uv run ksef2 fa3 build --in draft.json --out invoice.xml
```

Pass `--in -` to read the draft from stdin, which is how you pipe a draft from
another tool:

```bash
cat draft.json | uv run ksef2 fa3 build --in - --out invoice.xml
```

| Option | Purpose |
| --- | --- |
| `--out FILE` | Where to write the XML. Without it the XML goes to stdout. |
| `--pretty` / `--no-pretty` | Indent the XML. On by default. |
| `--validate` / `--no-validate` | Check the XML against the FA(3) schema before writing it. On by default. |

`--no-validate` skips only the schema check. The builder still rejects drafts it
cannot turn into an invoice, and the message names the missing part:

```text
Error: Invoice seller is required but not set.
```

## 3. Inspect an invoice

```bash
uv run ksef2 fa3 inspect --in invoice.xml
```

Text output prints one line each for `header`, `seller`, `buyer`, and `body`, so
you can check a counterparty, the invoice number, or a single row's computed
amounts. A section too wide for the terminal continues on the indented lines below
its name, so nothing is cut short: `COLUMNS=80` wraps to 80 columns in a pipe as
well as in a terminal. Add `--json` for the whole parsed invoice as one object:

```bash
uv run ksef2 --json fa3 inspect --in invoice.xml | jq '.body.rows[0]'
```

## 4. Render HTML, and PDF if you need it

```bash
uv run ksef2 fa3 render --in invoice.xml --out invoice.html
```

PDF needs the optional extra:

```bash
uv sync --extra pdf              # project checkout
uv tool install "ksef2-cli[pdf]"  # installed CLI

uv run ksef2 fa3 render --in invoice.xml --out invoice.html --pdf invoice.pdf
```

Without those dependencies the command checks for them first and exits `1`
naming the extra, so neither the HTML nor a half-written PDF appears. See
[PDF rendering](../getting-started/installation.md#pdf-rendering) for the system
libraries WeasyPrint needs, including the `DYLD_FALLBACK_LIBRARY_PATH` a macOS
checkout often needs on top of Homebrew.

`--ksef-number` adds the verification QR KSeF publishes for an accepted invoice: the
number is printed under the code, which links to the KSeF verification page for the
selected `--env`. Leave it out for a draft, whose PDF has no QR.

```bash
uv run ksef2 fa3 render --in invoice.xml --pdf invoice.pdf \
  --ksef-number 5252222222-20260409-ABCDEF123456-AB
```

`--code-lookups` resolves country, tax-office, and currency codes using the SDK's
bundled official lists. Network access and writes stay blocked. An unknown lookup
URI fails the render with details identifying the unresolved URI.
`--no-code-lookups` keeps coded values as codes.

## Related pages

- [Invoice workflows](invoices.md)
- [Collective identifiers](collective.md)
- [Command reference](../reference/commands.md)
