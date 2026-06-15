---
title: CLI Architecture
description: Contributor reference for the ksef2-cli command modules and shared helpers.
---

# CLI Architecture

This is a reference for contributors adding or changing commands in `ksef2-cli`.

## Design Goals

- Keep command modules focused on user-facing workflows.
- Keep SDK authentication, output rendering, file I/O, and model conversion in shared helpers.
- Keep every implementation file comfortably below 400 lines.
- Preserve fast `--help` startup by avoiding top-level `ksef2` SDK imports where possible.

## Module Layout

```text
src/ksef2_cli/
  app.py                 Root Typer app, global options, command registration
  config.py              Global settings, local config, output mode, environment names
  context.py             Client creation, authentication, command execution wrapper
  io.py                  JSON file/stdin reads and JSON writes
  parsing.py             CLI string parsing helpers
  rendering.py           Plain text/JSON output rendering
  sdk_models.py          Small SDK model construction and state-file helpers
  commands/
    config.py            Local config path/show/init commands
    auth.py              Authentication and refresh commands
    invoices.py          Metadata, XML download, exports
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
3. `app.py` merges CLI options, environment variables, and local config defaults.
4. Commands with local file or multi-step work define a zero-argument `operation` and pass it to `run_command(ctx, operation)`.
5. Authenticated operations call `run_authenticated(ctx, operation)` from `context.py`; use `get_authenticated_client(ctx)` only when a command truly needs direct access to the SDK client lifecycle.
6. Public commands call `run_client_command(ctx, command)` when they only need a root SDK client.
7. Human output is plain text by default; `--json` emits formatted JSON for scripts. The renderer preserves Pydantic/dataclass types until the final formatting step.

## Adding a Command

1. Put the command in the matching `src/ksef2_cli/commands/*.py` module.
2. If the command needs a new reusable parser or SDK model builder, add it to `parsing.py` or `sdk_models.py`.
3. Avoid importing `ksef2` SDK models at module import time. Prefer local imports inside helper functions or command operations.
4. Add or update a smoke test for command registration or helper behavior.
5. Run:

```bash
uv run pytest
uv run ksef2 --help
```

## File Size Rule

Use 400 lines as a hard warning threshold. If a command module approaches that size:

- Split repeated option groups into helper functions.
- Move reusable SDK model construction to `sdk_models.py`.
- Split the command group into a subpackage only when a single domain naturally has multiple subdomains.
