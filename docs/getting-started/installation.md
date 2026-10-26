---
title: Installation
description: Install or run KSeF2 CLI with uv and inspect the available command groups.
---

## Requirements

KSeF2 CLI requires Python 3.12 or newer.

This 1.0 line depends on the `ksef2` SDK `>=1.0,<2`. The SDK's 1.0 release is not on
PyPI yet, so install and run from a checkout until it is. `CONTRIBUTING.md` in the
repository explains the development override that makes `uv sync` resolve the SDK,
and why no published 1.0 package should be assumed.

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

`--version` reports the CLI and the SDK it resolved, one per line. It is read before
the config file, so it answers even when the config is missing or broken, and it
prints the same plain text in `--json` mode:

```bash
uv run ksef2 --version
```

```text
ksef2-cli 1.0.0
ksef2 1.0.0
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

The default environment is `test`. Pass `--env` before the command group when you
need `demo` or `production`:

```bash
uv run ksef2 --env production --help
```

Supported values are:

- `production`
- `demo`
- `test`

A selected profile supplies the environment when you do not pass `--env`, and it wins
over the default. A profile that says `environment = "production"` therefore still
authenticates against production, and `--env` on the command line still overrides that
profile for one invocation:

```bash
uv run ksef2 --profile prod-client --env test --json auth login
```

The same order applies to every environment-backed command, including `peppol
providers`, which needs no credentials at all and so is the easiest place to be
surprised by a silent default.

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

Without the extra the CLI still installs and every other command runs; the two PDF
commands report the install command above instead of rendering.

## Next steps

- [Run the quickstart](quickstart.md)
- [Configure authentication](../guides/authentication.md)
- [Create local defaults](../guides/configuration.md)
