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
| `--output`, `-o` | Output mode: `text` or `json`. |
| `--json` | Shortcut for `--output json`. |
| `--verbose`, `-v` | Show tracebacks for CLI errors. |
| `--config` | Local config file path. |
| `--no-config` | Ignore local config profiles. |
| `--profile` | Use a named profile for this invocation. |
| `--nip` | Taxpayer or context NIP. |
| `--token`, `--ksef-token` | KSeF token authentication secret. |
| `--context-type` | Token-auth context type. |
| `--test-cert` | Use an SDK-generated TEST certificate. |
| `--cert`, `--key` | PEM XAdES certificate and private key. |
| `--key-password` | Password for encrypted PEM private key. |
| `--p12`, `--p12-password` | PKCS#12/PFX XAdES archive and password. |
| `--auth-state` | Reuse saved auth state instead of authenticating again. |
| `--auth-poll-interval` | Authentication polling interval. |
| `--auth-timeout` | Seconds to wait for authentication to complete. |

## Command groups

| Group | Purpose |
| --- | --- |
| `auth` | Authenticate and refresh access tokens. |
| `invoices` | Send, confirm, query, download, export, and fetch invoices. |
| `collective` | Generate and query collective invoice identifiers. |
| `fa3` | Build, inspect, and render FA(3) invoices locally, without KSeF access. |
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
| `config` | Inspect and create the local CLI config file. |
| `profile` | Create, inspect, and select local CLI profiles. |

## Subcommands

### `auth`

| Command | Purpose |
| --- | --- |
| `auth login` | Authenticate with the configured method and print tokens. |
| `auth resume` | Reuse saved auth state, refreshing the access token when needed. |
| `auth refresh` | Exchange a refresh token for a new access token. |

| Option | Purpose |
| --- | --- |
| `auth login --save-state FILE` | Write resumable auth state. The file holds bearer tokens in plain text and is created with mode `0600`. |
| `auth resume --state-file FILE` | Auth state to reuse. Defaults to the global `--auth-state`. |
| `auth resume --save-state FILE` | Write the resumed state, including any refreshed access token. |

### `config`

| Command | Purpose |
| --- | --- |
| `config path` | Show the local config path used by this invocation. |
| `config show` | Show local config values. |
| `config init` | Create an empty local config file. |

### `profile`

| Command | Purpose |
| --- | --- |
| `profile create NAME` | Create or replace a profile and select it by default. |
| `profile list` | List configured profiles. |
| `profile current` | Show the active profile. |
| `profile show [NAME]` | Show one profile, or the active profile when omitted. |
| `profile use NAME` | Select the active profile. |

### `invoices`

| Command | Purpose |
| --- | --- |
| `invoices send` | Send invoice XML files or directories through the high-level online/batch workflow. |
| `invoices status` | Check a saved high-level workflow receipt. |
| `invoices upo` | Download UPO XML files from a saved high-level workflow receipt. |
| `invoices metadata` | Query invoice metadata. |
| `invoices download` | Download processed invoice XML by KSeF number. |
| `invoices export` | Schedule an invoice export and save the handle. |
| `invoices export-status` | Fetch invoice export status. |
| `invoices export-fetch` | Fetch and decrypt an export package using a saved handle. |
| `invoices export-download` | Schedule, wait for, and download an export package. It always waits, bounded by `--timeout` and `--poll-interval`. |

Common high-level invoice options:

| Option | Purpose |
| --- | --- |
| `invoices send PATH...` | `PATH` may be XML files or directories. Directories include direct child `*.xml` files. |
| `--recursive` | Include nested `*.xml` files for directory input. |
| `--mode online` / `--mode batch` | Select online mode or one batch submission. Defaults to `online`. |
| `--wait` | Wait for final processing status. |
| `--upo-dir DIR` | Write UPO XML files. Requires `--wait` on `invoices send`. |
| `--receipt FILE` | Write one receipt file. |
| `--receipt-dir DIR` | Write receipt files for multiple online invoices, or one batch receipt. |
| `invoices status --receipt FILE` | Check or wait for the workflow represented by a receipt. |
| `invoices upo --receipt FILE --out FILE` | Download one online invoice UPO. |
| `invoices upo --receipt FILE --upo-dir DIR` | Download online or batch UPO files into a directory. |

`invoices metadata`, `invoices export`, and `invoices export-download` send the
same filter object, so they share these options. The three commands differ only
in the extra options after this table.

