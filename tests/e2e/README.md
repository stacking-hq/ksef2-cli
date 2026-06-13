# E2E Tests

This directory is reserved for smoke tests that execute the installed `ksef2`
console script against a real external environment, for example the official
TEST API.

The current suite intentionally keeps live-network behavior out of the default
test run. Command behavior is covered in `tests/component/` with fake SDK
clients and deterministic fixtures.
