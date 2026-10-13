# Contributing

## Branches

| Branch | SDK it runs on | Use it for |
| --- | --- | --- |
| `main` | `ksef2` 0.22.x from PyPI | Fixes for the released CLI line. |
| `next` | `ksef2` from the SDK's `main` branch (unreleased 1.0) | Everything that adopts the ksef2 1.0 API. |

Open 1.0 work as a pull request into `next`. `next` merges into `main` once
ksef2 1.0.0 is on PyPI.

## Working on `next`

`pyproject.toml` on `next` has a temporary `[tool.uv.sources]` entry that
installs ksef2 from `https://github.com/stacking-hq/ksef2` `main`, and
`uv.lock` pins the exact SDK commit:

```bash
uv sync --all-groups
grep -A2 '^name = "ksef2"$' uv.lock   # which SDK commit you are on
```

Pick up newer SDK commits by refreshing only the ksef2 lock entry, then commit
`uv.lock` on its own:

```bash
uv lock -P ksef2
```

To try an SDK change before it is pushed, overlay a local checkout for one
command without touching the lock:

```bash
uv run --with-editable ../ksef2 pytest -q
```

The SDK's own docs describe the 1.0 API: `docs/en/reference/public-api.md`
(stable imports and the deprecated-to-replacement table) and
`docs/en/reference/migration-1-0.md` in the SDK repository.

## Command reference

`docs/reference/commands.md` is generated, not edited. After adding, removing,
or changing a command or option, regenerate it and commit the result:

```bash
uv run python scripts/generate_command_reference.py
uv run python scripts/generate_command_reference.py --check   # non-zero when stale
```

`tests/unit/test_command_reference.py` runs the same generator in memory, so a
commit that changes the CLI without regenerating the page fails the suite.

## Checks

Every pull request must pass:

```bash
uv run python -m coverage run -m pytest -q
uv run python -m coverage report
uv run python scripts/validate_docs_frontmatter.py docs/
```

Two tests keep the CLI on the supported SDK surface:

- `tests/unit/test_public_sdk_imports.py` fails on imports from private or
  legacy internal ksef2 modules.
- `tests/unit/test_no_deprecated_sdk_calls.py` fails on calls to SDK methods
  that 1.0 deprecates. Its `PENDING_MIGRATION` table lists the call sites not
  migrated yet; delete an entry in the same change that migrates it.

The `SDK head` workflow re-runs the suite against the newest SDK `main`
commit on every pull request into `next` and reports drift without blocking.

## Release day

When ksef2 1.0.0 is on PyPI, in one commit on `next`: delete the
`[tool.uv.sources]` table, set the dependency to `ksef2>=1.0,<2`, and run
`uv lock -P ksef2`. Then merge `next` into `main`.
