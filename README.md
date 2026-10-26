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
  <a href="https://docs.stacking.me/cli/intro/" title="ksef2 CLI documentation">
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

The 1.0 line runs on the published `ksef2` SDK and needs Python 3.12 or newer. SDK
1.0.0 is on PyPI, so a checkout resolves it from the index with no source override:

```bash
git clone https://github.com/stacking-hq/ksef2-cli
cd ksef2-cli
uv sync
uv run ksef2 --help
```

The CLI's own 1.0.0 package is not on PyPI yet, where the latest release is still
0.0.1, so `uv tool install` and `pipx install` hand you the older 0.x CLI:

```bash
uv tool install ksef2-cli
```

or:

```bash
pipx install ksef2-cli
```

The 1.0 behavior described in these pages needs a checkout until the CLI release
lands. An installed package exposes two equivalent executables:

```bash
ksef2 --help
ksef2-cli --help
```

Package metadata requires the `ksef2` SDK `>=1.0,<2`, so the built wheel refuses the
older 0.22.x SDK. `tests/unit/test_release_metadata.py` fails if the project version,
those bounds, `ksef2_cli.__version__`, or the locked SDK drift apart.

Check what you are running, CLI and SDK together:

```bash
ksef2 --version
```

```text
ksef2-cli 1.0.0
ksef2 1.0.0
```

`--version` is read before the local config file, so it answers even with a broken
or missing config. It prints plain text in every output mode.

## Choose an environment

The default environment is **TEST**. An explicit `--env` wins over a profile, and a
profile's `environment` wins over the default, so `--env production` and a profile
that says `environment = "production"` both keep working unchanged:

```bash
ksef2 --env production --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json auth login
```

Examples below name TEST explicitly. A copy-pasted command that omits `--env` and a
profile now talks to TEST rather than to production.

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
ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
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
- `--auth-state` to reuse state saved by `auth login --save-state`

`auth login`, `auth resume`, and `auth refresh` mask both token values in text and in
JSON output. Each line shows a short prefix and suffix of the token next to its expiry
time, so a log, a shell transcript, or a pasted issue comment keeps nothing reusable.
`--show-tokens` prints the raw bearer tokens instead, and a command that also uses
`--save-state` stays masked even under `--show-tokens`, because the file is where the
credential belongs. When a later command needs the credential, save it rather than
capturing the output.

Saving auth state lets later commands skip a fresh KSeF login:

```bash
ksef2 --profile test-company --json auth login --save-state ksef2-auth.json
ksef2 --env test --auth-state ksef2-auth.json --json sessions auth-list
```

`--save-state` holds the access and refresh bearer tokens **in plain text**. The CLI
writes the file with mode `0600`, which stops other users reading it and does nothing
else: it is not encrypted, and it survives `chmod`-preserving copies, backups, and
`git add`. Keep it outside the repository, or ignore it in `.gitignore`, and put it
somewhere private such as `$XDG_RUNTIME_DIR` on a shared machine.

Each command that reuses the state writes any refreshed token back to that file, and
keeps that mode. `auth refresh` accepts the same `--auth-state`, so a refresh needs
neither a token in the arguments nor a fresh login:

```bash
ksef2 --env test --auth-state ksef2-auth.json --json auth refresh
```

End the session and remove the file with `ksef2 --auth-state ksef2-auth.json
--json auth logout`.

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
ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices send invoice-1.xml invoice-2.xml \
  --mode batch \
  --wait \
  --upo-dir upos
```

Prepare a batch separately when its parts should survive a failed upload:

```bash
ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  batch prepare invoice-1.xml invoice-2.xml --out batch-parts

ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  batch submit --prepared batch-parts --state-file batch-state.json
```

List and record-query commands print aligned plain-text tables with uppercase
headers and one row per record. Empty lists print `No results.`. Identifiers stay
complete; long names and descriptions may end in `…`, and optional columns may
disappear on narrow terminals. Datetime columns use UTC, dates use `YYYY-MM-DD`,
and amounts use two decimal places. Redirected output uses a 120-column layout.
Pagination metadata, when returned by the command, appears below the table.

An online receipt carries the session AES key and IV in plain text, exactly as a session
state file does; a batch receipt holds the session reference and the file names. Every
one of them is written with mode `0600`, and every one of them is a credential for as
long as it can continue the workflow.

`online send` decides what to do with the session it used by how it got it: a session
the command opened closes when the command ends, and a session resumed with
`--state-file` stays open for the next command. `--close` and `--keep-open` say which
you want regardless.

Stopping a send after KSeF accepted the invoice does not unsubmit it. Ctrl-C, a
timed-out `--wait`, and a dropped connection all end the command with the invoice
still inside the session, so read the saved receipt or state file, or ask with
`invoices status`, `online list`, or `batch status`, before sending the file a second
time.

Use `--json` before the command group for all fields or when scripts consume the
output. JSON retains the SDK fields, values, and nulls.

## Output and exit codes

A successful command writes to stdout: plain text by default, one JSON document with
`--json`. Command errors go to stderr as plain text or one JSON object in
`--json` mode, leaving stdout empty. A completed `invoices send` can instead
return a result on stdout with rejected invoice items and exit 1.

In `--json` mode that object carries one `error`:

```json
{"error": {"type": "RemoteServiceError", "title": "KSeF rejected the request", "message": "...", "details": [], "hints": [], "exit_code": 1, "ksef": {"status_code": 400, "ksef_code": 21405, "trace_id": "..."}}}
```

`type` names the CLI error class and `title` gives the short summary. `details`,
`hints`, and `exit_code` are always present. The `ksef` object appears when KSeF
answered, and holds that service's `status_code`, `ksef_code`, and `trace_id`; quote
the trace ID when you report an incident. `report_url` appears on an unexpected CLI
error, and `traceback` appears with `--verbose`. A rejected command line reports
`"type": "UsageError"` with `"exit_code": 2`.

| Exit code | Meaning |
| --- | --- |
| `0` | Success. |
| `1` | Runtime failure: a rejected request, a KSeF timeout, missing or contradictory credentials, a bad file. |
| `2` | Usage failure: unknown option, missing argument, or an invalid value such as a bad NIP checksum or an unreadable `--auth-state` path. |
| `130` | Interrupted (Ctrl-C). The command may still have changed something server-side. |

`invoices send` exits `1` when any file failed, after printing every per-file result.

## Documentation

- Online docs: <https://docs.stacking.me/cli/intro/>
- Installation: <https://docs.stacking.me/cli/getting-started/installation/>
- Quickstart: <https://docs.stacking.me/cli/getting-started/quickstart/>
- Command reference: <https://docs.stacking.me/cli/reference/commands/>
- Source docs: [`docs`](https://github.com/stacking-hq/ksef2-cli/tree/main/docs)
- SDK repository: [`stacking-hq/ksef2`](https://github.com/stacking-hq/ksef2)

## Development

```bash
uv sync --all-groups
uv run ksef2 --help
uv run ksef2 --version
uv run python -m coverage run -m pytest -q
uv run python scripts/validate_docs_frontmatter.py docs/
```

`uv sync` installs the published `ksef2` SDK from PyPI, and `uv.lock` pins the exact
version. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the checks that keep the two in
step.

The CLI command domains live under `src/ksef2_cli/commands/`. Source
documentation lives under `docs/`.

## Contributing

Issues and pull requests are welcome. Before opening a PR, run the focused test
or docs check that covers your change, and update source docs when command
behavior changes.
