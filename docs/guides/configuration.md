---
title: Configuration
description: Use profiles, environment variables, output modes, and local config files with KSeF2 CLI.
---

KSeF2 CLI can run without any local config file. This is the preferred mode for
CI and shared machines. On a developer workstation, create named profiles so
daily commands do not repeat `--env`, `--nip`, and authentication paths.
The SDK can read the same profile file through
`client.authentication.with_profile()`.

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
  --nip 5261040828 \
  --test-cert
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

Certificate profiles store file paths and optional password environment
variable names:

```bash
uv run ksef2 profile create demo-pem \
  --env demo \
  --nip 5261040828 \
  --cert company.pem \
  --key company.key \
  --key-password-env KSEF2_KEY_PASSWORD

uv run ksef2 profile create prod-p12 \
  --env production \
  --nip 5261040828 \
  --p12 signing-credentials.p12 \
  --p12-password-env KSEF2_P12_PASSWORD
```

## Select a profile

```bash
uv run ksef2 profile use demo-client
uv run ksef2 profile current
uv run ksef2 profile list
```

Use a different profile for one command:

```bash
uv run ksef2 --profile prod-client --json \
  invoices metadata \
  --date-from 2026-01-01T00:00:00Z
```

Or select one for the current shell:

```bash
export KSEF2_PROFILE=demo-client
```

Selection order is:

1. `--profile NAME` on the current command.
2. `KSEF2_PROFILE` in the environment.
3. `active_profile` saved in the config file.

`KSEF2_PROFILE` affects runtime settings only. Use `profile use NAME` when you
want to change the saved active profile.

## Inspect local config

```bash
uv run ksef2 config show
uv run ksef2 profile show demo-client
```

The config file stores profile names, environments, NIPs, credential file paths,
polling settings, and secret environment variable names. It should not contain
token or password values.

Example config:

```toml
active_profile = "demo-client"

[profiles.demo-client]
environment = "test"
nip = "5261040828"

[profiles.demo-client.auth]
type = "test_certificate"

[profiles.prod-client]
environment = "production"
nip = "5261040828"
poll_interval = 2.0
max_poll_attempts = 90

[profiles.prod-client.auth]
type = "token"
token_env = "KSEF2_PROD_TOKEN"
context_type = "nip"

[profiles.demo-pem]
environment = "demo"
nip = "5261040828"

[profiles.demo-pem.auth]
type = "xades_pem"
cert = "company.pem"
key = "company.key"
key_password_env = "KSEF2_KEY_PASSWORD"

[profiles.prod-p12]
environment = "production"
nip = "5261040828"

[profiles.prod-p12.auth]
type = "xades_p12"
p12 = "signing-credentials.p12"
p12_password_env = "KSEF2_P12_PASSWORD"
```

Profile names, environment values, auth type strings, and field names match the
SDK profile models.

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
