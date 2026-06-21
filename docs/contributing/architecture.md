---
title: CLI Architecture
description: Contributor reference for the ksef2-cli command modules and shared helpers.
---

# CLI Architecture

This is a reference for contributors adding or changing commands in `ksef2-cli`.

For the in-progress typed rendering refactor (Pydantic results, singledispatch renderers),
see [Rendering Refactor Plan](./rendering-refactor-plan.md).

## Design Goals

- Keep command modules focused on user-facing workflows.
- Keep SDK authentication, output rendering, file I/O, and model conversion in shared helpers.
- Keep every implementation file comfortably below 400 lines.
- Preserve fast `--help` startup by avoiding top-level `ksef2` SDK imports unless Typer needs the type for command registration.

## Module Layout

```text
src/ksef2_cli/
  app.py                 Root Typer app, global options, command registration
  config.py              Profile config models, settings resolution, output mode, environment names
  context.py             Typer adapter for command execution and rendering
  runtime.py             Typer-free client creation, authentication, and model reads
  invoice_workflows.py   Shared invoice metadata, send, export, and UPO workflows
  io.py                  JSON file/stdin reads and JSON writes
  parsing.py             CLI string parsing helpers
  results.py             CLI-owned typed result models
  renderers/             Plain text/JSON output rendering
  commands/
    config.py            Local config path/show/init commands
    profile.py           Local profile create/list/current/show/use commands
    auth.py              Authentication and refresh commands
    invoices/            Thin Typer adapters for invoice workflows
    online.py            Online session workflows
    batch.py             Batch submission and inspection
    tokens.py            KSeF token lifecycle
    sessions.py          Auth and invoice session listings
    certificates.py      Certificate enrollment, query, retrieval, revocation
    permissions.py       Permission grant/query/revoke workflows
    limits.py            Limit query/update/reset workflows
    peppol.py            Public PEPPOL provider query
    encryption.py        Public encryption certificate query
    testdata.py          TEST-environment data helpers
```

## Command Flow

1. `app.py` builds the root `Typer` app and stores global `Settings` on `ctx.obj`.
2. A command module receives `ctx: typer.Context`.
3. `config.resolve_settings()` selects a profile, applies CLI/environment overrides, and stores runtime-ready settings.
4. Commands with local file or multi-step work define a zero-argument `operation` and pass it to `run_command(ctx, operation)`.
5. Single authenticated SDK calls use `run_authenticated_command(ctx, command)`; use `run_authenticated(ctx, operation)` only when the command has local work around the SDK call.
6. Public commands call `run_client_command(ctx, command)` when they only need a root SDK client.
7. Shared invoice behavior lives behind `invoice_workflows.py` so command modules
   can stay thin while preserving one implementation for send/status/UPO flows.
8. Human output is plain text by default; `--json` emits formatted JSON for scripts. The renderer preserves Pydantic/dataclass types until the final formatting step.

## Adding a Command

1. Put CLI-only parameter handling in the matching `src/ksef2_cli/commands/*.py` module.
2. If the command needs a new reusable parser, add it to `parsing.py`.
3. Put shared workflow behavior in an owner module such as `invoice_workflows.py` only when multiple command modules use the same implementation.
4. Avoid importing `ksef2` SDK models at module import time unless Typer needs the type for command choices. Prefer local imports inside helper functions or command operations.
5. Add or update a smoke test for command registration or helper behavior.
6. Run:

```bash
uv run pytest
uv run ksef2 --help
```

## File Size Rule

Use 400 lines as a hard warning threshold. If a command module approaches that size:

- Split repeated option groups into helper functions.
- Keep model construction near the owning command unless it has meaningful shared behavior.
- Split the command group into a subpackage only when a single domain naturally has multiple subdomains.
