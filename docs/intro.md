---
title: KSeF2 CLI
description: Command-line interface for the ksef2 Python SDK.
---

KSeF2 CLI wraps the `ksef2` Python SDK in a script-friendly command-line tool.
It is intended for local operations, CI jobs, and operational scripts that need
to authenticate with KSeF, query invoices, submit invoices, inspect sessions, or
manage administrative resources without writing Python code.

The CLI is intentionally stateless by default. Authenticated commands accept
credentials through global options or environment variables. A local config file
is available for developer workstations, but secrets should normally come from
environment variables or a trusted secret manager in shared environments.

The default environment is `test`. A selected profile carries the environment when
you do not pass `--env`, and `--env` overrides the profile, so `--env production` and
a profile that says `environment = "production"` both keep working. What changed in
1.0 is only the fallback: a command with no `--env` and no profile talks to TEST
instead of production.

Output is split by outcome. Success goes to stdout, as plain text or as one JSON
document with `--json`. Failure goes to stderr with nothing on stdout, and in JSON
mode it is one object: `{"error": {"code": ..., "message": ..., "ksef_code": ...,
"trace_id": ...}}`. Exit codes are `0` for success, `1` for a runtime failure, `2` for
a usage failure, and `130` for Ctrl-C. See
[Output modes](guides/configuration.md#output-modes).

Files the CLI writes to continue a workflow, meaning auth state, session state,
export handles, and receipts, hold credentials or session keys in plain text. The CLI
gives them mode `0600`, which is a permission and not encryption. Keep them out of
commits, logs, and issue threads.

## Start here

- [Install and run the CLI](getting-started/installation.md)
- [Run the quickstart](getting-started/quickstart.md)
- [Choose an authentication method](guides/authentication.md)
- [Use local configuration](guides/configuration.md)
- [Work with invoices and sessions](guides/invoices.md)
- [Build FA(3) invoices locally](guides/fa3.md)
- [Group invoices with collective identifiers](guides/collective.md)
- [Review the command reference](reference/commands.md)

## Command shape

The package exposes two equivalent executables:

```bash
ksef2
ksef2-cli
```

Global options come before the command group:

```bash
ksef2 --env test --nip 5261040828 --test-cert --json auth login
```

`--version` prints the CLI version and the SDK version it resolved, and reads no
config file:

The command groups mirror the SDK domains:

- `auth`
- `invoices`
- `collective`
- `fa3`
- `online`
- `batch`
- `tokens`
- `sessions`
- `certificates`
- `permissions`
- `limits`
- `peppol`
- `encryption`
- `testdata`
- `config`
- `profile`
