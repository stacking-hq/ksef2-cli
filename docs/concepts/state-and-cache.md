---
title: Local State and Files
description: How KSeF2 CLI stores profiles, receipts, session state, and export handles.
---

KSeF2 CLI separates long-lived profile configuration from workflow state that
you explicitly ask a command to save. The CLI does not maintain a hidden invoice
metadata cache.

## Profile configuration

New installations store profiles in:

```text
~/.config/ksef2/config.toml
```

When that file does not exist, the CLI continues to read the legacy
`~/.config/ksef2-cli/config.toml` file. An explicit `--config` option or
`KSEF2_CONFIG` value always takes precedence.

The profile file stores environments, NIPs, authentication method choices,
credential file paths, and the names of environment variables that contain
secrets. It should not contain KSeF tokens, private-key passwords, or PKCS#12
passwords.

## Command-owned state

Stateful workflows write files only when you provide the corresponding option:

- `invoices send --receipt` and `--receipt-dir` write high-level workflow receipts;
- `online open --state-file` and `online send --save-state` write resumable online-session state;
- `batch submit --state-file` writes resumable batch-session state;
- `invoices export --handle-file` writes the decryption handle required to fetch an export later;
- invoice and UPO download commands write to the output path you select.

These files belong to the command that creates them. Their location is not
derived from the profile configuration path.

## Security and cleanup

Treat saved workflow state as sensitive operational data. Depending on the
workflow, a file can contain authentication capabilities, encryption material,
session references, or identifiers that should not be committed to source
control. Store it with restricted permissions and remove it when the workflow
is complete.

Use separate directories for TEST, DEMO, and PRODUCTION automation so state
from one environment cannot be selected accidentally in another.
