---
title: Test Data
description: Create throwaway TEST subjects, people, permissions, attachment flags, and blocked contexts with KSeF2 CLI, including a one-command sandbox and certificate shortening.
---

The `testdata` group builds the sandbox you test against. It creates TEST subjects
and people, grants and revokes TEST permissions, turns attachments on and off,
blocks and unblocks authentication contexts, and shortens the validity of a TEST
certificate. None of it touches invoice data; it prepares the subjects that send
and receive invoices.

Two rules cover the whole group. It exists only in TEST, so every command here
runs with `--env test` or a profile that selects TEST; against any other
environment the CLI stops with `testdata is only available for Environment.TEST`.
And it is sandbox plumbing, not a production API: never design a workflow that
needs it in DEMO or PRODUCTION.

The commands talk to KSeF's TEST data endpoints through the root client, so they
need no token, no certificate, and no `--nip`. Every NIP involved is an option you
name. `testdata sandbox` is the exception: it authenticates internally, with the
certificate it generates.

## Sandbox a subject in one command

`testdata sandbox` creates a temporary TEST subject, generates a TEST certificate
and key for it, authenticates with them, and issues a token, then keeps everything
alive until you say otherwise:

```bash
uv run ksef2 --env test testdata sandbox
```

```text
nip: 5261040828
subject_type: enforcement_authority
token: ONE_TIME_VALUE
reference_number: 20260302-TOKEN-...
token_permissions: invoice_read, invoice_write
sandbox_dir: /home/you/work/.ksef2-sandbox/5261040828
cert_file: /home/you/work/.ksef2-sandbox/5261040828/cert.pem
key_file: /home/you/work/.ksef2-sandbox/5261040828/private-key.pem
env_file: /home/you/work/.ksef2-sandbox/5261040828/env.sh
source: source /home/you/work/.ksef2-sandbox/5261040828/env.sh
send_with_token: ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" invoices send invoice.xml --wait
send_with_certificate: ksef2 --env test --nip "$KSEF2_NIP" --cert "$KSEF2_CERT" --key "$KSEF2_KEY" invoices send invoice.xml --wait
cleanup: remote_test_data_on_exit
```

The command then waits for Enter, and pressing it removes the remote TEST data.
That hold is the point of the walkthrough: in a second terminal you use the
sandbox, and when you come back you press Enter and the subject is gone. Add
`--no-hold` in a script that creates the sandbox, reads its output, and cleans up
by itself.

In that second terminal, the env file is the whole credential set:

```bash
source .ksef2-sandbox/5261040828/env.sh

uv run ksef2 --env test --json \
  invoices metadata \
  --role seller \
  --date-from 2026-03-01T00:00:00Z \
  --all
```

`env.sh` exports `KSEF2_NIP`, `KSEF2_TOKEN`, `KSEF2_CERT`, and `KSEF2_KEY`, and the
CLI writes that file and the private key with owner-only permissions (`0600`). The
token value appears once, in this output and
in that file, and `--json` output of this command carries it too, so keep the
terminal and the directory out of logs and commits. Cleanup covers the remote TEST
data only, so delete the sandbox directory yourself when you are done.

| Option | Effect |
| --- | --- |
| `--nip` | NIP for the sandbox subject. Defaults to a generated checksum-valid NIP; a NIP you pass has to be valid. |
| `--type` | Subject type: `enforcement_authority` (default), `vat_group`, or `jst`. |
| `--description` | Subject description. Defaults to `ksef2-cli sandbox`. |
| `--out-dir` | Where certificate, key, and env files go. Default `.ksef2-sandbox`; each subject gets its own subdirectory named after its NIP. |
| `--token-permission` | Repeat for the permissions the token gets. Defaults to `invoice_read` and `invoice_write`. |
| `--token-description` | Description for the generated token. |
| `--hold` / `--no-hold` | Wait for Enter before cleaning up. Holding is the default. |

## Create subjects and people

A subject is an organisation; a person is a human being attached to one.

```bash
uv run ksef2 --env test testdata create-subject \
  --nip 5261040828 \
  --type vat_group \
  --description "Sandbox company"

uv run ksef2 --env test testdata create-person \
  --nip 5261040828 \
  --pesel 90010112345 \
  --description "Sandbox person"
```

