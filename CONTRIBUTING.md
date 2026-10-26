# Contributing

## Branches and the SDK line

| Branch | SDK it runs on | Use it for |
| --- | --- | --- |
| `main` | `ksef2` 0.22.x from PyPI | Fixes for the released 0.x CLI line. |
| `next` | `ksef2` 1.0 from PyPI | Everything on the ksef2 1.0 API. |

Open 1.0 work as a pull request into `next`.

`next` is version 1.0.0, and both `pyproject.toml` and the built wheel metadata
declare `ksef2>=1.0,<2`. That bound is final: the published CLI refuses any SDK
outside it, including the 0.22.x SDK `main` installs today, and
`tests/unit/test_release_metadata.py` fails if the project version, the declared
bounds, `ksef2_cli.__version__`, or the locked SDK drift apart.

ksef2 1.0.0 has been on PyPI since 2026-10-26, so `uv sync` resolves the SDK from the
index. There is no `[tool.uv.sources]` override, and re-adding one needs a reason as
strong as the SDK release it replaced:

```bash
uv sync --all-groups
grep -A2 '^name = "ksef2"$' uv.lock   # which SDK version you are on
```

`uv.lock` is what makes a development install reproducible. If you change it, refresh
only the SDK entry and commit the lock on its own:

```bash
uv lock -P ksef2
```

To try an SDK change before it is pushed, overlay a local checkout for one command
without touching the lock:

```bash
uv run --with-editable ../ksef2 pytest -q
```

The SDK's own docs describe the 1.0 API: `docs/en/reference/public-api.md`
(stable imports and the deprecated-to-replacement table) and
`docs/en/reference/migration-1-0.md` in the SDK repository.

The CLI is the half still unpublished. PyPI carries ksef2-cli 0.0.1, not 1.0.0, so a
doc, an issue comment, or a PR description that needs the 1.0 API says "from a
checkout" and never implies `pip install ksef2-cli` gives you 1.0.

Check what a command actually resolved, CLI and SDK together:

```bash
uv run ksef2 --version   # ksef2-cli <version> / ksef2 <version>
```

`--version` is a root option, read before the config file is touched, and it prints
plain text in every output mode.

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

Every `docs/**/*.md` page keeps its YAML frontmatter: the file must open with a
`---` line and close it before any content, and the validator fails the page when
that block is missing. `docs/README.md` and everything under `docs/assets/` are the
only exemptions.

Two tests keep the CLI on the supported SDK surface:

- `tests/unit/test_public_sdk_imports.py` fails on imports from private or
  legacy internal ksef2 modules.
- `tests/unit/test_no_deprecated_sdk_calls.py` fails on calls to SDK methods
  that 1.0 deprecates. Its `PENDING_MIGRATION` table lists the call sites not
  migrated yet; delete an entry in the same change that migrates it.

The `SDK head` workflow re-runs the suite against the newest SDK `main`
commit on every pull request into `next` and reports drift without blocking.

## Release day

The SDK half is done: ksef2 1.0.0 is on PyPI, `pyproject.toml` has no source override,
and the `>=1.0,<2` specifiers in `dependencies` and in the `pdf` extra need no change.
What is left is publishing ksef2-cli 1.0.0 itself. Before the tag, on `next`:

```bash
uv lock -P ksef2                      # the SDK entry resolves from PyPI
grep -A2 '^name = "ksef2"$' uv.lock   # 1.0.x, from the registry
uv build
```

Then install the built package into a clean environment that can only reach the index,
and run `ksef2 --version`. That proves the release against the published SDK instead of
a checkout.
