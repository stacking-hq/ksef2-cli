---
title: PEPPOL Providers
description: List the PEPPOL service providers registered in KSeF with KSeF2 CLI, page through them, and cache the list as reference data.
---

KSeF keeps a public register of PEPPOL service providers. The `peppol` group has
one command, and it reads that register. It runs on the anonymous client, so it
needs no NIP, no token, no certificate, and no profile:

```bash
uv run ksef2 peppol providers
```

```text
id=PPL000120 name=PPL000120 date_created=2026-02-23T08:17:19.144453+00:00
```

`--env` picks which environment you ask, and `test` is what you get when you name
neither `--env` nor a profile. The example above therefore reads the TEST register;
add `--env production` for the production one:

```bash
uv run ksef2 --env production peppol providers
```

## Page through the register

`--page-size` sets the number of items per API request, including with `--all`.
`--all` requires `--page-offset` to be 0, its default, and rejects a nonzero offset.

The first page holds 10 providers. `--page-size` accepts 10 to 100,
`--page-offset` skips records, and `--all` walks every page in one command:

```bash
uv run ksef2 peppol providers --page-size 50
uv run ksef2 peppol providers --page-size 50 --page-offset 50
uv run ksef2 peppol providers --all
```

A `--page-offset` past the last record prints nothing and exits 0, which is what
makes a loop like this safe as a crude walk:

```bash
offset=0
while :; do
  rows=$(uv run ksef2 --json peppol providers --page-size 100 --page-offset "$offset")
  [ "$rows" = "[]" ] && break
  echo "$rows"
  offset=$((offset + 100))
done
```

`--all` does the same walk for you and is the option you want in normal use. A
`--page-size` outside 10 to 100 fails as a usage error before the request:

```text
Invalid value for '--page-size': 5 is not in the range 10<=x<=100.
```

## Read the rows as JSON

```bash
uv run ksef2 --json peppol providers --page-size 10
```

```json
[
  {
    "id": "PPL000120",
    "name": "PPL000120",
    "date_created": "2026-02-23T08:17:19.144453Z"
  }
]
```

`id` is the provider's PEPPOL identifier, `name` is the display name KSeF holds,
which is sometimes the same string, and `date_created` is when the record entered
the register. Text mode drops fields that carry nothing, so `name` can be absent
from a row while `--json` always reports the field.

## Cache the list

Provider records are reference data. They change slowly, and a register query in
the middle of a user action is one more thing that can fail, so read the list on
your own schedule and keep the ids:

```bash
uv run ksef2 --json peppol providers --all \
  | jq -r '.[] | "\(.id)\t\(.name)"' > peppol-providers.tsv
```

Validate user input against the ids you stored rather than calling the register
per keystroke, and refresh on a schedule your data-freshness rule justifies.

## Where PEPPOL ids appear elsewhere

A PEPPOL identifier is one of the context and subject types the rest of the CLI
accepts, which is why this register is worth having locally:

- The root `--context-type` option and `KSEF2_CONTEXT_TYPE` take `peppol_id` for
  token authentication in a PEPPOL context. See
  [Token authentication](authentication.md#token-authentication).
- `permissions grant-authorization` takes `--subject-type peppol_id` for a
  partner you know by that identifier rather than by NIP. See
  [Permissions](permissions.md).

## Related pages

- [Authentication](authentication.md)
- [Permissions](permissions.md)
- [Command reference](../reference/commands.md)
