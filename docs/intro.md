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

## Start here

- [Install and run the CLI](getting-started/installation.md)
- [Run the quickstart](getting-started/quickstart.md)
- [Choose an authentication method](guides/authentication.md)
- [Use local configuration](guides/configuration.md)
- [Work with invoices and sessions](guides/invoices.md)
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

The command groups mirror the SDK domains:

- `auth`
- `invoices`
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
