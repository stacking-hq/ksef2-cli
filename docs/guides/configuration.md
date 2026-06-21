---
title: Configuration
description: Use profiles, environment variables, output modes, and local config files with KSeF2 CLI.
---

KSeF2 CLI can run without any local config file. This is the preferred mode for
CI and shared machines. On a developer workstation, create named profiles so
daily commands do not repeat `--env`, `--nip`, and authentication paths.

## Show the active config path

```bash
uv run ksef2 config path
```

By default, the CLI uses:

```text
~/.config/ksef2-cli/config.toml
```

Override the path with `--config` or `KSEF2_CONFIG`:

```bash
uv run ksef2 --config ./local.ksef2.toml config path
```

## Create a profile

```bash
uv run ksef2 profile create demo-client \
  --env test \
  --nip 6880313213 \
  --cert /path/accountant-auth-cert.pem \
  --key /path/accountant-auth-key.pem
```

`profile create` selects the new profile by default. Use `--no-activate` when
you only want to save it.

Token profiles store the environment variable name, not the token value:

```bash
uv run ksef2 profile create prod-client \
  --env production \
  --nip 5261040828 \
  --token-env KSEF2_PROD_TOKEN
```

## Select a profile

```bash
uv run ksef2 profile use demo-client
uv run ksef2 profile current
uv run ksef2 profile list
```

Use a different profile for one command:

```bash
uv run ksef2 --profile prod-client invoices metadata --date-from 2026-01-01T00:00:00Z
```

Or select one for the current shell:

```bash
export KSEF2_PROFILE=demo-client
```

## Inspect local config

```bash
uv run ksef2 config show
uv run ksef2 profile show demo-client
```

The config file stores profile names, environments, NIPs, credential file paths,
and secret environment variable names. It should not contain token or password
values.

Example config:

```toml
active_profile = "demo-client"

[profiles.demo-client]
environment = "test"
nip = "6880313213"

[profiles.demo-client.auth]
type = "xades_pem"
cert = "/path/accountant-auth-cert.pem"
key = "/path/accountant-auth-key.pem"
```

## Ignore local config once

```bash
uv run ksef2 --no-config --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices metadata --role seller --date-from 2026-01-01T00:00:00Z
```

## Output modes

The default output mode is plain text for humans:

```bash
uv run ksef2 invoices metadata --date-from 2026-01-01T00:00:00Z
```

Use `--json` or `--output json` for scripts:

```bash
uv run ksef2 --json invoices metadata --date-from 2026-01-01T00:00:00Z
```

## Common environment variables

| Variable | Purpose |
| --- | --- |
| `KSEF2_CONFIG` | Local config file path |
| `KSEF2_PROFILE` | Profile name for this shell/session |
| `KSEF2_NIP` | Taxpayer or context NIP override |
| `KSEF2_TOKEN` | KSeF token authentication secret override |
| `KSEF2_CONTEXT_TYPE` | Token-auth context type override |
| `KSEF2_TEST_CERT` | Enable SDK-generated TEST certificate authentication |
| `KSEF2_CERT` | PEM certificate path override |
| `KSEF2_KEY` | PEM private key path override |
| `KSEF2_KEY_PASSWORD` | PEM private key password override |
| `KSEF2_P12` | PKCS#12/PFX archive path override |
| `KSEF2_P12_PASSWORD` | PKCS#12/PFX password override |
