---
title: Rendering Refactor Plan
description: Implementation plan for typed Pydantic results and singledispatch renderers in ksef2-cli.
---

# Rendering refactor plan

Replace reflection-based output in `rendering.py` with typed Pydantic results and explicit
`singledispatchmethod` renderers. Collapse redundant command nesting where it adds no value.

## Goals

- Commands return typed values (`KSeFBaseModel`, `list[...]`, or CLI-owned Pydantic models).
- JSON output uses `model_dump(mode="json")` — no custom `_to_jsonable` walk.
- Plain text output uses registered handlers per type — no `_primary_collection` heuristics.
- Remove `collection()`, ad-hoc `dict[str, str]` success payloads, and duplicate settings access.
- Simple commands use one entry helper (`run_authenticated_command` / `run_client_command`).

## Non-goals

- Adding a service layer between commands and the SDK.
- Changing Typer option surfaces or command names.
- Rewriting `sdk_models.py` beyond what migration requires.
- Publishing user-facing docs until the refactor lands (update `architecture.md` only).

## Target architecture

```text
User invocation
  → app.py (Settings on ctx.obj)
  → commands/*.py (parse options, call SDK, return Renderable)
  → run_command (try / render / errors)
      → run_authenticated | run_client (SDK lifecycle, when needed)
  → renderers.render(ctx, result)
      → JsonRenderer | PlainTextRenderer (@singledispatchmethod)
  → stdout (errors → stderr via exceptions.py)
```

### Runtime layers (what stays)

| Layer | Module | Responsibility |
|-------|--------|------------------|
| Shell | `app.py` | Typer, global options, `Settings` |
| Pipeline | `context.py` | `run_command`, auth/client wrappers, errors |
| Workflow | `commands/*.py` | Option → SDK call → `Renderable` |
| Output | `renderers/` | JSON/text formatting |

### Nesting rule for commands

| Command shape | Pattern |
|---------------|---------|
| Single SDK call | `run_authenticated_command(ctx, lambda auth: ...)` |
| Public SDK call | `run_client_command(ctx, lambda client: ...)` |
| Void mutation | `run_authenticated_command(ctx, work)` where `work` returns `ActionResult` |
| Multi-step (file I/O, loops) | Named `work(auth)` closure, still one entry helper |
| Avoid | `def operation()` that only forwards to `run_authenticated` |

## New module layout

```text
src/ksef2_cli/
  results.py                 CLI-owned Pydantic result models + Renderable alias
  renderers/
    __init__.py              render(ctx, result)
    json.py                  JsonRenderer + json_renderer singleton
    json_cli.py              JSON handlers for CLI-only types (FocusedResult, …)
    text.py                  PlainTextRenderer + plain_renderer singleton
    rows/
      __init__.py            import all row modules (registration side effects)
      tokens.py
      peppol.py
      invoices.py
      sessions.py
      …                        one file per domain as handlers are added
  context.py                 updated helpers (see below)
  rendering.py               DELETE after migration (or thin re-export during transition)
```

## `results.py`

Base type — **not** `KSeFBaseModel` (no API extra-field logging, no camelCase aliases):

```python
class CliResult(BaseModel):
    model_config = ConfigDict(frozen=True)
```

### CLI-only models

| Model | Replaces | Notes |
|-------|----------|-------|
| `SavedFile` | `{"path", "bytes"}` | Use `Field(serialization_alias="bytes")` on `size` for JSON compat |
| `ActionResult` | `{"revoked": "true"}`, etc. | Optional fields; bools for flags |
| `FocusedResult` | `collection(payload, items)` | JSON → `payload`, text → `items` |
| `ExportHandleSaved` | export dict + optional `handle_file` | Move logic from `_export_handle_to_dict` |
| `ExportPaths` | export-fetch / export-download payload | `reference_number`, `paths`, optional `handle_file` |
| `SessionOpened` | `{"state_file", "state"}` | online/batch open |
| `BatchOpened` | batch open composite | state + status |
| `OnlineSendResult` | online send payload | or `FocusedResult` if simpler |
| `ConfigPathInfo` | `config path` dict | |
| `ConfigShowResult` | `config show` dict | mask secrets in serializer |
| `ConfigInitResult` | `config init` dict | |

