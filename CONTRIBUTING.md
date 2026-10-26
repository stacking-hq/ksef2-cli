# Contributing

## Branches and the SDK line

| Branch | SDK it runs on | Use it for |
| --- | --- | --- |
| `main` | `ksef2` 1.1 or newer from PyPI | Released CLI 1.x. |
| `next` | `ksef2` 1.1 or newer from PyPI | Integration for the next CLI release. |

Open 1.0 work as a pull request into `next`.

`next` is version 1.0.0, and both `pyproject.toml` and the built wheel metadata
declare `ksef2>=1.1,<2`. The minimum includes certificate-retrieval and offline
PDF lookup fixes. The published CLI refuses older SDKs, and
`tests/unit/test_release_metadata.py` fails if the project version, the declared
bounds, `ksef2_cli.__version__`, or the locked SDK drift apart.

ksef2 1.1.0 is on PyPI, so `uv sync` resolves the SDK from the
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

The SDK's own docs describe the 1.x API: `docs/en/reference/public-api.md`
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

Before the tag, on `next`, resolve the published SDK and build the CLI:

```bash
uv lock -P ksef2                      # the SDK entry resolves from PyPI
grep -A2 '^name = "ksef2"$' uv.lock   # 1.1 or newer, from the registry
uv build
```

Then install the built package into a clean environment that can only reach the index,
and run `ksef2 --version`. That proves the release against the published SDK instead of
a checkout. Merge the verified release into `main`, then push the matching
`v<version>` tag. The Publish workflow tests, builds, publishes to PyPI, and
dispatches the documentation deployment.
