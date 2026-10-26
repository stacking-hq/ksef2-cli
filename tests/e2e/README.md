# E2E Tests

`release_smoke.py` executes an installed `ksef2` console script against the
official TEST API. It creates three uniquely numbered invoices, checks online
and batch submission, receipts, reference reads, UPO, byte-exact download, and PDF
rendering and export. It logs out its authentication session at the end.

The current suite intentionally keeps live-network behavior out of the default
test run. Command behavior is covered in `tests/component/` with fake SDK
clients and deterministic fixtures.

Install the built wheel with its PDF extra in a clean virtual environment, then
run the script with a new output directory:

```bash
python tests/e2e/release_smoke.py \
  --cli /absolute/path/to/venv/bin/ksef2 \
  --work-dir /absolute/path/to/new-smoke-directory \
  --allow-test-writes
```

The script explicitly selects TEST, ignores profiles and `KSEF2_*` environment
variables, and uses a generated TEST certificate for NIP 5261040828. Invoices
remain in TEST after the run. A failed send is not retried: inspect the saved
receipt and command logs before sending again.

PDF rendering needs the optional dependencies and system libraries documented in
[Installation](../../docs/getting-started/installation.md#pdf-rendering). On Apple
Silicon, set `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` when invoking the script
if the dynamic loader does not find the Homebrew libraries.