`--nip`, `--pesel`, and `--description` are required on `create-person`; add
`--bailiff` or `--deceased` to exercise the statuses those names describe. On
`create-subject`, `--type` takes `enforcement_authority`, `vat_group`, or `jst`, and
`--subunit` repeats to add branches in `NIP:description` form:

```bash
uv run ksef2 --env test --json testdata create-subject \
  --nip 5261040828 \
  --type jst \
  --description "Sandbox unit" \
  --subunit 5261040829:"Branch one" \
  --subunit 5261040830:"Branch two"
```

Both kinds have a matching delete, and both take only the NIP:

```bash
uv run ksef2 --env test testdata delete-subject --nip 5261040828
uv run ksef2 --env test testdata delete-person --nip 5261040828
```

Delete what you create when the fixture is shared across runs. The commands create
data in KSeF's TEST database and do not clean up after themselves; only
`testdata sandbox` does.

## Grant and revoke TEST permissions

Grants are made in a context: someone gets a permission that applies to someone
else's data.

```bash
uv run ksef2 --env test testdata grant-permissions \
  --grant-to-type nip \
  --grant-to-value 1111111111 \
  --context-type nip \
  --context-value 5261040828 \
  --permission invoice_read \
  --permission invoice_write
```

`--grant-to-type` and `--context-type` each take `nip`, `pesel`, `fingerprint`, or
`system`, and at least one `--permission` is required. The names are KSeF's own:

```text
invoice_read            invoice_write           pef_invoice_write
introspection           credentials_read        credentials_manage
enforcement_operations  subunit_manage          vat_ue_manage
collective_identifier_manage
```

`--description` labels the grant and defaults to `Granted by ksef2-cli`. The
matching reversal names the same pair without the permissions:

```bash
uv run ksef2 --env test testdata revoke-permissions \
  --revoke-from-type nip \
  --revoke-from-value 1111111111 \
  --context-type nip \
  --context-value 5261040828
```

These are TEST fixtures for checking a grant shape before you ask for it for real.
Production grants go through the `permissions` group, described in
[Permissions](permissions.md).

## Turn attachments on and off

```bash
uv run ksef2 --env test testdata enable-attachments --nip 5261040828
uv run ksef2 --env test testdata revoke-attachments --nip 5261040828
```

Attachments are a flag on the subject rather than an entry in a grant list, which is
why [Permissions](permissions.md#check-attachment-rights) reads them with its own
command and changes them here. A subject with `is_attachment_allowed` false cannot
send invoices with attachments until something enables them. `revoke-attachments`
takes an optional `--expected-end-date` in `YYYY-MM-DD` form for the revocation KSeF
records.

## Block and unblock a context

```bash
uv run ksef2 --env test testdata block-context \
  --context-type nip \
  --context-value 5261040828

uv run ksef2 --env test testdata unblock-context \
  --context-type nip \
  --context-value 5261040828
```

`--context-type` takes `nip`, `internal_id`, `nip_vat_ue`, or `peppol_id`, and both
options are required. This is the switch for testing how your code reacts to a
refused context: block it, run the command that should fail, then unblock it in the
same test. Do not leave a context you authenticate with blocked, because KSeF keeps
refusing it until something unblocks it.

## Shorten a certificate's validity

```bash
uv run ksef2 --env test testdata update-certificate-valid-to \
  --serial-number ABCDEF1234567890 \
  --valid-to 2026-03-01T12:00:00Z
```

```text
serial_number: ABCDEF1234567890
valid_to: 2026-03-01T12:00:00+00:00
updated: yes
```

`--serial-number` is 16 hexadecimal characters, which is what `certificates list`
and `certificates retrieve` report for a certificate you hold; the CLI rejects a
serial KSeF could never accept. `--valid-to` takes an ISO 8601 datetime with a UTC
offset, because the endpoint acts on one instant and a naive timestamp names none; a
date with no time of day, such as `2026-03-01`, is that day at midnight UTC. A
datetime without an offset is rejected before anything is sent. The command exists to
make a certificate run out soon, so you can watch what your renewal path does. Do not
plan on lengthening a validity with it.

## Related pages

- [Authentication](authentication.md)
- [Permissions](permissions.md)
- [Certificates](certificates.md)
- [Limits](limits.md)
- [Command reference](../reference/commands.md)
