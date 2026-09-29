---
title: Public and TEST Data
description: Query public KSeF data and manage TEST-environment subjects, people, contexts, and permissions.
---

Public data commands do not need authentication. TEST data commands mutate the
KSeF TEST environment and should be run with `--env test`.

## Query public PEPPOL providers

List PEPPOL providers:

```bash
uv run ksef2 --env test peppol providers
```

Use pagination or fetch every page:

```bash
uv run ksef2 peppol providers --page-size 100 --page-offset 0
uv run ksef2 --json peppol providers --all
```

## Read public encryption certificates

KSeF publishes public certificates used by invoice workflows. Read all current
certificates or filter by usage:

```bash
uv run ksef2 encryption certificates

uv run ksef2 --json encryption certificates \
  --usage ksef_token_encryption \
  --usage symmetric_key_encryption
```

## Create a temporary TEST sandbox

`testdata sandbox` creates a TEST subject, generates a TEST certificate and key,
generates an authorization token, writes a shell env file, and cleans up the
remote TEST subject when it exits.

```bash
uv run ksef2 --env test testdata sandbox \
  --nip "$TEST_SUBJECT_NIP" \
  --out-dir .ksef2-sandbox
```

In another shell, source the generated env file shown by the command:

```bash
source ".ksef2-sandbox/$TEST_SUBJECT_NIP/env.sh"
uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices send invoice.xml --wait
```

The remote TEST subject is cleaned up when `testdata sandbox` exits. Use
`--no-hold` only for noninteractive setup checks or local artifact generation
where immediate remote cleanup is expected.

## Create and delete TEST subjects

Create a TEST subject:

```bash
uv run ksef2 --env test testdata create-subject \
  --nip "$TEST_SUBJECT_NIP" \
  --type enforcement_authority \
  --description "CLI test subject"
```

Create a subject with subunits:

```bash
uv run ksef2 --env test testdata create-subject \
  --nip "$TEST_SUBJECT_NIP" \
  --type jst \
  --description "CLI test JST" \
  --subunit "$SUBUNIT_NIP:Subunit description"
```

Delete the TEST subject when the scenario is over:

```bash
uv run ksef2 --env test testdata delete-subject --nip "$TEST_SUBJECT_NIP"
```

## Create and delete TEST people

```bash
uv run ksef2 --env test testdata create-person \
  --nip "$TEST_PERSON_NIP" \
  --pesel "$TEST_PESEL" \
  --description "CLI test person"

uv run ksef2 --env test testdata delete-person --nip "$TEST_PERSON_NIP"
```

Add `--bailiff` or `--deceased` when that TEST person state is required.

## Attachments and context access

Enable or revoke attachments for a TEST subject:

```bash
uv run ksef2 --env test testdata enable-attachments \
  --nip "$TEST_SUBJECT_NIP"

uv run ksef2 --env test testdata revoke-attachments \
  --nip "$TEST_SUBJECT_NIP" \
  --expected-end-date 2026-12-31
```

Block and unblock a TEST authentication context:

```bash
uv run ksef2 --env test testdata block-context \
  --context-type nip \
  --context-value "$TEST_SUBJECT_NIP"

uv run ksef2 --env test testdata unblock-context \
  --context-type nip \
  --context-value "$TEST_SUBJECT_NIP"
```

## Grant and revoke TEST permissions

Grant permissions in one TEST context:

```bash
uv run ksef2 --env test testdata grant-permissions \
  --grant-to-type nip \
  --grant-to-value "$TARGET_NIP" \
  --context-type nip \
  --context-value "$TEST_SUBJECT_NIP" \
  --permission invoice_read \
  --permission invoice_write
```

Revoke permissions for the same target/context pair:

```bash
uv run ksef2 --env test testdata revoke-permissions \
  --revoke-from-type nip \
  --revoke-from-value "$TARGET_NIP" \
  --context-type nip \
  --context-value "$TEST_SUBJECT_NIP"
```
