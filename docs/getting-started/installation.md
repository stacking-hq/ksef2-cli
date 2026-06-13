---
title: Installation
description: Install or run KSeF2 CLI with uv and inspect the available command groups.
---

## Requirements

KSeF2 CLI requires Python 3.12 or newer.

For local development from a checkout, use `uv`:

```bash
uv sync
uv run ksef2 --help
```

For an installed package, use either executable:

```bash
ksef2 --help
ksef2-cli --help
```

Both entry points run the same Typer application.

## Verify the command surface

The top-level command lists global options first and command groups second:

```bash
uv run ksef2 --help
```

Use group help to inspect a specific workflow:

```bash
uv run ksef2 invoices --help
uv run ksef2 online --help
uv run ksef2 batch --help
```

Use `--json` when you need machine-readable output:

```bash
uv run ksef2 --json config path
```

## Environment selection

The default environment is `production`. Pass `--env` before the command group
when you need `test` or `demo`:

```bash
uv run ksef2 --env test --help
```

Supported values are:

- `production`
- `demo`
- `test`

## Next steps

- [Run the quickstart](quickstart.md)
- [Configure authentication](../guides/authentication.md)
- [Create local defaults](../guides/configuration.md)
