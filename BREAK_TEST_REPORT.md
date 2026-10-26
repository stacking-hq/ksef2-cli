# Break-test fixes, 2026-10-25

Implementation of the supplied report against `next` at `3d6ff07`.
GPT-6.1 handled implementation and integration; Pi/Qwen 3.8 handled release
metadata and documentation. Changes are local, with no publishing or live KSeF calls.

## Validation

- `uv run python -m coverage run -m pytest -q`: 602 passed, 1 skipped.
- `uv run python -m coverage report`: 96%, above the required 85%.
- `uv build`: wheel and source distribution built for 1.0.0.
- Generated command reference is current; frontmatter validation and
  `git diff --check` pass.
- Fresh installation with an explicitly built SDK 1.0 wheel runs `--help`.
  PyPI-only installation correctly refuses SDK 0.22.2.
- Seven expected SDK deprecation warnings remain for reference-only batch
  reads. The precise calls are recorded in `PENDING_MIGRATION`; the SDK's
  session-client replacement requires encryption state that a reference does
  not contain. No dummy encryption state is constructed.

## Release blockers

- **B1:** Both package dependencies require `ksef2>=1.0,<2`, including the PDF
  extra. The wheel no longer permits the incompatible SDK. SDK 1.0 is not
  published on PyPI at verification time, so the development git override
  remains. After publication, remove `[tool.uv.sources]`, refresh the lock,
  and repeat the clean index-only installation before release.
- **B2:** Reference-based batch status, list, UPO and receipt continuation use
  the reference service APIs. Regression tests exercise real SDK clients with
  fake HTTP transports, including all three previously failing receipt cases.
- **B3:** Package and module versions are 1.0.0; eager `--version` prints CLI
  and SDK versions without loading configuration.

## Bugs and usability

- **BG1, BG4–BG7, D1, D13:** TEST is the fallback environment. Explicit
  environment/profile selection remains supported. NIPs are validated;
  test certificates are rejected outside TEST before client construction.
  Missing profiles identify `--profile`. `profile current` honors
  `--no-config`. Deletion checks existence first, requires `--yes`/`-y`
  without a terminal, and handles interrupted confirmation without a bug URL.
- **BG2–BG3:** Batch results include an item per input; after waiting, items
  carry available KSeF numbers and rejection descriptions, including duplicate
  reasons. A completed result containing rejected invoices still goes to
  stdout and exits 1.
- **BG8–BG9, D2–D3:** JSON command errors go to stderr with an error envelope;
  usage parsing is covered. Text output avoids duplicate API metadata.
  Validation messages omit Pydantic documentation URLs. Wrapping-sensitive
  test assertions are normalized.
- **BG10:** SIGINT exits 130. High-level sends persist requested receipts
  before waiting and report submitted references if waiting is interrupted.
  This is not a rollback, and the user must check status before resending.
- **D4–D5:** Authentication output masks tokens in both formats. Saved auth
  state supports refresh and is updated with refreshed credentials.
- **D6:** Resumed online sessions stay open by default; sessions opened by
  `online send` close by default. Explicit `--close` and `--keep-open` override
  that choice.
- **D7:** Draft examples generate the current UTC timestamp.
- **D8:** Help descriptions and hidden `None` defaults were improved.
  Download and FA(3) inspection accept compatible positional aliases while
  retaining existing options. The generated command reference was refreshed.
- **D9:** Online and batch sends accept one stdin input, preserve its bytes
  in memory, avoid plaintext temporary files and choose a collision-free
  receipt name. Empty/invalid input fails before authentication.
- **D10–D12:** FA(3) inspection has readable text output. Invalid date ranges
  report effective UTC bounds. Invoice encoding/BOM problems are detected
  locally without silently rewriting signed XML.
- **D14:** Informational finding; no change needed.

Documentation explains exit codes, environment selection, masked output,
plaintext credential/state files with mode 0600, session lifetime, and
recovery after interruption. Bug-report URLs redact home and virtualenv paths.

## Verification limits

- **V1:** The timestamp fix is tested locally. KSeF's classification of an
  online submission as offline, and its cause, remain unverified.
- **V2:** Real SDK/fake HTTP tests cover logout and access-token refresh before
  logout. They do not prove when KSeF invalidates a previously copied token.
- **V3:** TEST-certificate restrictions are verified before network/client
  construction, including profile/environment overrides.
- **V4:** Missing PDF dependencies are checked before scheduling an export.
  The real local PDF smoke test is skipped because optional dependencies are
  unavailable; rendering with system libraries remains to be verified.
- **V5:** Generated encrypted PEM/P12 credentials and wrong-password rejection
  are tested locally. Real certificate authentication remains unverified.
- **V6:** Local contract tests cover retrying exact prepared parts, avoiding
  upload once processing has started, and recovery after submitted waits.
  Actual SIGINT during a remote upload, especially before the SDK returns a
  reference/state, remains unverified.

No issue was closed, no PR or release was published, and no live invoice,
permission, token or certificate was created or modified.