| Option | Purpose |
| --- | --- |
| `--date-from` / `--date-to` | Window over the field named by `--date-type`, ISO datetime or date. `--date-from` is required. |
| `--date-type` | `issue_date` (default), `invoicing_date`, or `permanent_storage`. |
| `--role` | `seller` (default), `buyer`, `third_subject`, or `authorized_subject`. |
| `--restrict-hwm` | Restrict results to the permanent-storage high-water mark, so repeated requests return a stable set. Full name: `--restrict-to-permanent-storage-hwm-date`. |
| `--currency` | Currency code. Repeat for multiple. |
| `--invoice-type` | Invoice type, such as `vat`, `kor`, `zal`, `upr`. Repeat for multiple. |
| `--seller-nip` / `--buyer-nip` | Match one seller or buyer NIP. |
| `--buyer-vat-ue` / `--buyer-other-id` | Match a buyer EU VAT ID or another buyer identifier. |
| `--invoice-number` / `--ksef-number` | Match the seller invoice number or the KSeF number. |
| `--amount-type` | `brutto` (default), `netto`, or `vat`. Names the field the amount bounds compare against. |
| `--amount-min` / `--amount-max` | Amount bounds for the chosen amount type. |
| `--form` | Form schema: `FA2`, `FA3`, `FA_RR1`, `PEF3`, `PEF_KOR3`. |
| `--invoicing-mode` | `online` or `offline`. |
| `--attachment yes\|no` | Filter by attachment presence. |
| `--self-invoicing yes\|no` | Filter by the self-invoicing flag. |

Export-only options: `--only-metadata`, `--compression-type zip\|tar_gz`, and
`--handle-file FILE` to save the decryption handle for `export-fetch`.
`export-download` and `export-fetch` add `--out-dir`, `--timeout`, and
`--poll-interval`; only `export-fetch` has `--wait`. `metadata` pages with
`--page-size`, `--page-offset`, `--sort-order`, and `--all`.

### `collective`

A collective identifier groups invoices that are already in KSeF. Every command
here takes KSeF numbers, never local files.

| Command | Purpose |
| --- | --- |
| `collective generate` | Generate a collective identifier for a set of invoices. |
| `collective list` | Query collective identifiers visible in the current context. |
| `collective list-for-invoice` | List collective identifiers that reference one KSeF invoice. |
| `collective list-invoices NUMBERS...` | List the invoices grouped under collective identifiers. |

| Option | Purpose |
| --- | --- |
| `generate --invoice KSEF_NUMBER` | KSeF number of an invoice to group. Repeat for multiple invoices. |
| `generate --invoices-file FILE` | JSON array of `{ksef_number, payment, description}`. Merged with any `--invoice` values. |
| `list --date-from` / `--date-to` | Creation window, ISO datetime or date. `--date-from` is required, `--date-to` defaults to now. |
| `list --number` | Exact identifier number. |
| `list --invoice-count-min` / `--invoice-count-max` | Filter by the number of grouped invoices. |
| `list --current-context yes\|no` | Limit to identifiers created in this context. |
| `list-for-invoice --ksef-number` | Invoice to look up. Required. |
| `list-invoices NUMBERS...` | Identifier numbers; KSeF accepts at most 10 per request. |
| `--page-size` / `--all` | Page size from 10 to 200, or fetch every page. Applies to the three listing commands. |

### `fa3`

These commands use the SDK's public builder and renderer APIs and never call the KSeF API, so they need no credentials.

| Command | Purpose |
| --- | --- |
| `fa3 draft-example` | Print a minimal invoice draft in JSON. |
| `fa3 build` | Build FA(3) XML from a JSON invoice draft. |
| `fa3 inspect` | Read invoice XML and print the invoice it describes. |
| `fa3 render` | Render invoice XML to HTML, and optionally to PDF. |

| Option | Purpose |
| --- | --- |
| `fa3 build --in FILE` / `--in -` | Read the draft from a file, or from stdin with `-`. `fa3 render` and `fa3 inspect` take the invoice XML in `--in`. |
| `--out FILE` | Where to write the output. Without it, XML, HTML, and drafts go to stdout. |
| `--pretty` / `--no-pretty` | Indent the generated XML. Indented by default. |
| `--validate` / `--no-validate` | Check the XML against the FA(3) schema. On by default. |
| `fa3 render --pdf FILE` | Also write PDF. Needs the optional `ksef2[pdf]` dependencies. |
| `--code-lookups` | Let the stylesheet read local files and URLs to print coded values as names. |

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
| `batch prepare` | Build and encrypt batch parts and store them for a later submit. |
| `batch submit` | Prepare, upload, close, and optionally wait for a batch session. |
| `batch upload` | Send stored parts again to a session whose upload failed. |
| `batch status` | Fetch or wait for batch session status. |
| `batch list` | List invoices submitted in a batch session. |
| `batch upo` | Download a collective UPO page. |