### Renderable alias

```python
type Renderable = BaseModel | list[BaseModel]
```

SDK response models and `CliResult` subclasses are all `BaseModel`. Lists appear when `--all`
flattens pages.

## Renderers

### `JsonRenderer`

Registrations (minimal set):

1. `BaseModel` → `model_dump(mode="json", by_alias=True)`
2. `list` → list of dumps
3. `FocusedResult` → delegate to `payload`
4. Overrides only where needed (e.g. `ConfigShowResult` secret masking)

### `PlainTextRenderer`

Registrations added incrementally per migration PR. Required handlers:

1. `list` → join `render(item)` per element (recursive dispatch)
2. One handler per SDK type that appears in text output
3. All `CliResult` subclasses

No generic `BaseModel` fallback for text — missing handler raises `TypeError` and fails tests.

### Entry point

```python
def render(ctx: typer.Context, result: Renderable) -> None:
    settings = get_settings(ctx)
    renderer = json_renderer if settings.output is OutputMode.json else plain_renderer
    sys.stdout.write(renderer.render(result) + "\n")
```

Import `rows` package from `renderers/__init__.py` so handlers register at startup.

## `context.py` changes

### Keep

- `get_settings`, `create_client`, `use_client`, `run_client`, `run_authenticated`
- `authenticate_client`, credential loaders, `read_model`, `fail`
- `run_command` (update type hint to `Callable[[], Renderable]`)

### Add

```python
def run_authenticated_command(ctx, work: Callable[[Any], Renderable]) -> None:
    run_command(ctx, lambda: run_authenticated(ctx, work))

def run_client_command(ctx, work: Callable[[Client], Renderable]) -> None:
    run_command(ctx, lambda: run_client(ctx, work))
```

### Remove

- Old `run_client_command` body that duplicated `use_client` differently (fold into above)
- Import from deleted `rendering.py`; import from `renderers`

## `io.py` addition

```python
def write_bytes_file(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path
```

Use in download/upo commands instead of inline `mkdir` + `write_bytes`.

## PR sequence

### PR 1 — Foundation + proof (`tokens`, `peppol`)

**Scope**

- Add `results.py` with `CliResult`, `ActionResult`, `Renderable`
- Add `renderers/` skeleton with `JsonRenderer`, `PlainTextRenderer`, singledispatch
- Register JSON handlers for `BaseModel`, `list`, `FocusedResult` (stub if unused yet)
- Register text handlers: `GenerateTokenResponse`, `TokenStatusResponse`, `QueryTokensResponse`,
  `TokenInfo`, `TokenInfo` via list, `ListPeppolProvidersResponse`, `PeppolProvider`,
  `ActionResult`
- Update `context.py` with new command helpers
- Migrate `commands/tokens.py`, `commands/peppol.py`
- Migrate `commands/auth.py` to unified `run_client_command`
- Unit tests: JSON dump, text rows, `ActionResult`, list recursion
- Keep old `rendering.py` unused or re-export `render` from `renderers` for other commands

**Acceptance**

- `uv run pytest tests/unit/test_renderers*.py tests/component/...tokens...`
- `ksef2 tokens list`, `tokens revoke`, `peppol providers` work in text and `--json`
- No `collection()` or `dict` returns in migrated commands

### PR 2 — File results (`SavedFile`, downloads)

**Scope**

- Add `SavedFile`, `write_bytes_file`
- Text handler for `SavedFile`
- Migrate: `invoices download`, `online upo`, `batch upo`

**Acceptance**

- JSON still exposes `"bytes"` field name
- Text shows `path` and `size`/`bytes` consistently

### PR 3 — Export and focused results

**Scope**

- Add `ExportHandleSaved`, `ExportPaths`, `FocusedResult`
- JSON/text handlers for export types
- Migrate: `invoices export`, `export-fetch`, `export-download`
- Replace all `collection()` usages in `invoices.py`

