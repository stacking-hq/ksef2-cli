<h1 align="center">ksef2 CLI</h1>

<h3 align="center">
  Scriptable terminal workflows for the ksef2 Python SDK.
</h3>

<p align="center">
  Use local profiles, environment-backed authentication, JSON output, and
  resumable workflow files to automate KSeF invoicing from shells, CI jobs, and
  operational scripts.
</p>

<div align="center">
  <br>
  <a href="https://ksef2.stacking.me/cli/intro/" title="ksef2 CLI documentation">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/stacking-hq/ksef2-cli/main/docs/assets/ksef2-cli-light-logo.png">
      <img src="https://raw.githubusercontent.com/stacking-hq/ksef2-cli/main/docs/assets/ksef2-cli-dark-logo.png" alt="ksef2 CLI" width="420">
    </picture>
  </a>
  <br>
  <br>
  <p>
    <a href="https://github.com/stacking-hq/ksef2-cli/actions/workflows/ci.yml"><img src="https://github.com/stacking-hq/ksef2-cli/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
    <a href="https://github.com/stacking-hq/ksef2-cli/actions/workflows/docs-check.yml"><img src="https://github.com/stacking-hq/ksef2-cli/actions/workflows/docs-check.yml/badge.svg" alt="Docs"></a>
    <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+"></a>
  </p>
</div>

## What is ksef2 CLI?

`ksef2-cli` exposes the [`ksef2`](https://github.com/stacking-hq/ksef2)
Python SDK as a command-line tool. It is designed for developers and operators
who want to authenticate with KSeF, query invoice metadata, send invoices,
download invoice XML, export packages, inspect sessions, and manage
administrative resources without writing Python code.

The CLI avoids hidden state by default. Commands can read credentials from
global options or environment variables, while local profiles store reusable
non-secret defaults such as environment, NIP, auth method, certificate paths,
and secret environment variable names.

This project is not published, endorsed, or supported by Poland's Ministry of
Finance. Official KSeF documentation remains the source of truth for API
behavior.

## Install

```bash
uv tool install ksef2-cli
```

or:

```bash
pipx install ksef2-cli
```

The package exposes two equivalent executables:

```bash
ksef2 --help
ksef2-cli --help
```

Requires Python 3.12 or newer.

## Authenticate

For repeated local work, create a profile once and let commands inherit its
environment, NIP, and authentication settings:

```bash
ksef2 profile create test-company \
  --env test \
  --nip 5261040828 \
  --test-cert

ksef2 --profile test-company --json auth login
```

For CI and one-off scripts, pass global options before the command group:

```bash
ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  invoices metadata \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --all
```

Supported direct authentication methods:

- `--token` or `KSEF2_TOKEN`
- `--test-cert` for the TEST environment
- `--cert` and `--key` for PEM XAdES credentials
- `--p12` for PKCS#12/PFX XAdES credentials

## Send and download invoices

Send one XML invoice, wait for processing, save a UPO, and keep a receipt for
later status checks:

```bash
ksef2 --profile test-company \
  invoices send invoice.xml \
  --wait \
  --upo-dir upos \
  --receipt invoice-receipt.json
```

Download the UPO later from the saved receipt:

```bash
ksef2 --profile test-company \
  invoices upo \
  --receipt invoice-receipt.json \
  --out invoice-upo.xml
```

Submit many XML files as one batch:

```bash
ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices send invoice-1.xml invoice-2.xml \
  --mode batch \
  --wait \
  --upo-dir upos
```

Use `--json` before the command group when output is consumed by scripts.

## Documentation

- Online docs: <https://ksef2.stacking.me/cli/intro/>
- Installation: <https://ksef2.stacking.me/cli/getting-started/installation/>
- Quickstart: <https://ksef2.stacking.me/cli/getting-started/quickstart/>
- Command reference: <https://ksef2.stacking.me/cli/reference/commands/>
- Source docs: [`docs`](https://github.com/stacking-hq/ksef2-cli/tree/main/docs)
- SDK repository: [`stacking-hq/ksef2`](https://github.com/stacking-hq/ksef2)

## Development

```bash
uv sync --all-groups
uv run ksef2 --help
uv run python -m coverage run -m pytest -q
uv run python scripts/validate_docs_frontmatter.py docs/
```

The CLI command domains live under `src/ksef2_cli/commands/`. Source
documentation lives under `docs/`.

## Contributing

Issues and pull requests are welcome. Before opening a PR, run the focused test
or docs check that covers your change, and update source docs when command
behavior changes.
