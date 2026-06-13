---
title: Command Reference
description: Command groups and subcommands exposed by KSeF2 CLI.
---

Global options must be placed before the command group:

```bash
ksef2 [GLOBAL OPTIONS] COMMAND [ARGS]...
```

## Global options

| Option | Purpose |
| --- | --- |
| `--env`, `-e` | KSeF environment: `production`, `demo`, or `test`. |
| `--output`, `-o` | Output mode: `table` or `json`. |
| `--json` | Shortcut for `--output json`. |
| `--verbose`, `-v` | Show tracebacks for CLI errors. |
| `--config` | Local config file path. |
| `--no-config` | Ignore local config defaults. |
| `--nip` | Taxpayer or context NIP. |
| `--token`, `--ksef-token` | KSeF token authentication secret. |
| `--context-type` | Token-auth context type. |
| `--test-cert` | Use an SDK-generated TEST certificate. |
| `--cert`, `--key` | PEM XAdES certificate and private key. |
| `--key-password` | Password for encrypted PEM private key. |
| `--p12`, `--p12-password` | PKCS#12/PFX XAdES archive and password. |
| `--auth-poll-interval` | Authentication polling interval. |
| `--auth-max-poll-attempts` | Authentication polling attempts. |

## Command groups

| Group | Purpose |
| --- | --- |
| `auth` | Authenticate and refresh access tokens. |
| `invoices` | Query, download, export, and fetch invoices. |
| `online` | Open, resume, inspect, and close online invoice sessions. |
| `batch` | Submit and inspect batch invoice sessions. |
| `tokens` | Generate, list, inspect, and revoke KSeF tokens. |
| `sessions` | Inspect authentication and historical invoice sessions. |
| `certificates` | Manage MCU certificate enrollment and lifecycle. |
| `permissions` | Grant, query, and revoke permissions. |
| `limits` | Read and manage effective KSeF limits. |
| `peppol` | Query public PEPPOL providers. |
| `encryption` | Read public KSeF encryption certificates. |
| `testdata` | Manage TEST-environment test data. |
| `config` | Inspect and create local CLI defaults. |

## Subcommands

### `auth`

| Command | Purpose |
| --- | --- |
| `auth login` | Authenticate with the configured method and print tokens. |
| `auth refresh` | Exchange a refresh token for a new access token. |

### `config`

| Command | Purpose |
| --- | --- |
| `config path` | Show the local config path used by this invocation. |
| `config show` | Show local config values. |
| `config init` | Create a local config file with auth defaults. |

### `invoices`

| Command | Purpose |
| --- | --- |
| `invoices metadata` | Query invoice metadata. |
| `invoices download` | Download processed invoice XML by KSeF number. |
| `invoices export` | Schedule an invoice export and save the handle. |
| `invoices export-status` | Fetch invoice export status. |
| `invoices export-fetch` | Fetch and decrypt an export package using a saved handle. |
| `invoices export-download` | Schedule, wait for, and download an export package. |

### `online`

| Command | Purpose |
| --- | --- |
| `online open` | Open an online session and optionally save state. |
| `online send` | Send one or more invoice XML files. |
| `online status` | Fetch status for a resumed online session. |
| `online list` | List invoices submitted in an online session. |
| `online invoice-status` | Fetch or wait for one invoice status. |
| `online upo` | Download invoice UPO by reference or KSeF number. |
| `online close` | Close a resumed online session. |

### `batch`

| Command | Purpose |
| --- | --- |
| `batch submit` | Prepare, upload, close, and optionally wait for a batch session. |
| `batch status` | Fetch or wait for batch session status. |
| `batch list` | List invoices submitted in a batch session. |
| `batch upo` | Download a collective UPO page. |

### `sessions`

| Command | Purpose |
| --- | --- |
| `sessions auth-list` | List authentication sessions. |
| `sessions auth-close` | Close an authentication session. |
| `sessions auth-terminate-current` | Terminate the current authentication session. |
| `sessions invoice-list` | List historical invoice sessions. |

### `tokens`

| Command | Purpose |
| --- | --- |
| `tokens generate` | Generate a KSeF token. |
| `tokens list` | List KSeF tokens. |
| `tokens status` | Fetch token status. |
| `tokens revoke` | Revoke a token. |

### `certificates`

| Command | Purpose |
| --- | --- |
| `certificates limits` | Show certificate limits. |
| `certificates enrollment-data` | Fetch certificate enrollment data. |
| `certificates enroll` | Submit a certificate enrollment request. |
| `certificates enrollment-status` | Check enrollment status. |
| `certificates list` | List certificates. |
| `certificates retrieve` | Retrieve a certificate. |
| `certificates revoke` | Revoke a certificate. |

### `permissions`

| Command | Purpose |
| --- | --- |
| `permissions attachment-status` | Check attachment permission status. |
| `permissions operation-status` | Check permission operation status. |
| `permissions entity-roles` | List entity roles. |
| `permissions grant-person` | Grant permissions to a person. |
| `permissions grant-entity` | Grant permissions to an entity. |
| `permissions grant-authorization` | Grant authorization permissions. |
| `permissions grant-indirect` | Grant indirect permissions. |
| `permissions grant-subunit` | Grant subunit administrator permissions. |
| `permissions grant-eu-entity` | Grant EU entity representative permissions. |
| `permissions grant-eu-admin` | Grant EU entity administrator permissions. |
| `permissions query` | Query permissions by type. |
| `permissions revoke-common` | Revoke a common permission. |
| `permissions revoke-authorization` | Revoke an authorization permission. |

### `limits`

| Command | Purpose |
| --- | --- |
| `limits get` | Read effective limits. |
| `limits set` | Set effective limits in TEST workflows. |
| `limits reset` | Reset effective limits in TEST workflows. |
| `limits production-rate-limits` | Set TEST API rate limits to production-like values. |

### Public data and TEST data

| Command | Purpose |
| --- | --- |
| `peppol providers` | Query public PEPPOL providers. |
| `encryption certificates` | Read public KSeF encryption certificates. |
| `testdata create-subject` | Create a TEST subject. |
| `testdata delete-subject` | Delete a TEST subject. |
| `testdata create-person` | Create a TEST person. |
| `testdata delete-person` | Delete a TEST person. |
| `testdata enable-attachments` | Enable TEST attachments. |
| `testdata revoke-attachments` | Revoke TEST attachments. |
| `testdata block-context` | Block a TEST context. |
| `testdata unblock-context` | Unblock a TEST context. |
| `testdata grant-permissions` | Grant TEST permissions. |
| `testdata revoke-permissions` | Revoke TEST permissions. |
