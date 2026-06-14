---
title: Configuration
description: Use environment variables, output modes, and local config files with KSeF2 CLI.
---

KSeF2 CLI can run without any local config file. This is the preferred mode for
CI and shared machines. Use environment variables or secret-manager injection for
credentials.

Local config files are useful on a developer workstation when you repeatedly use
the same non-secret defaults.

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

## Create local defaults

```bash
uv run ksef2 config init --nip 5261040828
```

The CLI writes the file with mode `0600`.

## Inspect local config

```bash
uv run ksef2 config show
```

Token and credential passwords are always masked in CLI output.

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
| `KSEF2_NIP` | Taxpayer or context NIP |
| `KSEF2_TOKEN` | KSeF token authentication secret |
| `KSEF2_CONTEXT_TYPE` | Token-auth context type |
| `KSEF2_TEST_CERT` | Enable SDK-generated TEST certificate authentication |
| `KSEF2_CERT` | PEM certificate path |
| `KSEF2_KEY` | PEM private key path |
| `KSEF2_KEY_PASSWORD` | PEM private key password |
| `KSEF2_P12` | PKCS#12/PFX archive path |
| `KSEF2_P12_PASSWORD` | PKCS#12/PFX password |
