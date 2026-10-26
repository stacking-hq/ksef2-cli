# Contributing

## Branches and the SDK line

| Branch | SDK it runs on | Use it for |
| --- | --- | --- |
| `main` | `ksef2` 0.22.x from PyPI | Fixes for the released 0.x CLI line. |
| `next` | `ksef2` 1.0 from the SDK's release branch | Everything on the ksef2 1.0 API. |

Open 1.0 work as a pull request into `next`.

`next` is version 1.0.0, and both `pyproject.toml` and the built wheel metadata
declare `ksef2>=1.0,<2`. That bound is final: the published CLI refuses any SDK
outside it, including the 0.22.x SDK `main` installs today, and
`tests/unit/test_release_metadata.py` fails if the project version, the declared
bounds, `ksef2_cli.__version__`, or the locked SDK drift apart.

The ksef2 1.0 release is not on PyPI yet (tracked in `stacking-hq/ksef2#147`), so
`>=1.0,<2` cannot be satisfied from an index. Development resolves it through a
temporary `[tool.uv.sources]` entry that installs ksef2 from
`https://github.com/stacking-hq/ksef2` `chore/08-release-1-0-0`, and `uv.lock` pins
the exact SDK commit. That table is uv-only config and never reaches the wheel, so
the override does not weaken what a published package requires. Until the SDK ships:

- do not describe a published 1.0 release, and do not write install instructions that
  imply `pip install ksef2-cli` resolves an SDK satisfying `>=1.0,<2`;
- work from a checkout, and say so when a doc or issue comment needs the 1.0 API.

```bash
uv sync --all-groups
grep -A2 '^name = "ksef2"$' uv.lock   # which SDK commit you are on
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

When ksef2 1.0.0 is on PyPI, in one commit on `next`: delete the
`[tool.uv.sources]` table and run `uv lock -P ksef2`. The `>=1.0,<2` specifiers in
`dependencies` and in the `pdf` extra need no change; they are already final.