**Acceptance**

- JSON export-fetch returns full payload; text lists paths only (parity with today)

### PR 4 — Session workflows

**Scope**

- Add `SessionOpened`, `BatchOpened`, `OnlineSendResult` (or `FocusedResult`)
- Migrate: `online.py` (open, send, close), `batch.py` (open, close paths)
- Replace remaining `ActionResult` dicts in sessions/online/batch

**Acceptance**

- Multi-invoice send text output readable; JSON unchanged structurally

### PR 5 — Void actions and config

**Scope**

- Migrate `sessions.py`, `certificates.py` (revoke), `limits.py`, `testdata.py`
- Add config result models + secret-safe JSON for `config show`/`init`
- Migrate `commands/config.py`

**Acceptance**

- All `{"…": "true"}` dict returns gone from codebase

### PR 6 — Remaining SDK passthrough handlers

**Scope**

- Register plain-text handlers for types returned by:
  - `permissions.py`
  - `certificates.py` (queries)
  - `encryption.py`
  - `limits get`
  - `invoices metadata`, `export-status`
  - `sessions invoice-list`, `auth-list`
  - `batch status`, `list`
- Collapse unnecessary `def operation()` wrappers in touched files

**Acceptance**

- Every command path covered by a registered text handler
- Grep for `def operation()` only where multi-step logic exists

### PR 7 — Cleanup

**Scope**

- Delete `rendering.py` (and `Collection`, `collection()`, reflection helpers)
- Remove dead tests in `test_helpers.py`; add/organize renderer tests
- Update `docs/contributing/architecture.md` to describe new flow
- Delete this plan doc or mark complete

**Acceptance**

- `rg '_primary_collection|collection\\(|_to_jsonable|_plain_text' src/` → empty
- Full `uv run pytest` green

## Command migration checklist

For each command handler:

- [ ] Return type is `Renderable` (no `Any`, no bare `dict`)
- [ ] Uses `run_authenticated_command` or `run_client_command` (or `run_command` only for config-style local work)
- [ ] Void SDK calls return `ActionResult(...)` with bool fields
- [ ] File writes go through `io.write_bytes_file` / `_write_json`
- [ ] Text/JSON split uses `FocusedResult`, not `collection()`
- [ ] Plain-text handler registered for every new return type
- [ ] Component or unit test covers `--json` and default text output

## Testing strategy

### Unit (`tests/unit/test_renderers/`)

- `test_json.py` — model dump, list, `FocusedResult`, alias fields (`SavedFile.bytes`)
- `test_text_tokens.py`, etc. — golden strings per handler
- `test_action_result.py` — bool → `yes`/`no` in text, `true`/`false` in JSON

### Existing tests to update

- `tests/unit/test_helpers.py` — remove rendering reflection tests; keep parsing/io/sdk_models
- `tests/unit/test_context.py` — adjust imports if `render` moves

### Component

- Keep `CliRunner` smoke tests; update expected output when text layout is intentionally defined
- Snapshot critical `--json` outputs before PR 1 for regression comparison

## Compatibility notes

| Topic | Decision |
|-------|----------|
| JSON field `bytes` on file results | Keep via serialization alias |
| Text heuristic unwrapping single list field | Removed — explicit handlers instead |
| `collection()` JSON vs text | `FocusedResult` preserves behavior |
| String `"true"` flags | Become JSON booleans in `ActionResult` (breaking for scripts relying on strings — document in PR 5) |

## Definition of done

- [ ] All commands return `Renderable`
- [ ] `rendering.py` deleted; output only through `renderers/`
- [ ] `singledispatchmethod` on both renderers; row handlers in `renderers/rows/`
- [ ] No `collection()`, no reflection formatters, no duplicate `get_settings` in renderers
- [ ] `architecture.md` updated
- [ ] Full test suite passes

## Execution order for contributors

1. Read this plan and `architecture.md`.
2. Land PR 1 before touching session/export workflows.
3. When adding a command or return type, register text handler in the same PR.
4. Do not reintroduce `Any` return types or dict payloads for success output.
