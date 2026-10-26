---
title: Configuration
description: Use profiles, environment variables, output modes, and local config files with KSeF2 CLI.
---

KSeF2 CLI can run without any local config file. This is the preferred mode for
CI and shared machines. On a developer workstation, create named profiles so
daily commands do not repeat `--env`, `--nip`, and authentication paths.
The SDK can read the same profile file through
`client.authentication.with_profile()`.

Without a profile and without `--env`, the environment is `test`. A profile carries
the environment when you do not name one, and `--env` beats the profile, so production
work needs either `--env production` or a profile that says
`environment = "production"`.

## Show the active config path

```bash
uv run ksef2 config path
```

By default, the CLI uses:

```text
~/.config/ksef2/config.toml
```

That is the same file the SDK reads, so `ksef2 profile create` and
`client.authentication.with_profile()` share one source of truth. A config left
over at the older `~/.config/ksef2-cli/config.toml` is still picked up while no
`~/.config/ksef2/config.toml` exists, and keeps being written to until you move
it yourself.

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

Store a longer authentication wait with the profile itself when the default one is
too short. `--poll-interval` is the delay between status checks and
`--max-poll-attempts` the number of checks, so the profile below waits
`2.0 * 90 = 180` seconds:

```bash
uv run ksef2 profile create slow-prod \
  --env production \
  --nip 5261040828 \
  --token-env KSEF2_PROD_TOKEN \
  --poll-interval 2.0 \
  --max-poll-attempts 90
```

Both settings stay unset when you omit them, and the SDK reads them the same way,
so `client.authentication.with_profile()` polls to the same deadline. The two
fields appear in `profile show` once the profile carries them.

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

## Delete a profile

```bash
uv run ksef2 profile delete demo-client
```

The command asks for confirmation, and removing the selected profile leaves no
profile active. JSON output has no prompt to answer, so it needs `--yes`:

```bash
uv run ksef2 --json profile delete demo-client --yes
```

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

Profile names, environment values, auth type strings, and field names are the SDK
profile models themselves, not a CLI copy of them. `poll_interval` is the delay
between status checks and `max_poll_attempts` the number of checks, so
authenticating with `prod-client` waits `2.0 * 90 = 180` seconds.

Older CLI releases wrote a flat `auth_timeout = 180.0` seconds instead. That key is
not part of the SDK schema and is ignored, so move it to
`max_poll_attempts = round(auth_timeout / poll_interval)` to keep the same wait.

## Ignore local config once

```bash
uv run ksef2 --no-config --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices metadata --role seller --date-from 2026-01-01T00:00:00Z
```

`--no-config` and `--profile` together fail with exit `2`, and so does a `--profile`
name the config file does not define.

## Output modes

The default output mode is plain text for humans:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices metadata --date-from 2026-01-01T00:00:00Z
```

Use `--json` or `--output json` for scripts:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  invoices metadata --date-from 2026-01-01T00:00:00Z
```

### Where output goes

Success is written to stdout: the text form, or one JSON document in `--json` mode.
Nothing else is written there, so `ksef2 --json ... > out.json` captures exactly one
value.

Command errors go to stderr and leave stdout empty. Check the exit code before
parsing stdout. A completed `invoices send` with rejected items writes its result
to stdout and exits 1. For command errors, text mode prints human lines and
`--json` mode prints one object:

```bash
uv run ksef2 --json auth login --token 2>error.json
```

```json
{
  "error": {
    "type": "RemoteServiceError",
    "title": "KSeF rejected the request",
    "message": "KSeF rejected the request.",
    "details": [],
    "hints": [],
    "exit_code": 1,
    "ksef": {
      "status_code": 400,
      "exception_code": 21405,
      "message": "Validation error",
      "ksef_code": 21405,
      "trace_id": "0f6c…"
    }
  }
}
```