Parts are the expensive part of a batch: every one of them is packed and encrypted with
a session key fetched before any session exists. `batch prepare` writes them, together
with that key, into an artifact directory that `batch submit --prepared` uploads as it
stands. Keep the directory as protected as a credential file.

| Option | Purpose |
| --- | --- |
| `batch prepare INVOICE... --out DIR` | Build the package into `DIR`: `prepared.json` plus `parts/part-NNNN.bin`. `--form`, `--offline`, and `--max-part-size` are recorded in the artifact. |
| `batch submit INVOICE...` | Prepare and submit in one call, the way it always worked. |
| `batch submit --prepared DIR` | Upload a stored package instead of building a new one. The build options above do not apply. |
| `batch submit --state-file FILE` | Write session state. When the upload is rejected, `FILE` keeps the state of the interrupted session instead, which is what a retry resumes. |
| `batch upload --prepared DIR --state-file FILE` | Re-send the stored parts to the session in `FILE`, which is how you recover an upload KSeF or its storage rejected. |

### `sessions`

| Command | Purpose |
| --- | --- |
| `sessions auth-list` | List authentication sessions. |
| `sessions auth-close` | Close an authentication session. |
| `sessions auth-terminate-current` | Terminate the current authentication session. |
| `sessions invoice-list` | List historical online or batch invoice sessions. |
| `sessions upo` | Download invoice UPO XML or a session UPO page without saved session state. |

| Option | Purpose |
| --- | --- |
| `upo --session REF` | Online or batch session reference. Required; no state or receipt file is needed. |
| `upo --ksef-number N` / `--invoice-reference R` / `--upo-reference U` | Exactly one identifier is required. `--upo-reference` selects a session UPO page. |
| `upo --out FILE` / `-o FILE` | Write UPO XML to a file. Required, as for `online upo`. Existing files are overwritten. |
| `invoice-list --type online\|batch` | Session type to list. Required. |
| `invoice-list --status` | `in_progress`, `succeeded`, `failed`, or `cancelled`. Repeat for multiple. |
| `invoice-list --reference` | Match one session reference. |
| `invoice-list --created-from` / `--created-to` | Created-at window, ISO datetime or date. |
| `invoice-list --closed-from` / `--closed-to` | Closed-at window, ISO datetime or date. |
| `invoice-list --modified-from` / `--modified-to` | Last-modified window, ISO datetime or date. |
| `invoice-list --page-size` / `--all` | Page size from 10 to 100, or fetch every page. |

### `tokens`

| Command | Purpose |
| --- | --- |
| `tokens generate` | Generate a KSeF token, and wait for it to activate with `--wait`. |
| `tokens list` | List KSeF tokens. |
| `tokens status` | Fetch token status. |
| `tokens revoke` | Revoke a token. |

### `certificates`

| Command | Purpose |
| --- | --- |
| `certificates limits` | Show certificate limits. |
| `certificates enrollment-data` | Fetch certificate enrollment data. |
| `certificates enroll` | Submit a certificate enrollment request, or wait for final status with `--wait`. |
| `certificates enrollment-status` | Check enrollment status. |
| `certificates list` | List certificates. |
| `certificates retrieve` | Retrieve a certificate. |
| `certificates revoke` | Revoke a certificate. |

`certificates enroll` returns the enrollment reference and acceptance timestamp.
With `--wait`, it returns the final enrollment status instead. Enrollment polling
uses the global `--auth-poll-interval`, the profile's `poll_interval`, or 1 second by
default. The wait timeout is the profile's `max_poll_attempts` multiplied by that
interval, or 60 seconds when no attempt limit is configured.

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
| `testdata sandbox` | Create a temporary TEST subject with credentials and cleanup on exit. |
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
| `testdata update-certificate-valid-to` | Shorten a TEST-environment certificate's validity. Needs `--serial-number` and `--valid-to` (ISO datetime). |
