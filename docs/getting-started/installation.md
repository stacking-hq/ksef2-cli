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

## PDF rendering

Two commands turn invoice XML into PDF: `invoices export-pdf` and
`fa3 render --pdf`. They render with WeasyPrint, which is an optional extra and is
not installed with the CLI by default:

```bash
uv tool install "ksef2-cli[pdf]"   # installed CLI
uv sync --extra pdf                # project checkout
```

On Linux, WeasyPrint also needs system libraries:

```bash
sudo apt-get install libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0 libharfbuzz-subset0
```

On macOS it needs the same libraries from Homebrew. If they are installed and the load
still fails, hand the dynamic loader the Homebrew directory with each PDF command:

```bash
brew install pango
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run ksef2 fa3 render --in invoice.xml --pdf invoice.pdf
```

`/usr/local/lib` is the equivalent path on Intel Macs. Both PDF commands report the
install command, and on macOS the fallback path above, when the dependencies are
missing; every other command keeps working without them.

Without the extra the CLI still installs and every other command runs; the two PDF
commands report the install command above instead of rendering.

## Next steps

- [Run the quickstart](quickstart.md)
- [Configure authentication](../guides/authentication.md)
- [Create local defaults](../guides/configuration.md)