| Key | Content |
| --- | --- |
| `type` | The CLI error class, such as `RemoteServiceError`, `AuthenticationConfigError`, `ConfigError`, or `FileCliError`; `UsageError` when the command line itself was rejected. |
| `title` | The short summary the CLI chose for this failure. |
| `message` | One human-readable sentence about the failure. |
| `details`, `hints`, `exit_code` | Always present. The two lists are empty when the CLI has nothing to add. |
| `ksef` | Present when KSeF answered. Carries that service's `status_code`, `exception_code`, and `message`, plus `ksef_code`, `trace_id`, `details`, or `response` when the CLI has them. Quote `trace_id` when you report an incident. |
| `report_url` | Present on an error the CLI treats as a bug. |
| `traceback` | Present with `--verbose`, and only for such an error. |

Any secret the CLI recognized on the command line or in its secret environment
variables is replaced with `<redacted>` inside the payload before it is encoded.

### Exit codes

| Exit code | Meaning |
| --- | --- |
| `0` | Success. |
| `1` | Runtime failure: KSeF rejected or timed out on the request, credentials are missing or contradictory, a file operation failed. |
| `2` | Usage failure: unknown option or command, missing argument, a value that fails its check such as an NIP with a bad checksum, or a `--profile` that does not exist. |
| `130` | Interrupted with Ctrl-C. |

A high-level send is its own case: `invoices send` prints every per-file result and
then exits `1` when any file failed, so read the items before concluding nothing was
submitted. `130` is not a rollback either; see
[An interrupted send is not an unsubmitted invoice](invoices.md#an-interrupted-send-is-not-an-unsubmitted-invoice).

## Secrets in the files this CLI writes

Every continuation file the CLI writes is credential material, and each is written
with mode `0600`:

| File | Holds |
| --- | --- |
| `auth login --save-state` | The access and refresh bearer tokens, in plain text. |
| `online open --state-file`, `online send --save-state` | The online session AES key and IV. |
| `--receipt`, `--receipt-dir` from an online send | The same session state again, because an online receipt is resumable session state. |
| `--handle-file` on an export | The export decryption key and IV. |
| `batch prepare --out` | The batch session key, next to the encrypted invoice payloads. |
| `batch submit --state-file` | The batch session key and the prepared-package digest. |

`0600` says only that other users on that machine cannot open the file. It is not
encryption: the bytes are readable to whoever owns the file and to anything running as
that user, and the mode does not survive a `chmod`-preserving copy, a tarball, a
Docker layer, or a commit. Keep these files outside the repository, list them in
`.gitignore`, prefer a private directory such as `$XDG_RUNTIME_DIR` on a shared
machine, and delete them when the workflow ends: `auth logout` removes the auth state
file it was pointed at, once KSeF confirms the session ended.

## Common environment variables

| Variable | Purpose |
| --- | --- |
| `KSEF2_CONFIG` | Local config file path |
| `KSEF2_PROFILE` | Profile name for this shell/session |
| `KSEF2_NIP` | Taxpayer or context NIP override |
| `KSEF2_TOKEN` | KSeF token authentication secret override |
| `KSEF2_CONTEXT_TYPE` | Token-auth context type override |
| `KSEF2_AUTH_STATE` | Saved auth state to reuse instead of authenticating |
| `KSEF2_REFRESH_TOKEN` | Refresh token for `auth refresh`, off the command line |
| `KSEF2_TEST_CERT` | Enable SDK-generated TEST certificate authentication |
| `KSEF2_CERT` | PEM certificate path override |
| `KSEF2_KEY` | PEM private key path override |
| `KSEF2_KEY_PASSWORD` | PEM private key password override |
| `KSEF2_P12` | PKCS#12/PFX archive path override |
| `KSEF2_P12_PASSWORD` | PKCS#12/PFX password override |

The `KSEF2_*` names above are what the CLI reads on its own. A profile names its own
secret variables, such as `auth.token_env`, and those names are yours to choose.
