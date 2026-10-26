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
  config.py              Settings resolution, output mode, environment names (profile models come from the ksef2 SDK)
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
3. `config.resolve_settings()` delegates profile selection to `ksef2.profiles`, applies CLI/environment overrides, and stores runtime-ready settings.
4. Commands with local file or multi-step work define a zero-argument `operation` and pass it to `run_command(ctx, operation)`.
5. Single authenticated SDK calls use `run_authenticated_command(ctx, command)`; use `run_authenticated(ctx, operation)` only when the command has local work around the SDK call.
6. Public commands call `run_client_command(ctx, command)` when they only need a root SDK client.
7. Shared invoice behavior lives behind `invoice_workflows.py` so command modules
   can stay thin while preserving one implementation for send/status/UPO flows.
8. Human output is plain text by default; `--json` emits formatted JSON for scripts. The renderer preserves Pydantic/dataclass types until the final formatting step.

## Output and file contract

Users script this CLI, so these are the promises a new command keeps:

| Promise | Where it is kept |
| --- | --- |
| Success goes to stdout, as text or as one JSON document. | `renderers.render()` writes the rendered result to `sys.stdout` and nothing else does. |
| Command errors leave stdout empty and report on stderr; completed sends with rejected items return a result and exit 1. | `context.run_command` catches errors and calls `render_cli_error`; `exit_code_from_result` handles completed results. |
| The JSON failure body is `{"error": {"type", "title", "message", "details", "hints", "exit_code"}}`, plus a `ksef` object with `ksef_code`, `trace_id`, and `status_code`, and `report_url` and `traceback` where they apply. | `render_cli_error()` in `exceptions.py`. |
| Exit `0` on success, `1` on a runtime failure, `2` on a rejected command line, `130` on Ctrl-C. | `CliError.exit_code`, and `exit_code_from_result` for commands that report partial failure. |
| A secret never reaches an argument, a log, or a rendered result unless the command's job is to hand it over. | `SECRET_OPTIONS`, the default token mask in `renderers/auth.py`, the `--show-tokens` opt-in on the three auth commands, and masked `SecretStr` fields in state models. |
| A file that continues a workflow is written with mode `0600`. | `write_text_file(..., file_mode=SECRET_MODEL_FILE_MODE)`, used by `save_resume_state()`, the session state writers, receipts, export handles, and the batch artifact. |

`0600` is a permission, not encryption: those files hold bearer tokens or a session AES
key and IV as readable bytes. A command that adds a new continuation file therefore also
adds a row to the table in [Configuration](../guides/configuration.md#secrets-in-the-files-this-cli-writes),
and updates the relevant usage examples.

A send that stops halfway is the case that catches operators: KSeF already holds whatever
it accepted, so a wait that was interrupted or timed out must report the reference, say
not to submit again, and exit `130` for Ctrl-C or `1` otherwise. `RemoteServiceError` in
`invoice_workflows.py` and `commands/batch.py` shows the shape.

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
