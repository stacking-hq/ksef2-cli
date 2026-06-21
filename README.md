<div align="center">
<a href="https://github.com/stacking-hq/ksef2-cli" title="ksef2-cli">
  <img src="docs/assets/banner.png" alt="ksef2-cli logo" width="50%">
</a>

**Command-line interface for the [`ksef2`](https://github.com/stacking-hq/ksef2) Python SDK.**

</div>

The CLI avoids hidden state: authenticated commands accept credentials from global
options or environment variables, and resumable workflow files are written only
when you pass options such as `--receipt`, `--receipt-dir`, or `--state-file`.

## Install / Run

```bash
pip install ksef2-cli
ksef2 --help
```

For an isolated CLI install:

```bash
uv tool install ksef2-cli
# or
pipx install ksef2-cli
```

The package exposes scriptable CLI commands:

```bash
ksef2
ksef2-cli
```

## Documentation

Published documentation is assembled into <https://docs.ksef2.dev/cli/>.
Source documentation lives in [`docs/`](docs/).

## Authentication

For repeated local work, create a profile once and let commands inherit its
environment, NIP, and authentication settings:

```bash
uv run ksef2 profile create demo-client \
  --env test \
  --nip 6880313213 \
  --cert /path/accountant-auth-cert.pem \
  --key /path/accountant-auth-key.pem

uv run ksef2 invoices metadata --role buyer --date-from 2026-01-01T00:00:00Z
```

Global auth options are still available for CI and one-off commands. They must
be placed before the command group:

```bash
uv run ksef2 --env test --nip 5261040828 --test-cert auth login --json
uv run ksef2 --nip 5261040828 --token "$KSEF_TOKEN" invoices metadata --date-from 2026-01-01T00:00:00Z
```

Supported direct auth methods:

- `--token` / `KSEF2_TOKEN`
- `--test-cert` for the TEST environment
- `--cert` and `--key` for PEM XAdES credentials
- `--p12` for PKCS#12/PFX XAdES credentials

Common environment variables:

```bash
export KSEF2_PROFILE=demo-client
export KSEF2_NIP=5261040828
export KSEF2_TOKEN=...
```

Precedence is:

1. CLI options such as `--profile`, `--nip`, and `--token`
2. Environment variables such as `KSEF2_PROFILE`, `KSEF2_NIP`, and `KSEF2_TOKEN`
3. The active profile in the local config file

## Local Config

For local development, create profiles under your home directory:

```bash
uv run ksef2 profile create demo-client --env test --nip 5261040828 --test-cert
uv run ksef2 profile current
uv run ksef2 profile list
```

By default the file is:

```text
~/.config/ksef2-cli/config.toml
```

You can override it with `--config path/to/config.toml` or `KSEF2_CONFIG`.
Use `--no-config` to ignore the file for one invocation.

Example config:

```toml
active_profile = "demo-client"

[profiles.demo-client]
environment = "test"
nip = "5261040828"

[profiles.demo-client.auth]
type = "test_certificate"
```

Profiles store token and password environment variable names rather than secret
values.

## Examples

Query invoice metadata:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices metadata --role seller --date-from 2026-01-01T00:00:00Z --all
```

Download one processed invoice XML:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices download --ksef-number "$KSEF_NUMBER" --out invoice.xml
```

Schedule and fetch an export:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices export --date-from 2026-01-01T00:00:00Z --handle-file export.json

uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices export-fetch --handle-file export.json --wait --out-dir downloads
```

Send one invoice and save its UPO:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  invoices send invoice.xml --wait --upo-dir upos
```

Send every XML file in a directory and save receipts for later status/UPO checks:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  invoices send invoices/ --receipt-dir receipts
```

Fetch a UPO later from a receipt:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  invoices upo --receipt receipts/invoice-receipt.json --out invoice-upo.xml
```

Submit invoices as one batch:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices send invoice-1.xml invoice-2.xml --mode batch --wait --upo-dir upos
```

The lower-level `online` and `batch` command groups remain available when you
need explicit session control.

Permission queries and TEST limit updates use JSON payloads shaped like the SDK
models:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  permissions query persons --payload person-query.json

uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  limits set api --payload api-rate-limits.json
```

Use `--json` for script-friendly output.

## Maintainability

The CLI is split by command domain under `src/ksef2_cli/commands/`, with shared
runtime, auth, rendering, parsing, JSON I/O, and invoice workflow modules.
See [docs/contributing/architecture.md](docs/contributing/architecture.md) for
the module map and the rules for adding new commands without growing large files
again.
