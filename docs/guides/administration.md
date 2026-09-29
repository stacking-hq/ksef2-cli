---
title: Administration
description: Manage tokens, sessions, certificates, permissions, and TEST limits with KSeF2 CLI.
---

Administrative commands are authenticated KSeF operations. Put root options such
as `--env`, `--nip`, `--token`, `--test-cert`, and `--profile` before the command
group:

```bash
ksef2 [ROOT OPTIONS] tokens list
```

Many commands in this guide mutate remote KSeF state. Use `--json` when you need
to capture references for follow-up commands.

## Manage authorization tokens

Generate a token with one or more permissions:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  tokens generate \
  --description "readonly automation" \
  --permission invoice_read
```

The generated token value is a secret. Store it in a secret manager or an
environment variable, not in the local profile file.

List, inspect, and revoke tokens:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  tokens list --status active --all

uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  tokens status --reference "$TOKEN_REFERENCE"

uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  tokens revoke --reference "$TOKEN_REFERENCE"
```

## Inspect and close sessions

Authentication sessions and invoice sessions are separate KSeF resources.

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  sessions auth-list --all

uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  sessions auth-close --reference "$AUTH_SESSION_REFERENCE"

uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  sessions auth-terminate-current
```

List historical online or batch invoice sessions:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  sessions invoice-list --type online --status succeeded --all

uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  sessions invoice-list --type batch --reference "$SESSION_REFERENCE"
```

## Manage MCU certificates

Read certificate limits and enrollment data:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  certificates limits

uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  certificates enrollment-data
```

Submit a base64-encoded CSR, then check the enrollment status:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  certificates enroll \
  --name "automation certificate" \
  --csr-file certificate.csr.b64 \
  --type authentication

uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  certificates enrollment-status --reference "$ENROLLMENT_REFERENCE"
```

List, retrieve, and revoke certificates:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  certificates list --status active --all

uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  certificates retrieve "$CERTIFICATE_SERIAL" --out-dir certificates

uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  certificates revoke \
  --serial-number "$CERTIFICATE_SERIAL" \
  --reason superseded
```

## Grant, query, and revoke permissions

Start by checking the current entity roles and attachment permission status:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  permissions entity-roles

uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  permissions attachment-status
```

Grant invoice permissions to another entity:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  permissions grant-entity \
  --subject-value "$TARGET_NIP" \
  --entity-name "Target company" \
  --description "Invoice read access" \
  --permission invoice_read
```

Grant permissions to a person:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  permissions grant-person \
  --subject-type pesel \
  --subject-value "$TARGET_PESEL" \
  --first-name "Jan" \
  --last-name "Kowalski" \
  --description "Invoice write access" \
  --permission invoice_write
```

Check an asynchronous permission operation:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  permissions operation-status --reference "$PERMISSION_OPERATION_REFERENCE"
```

Permission queries use SDK model-shaped JSON payloads:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  permissions query entities \
  --payload entity-permissions-query.json
```

Revoke by permission id:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  permissions revoke-common --permission-id "$PERMISSION_ID"

uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  permissions revoke-authorization --permission-id "$PERMISSION_ID"
```

## Read and override limits

Read effective limits:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  limits get api

uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  limits get context

uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  limits get subject
```

Limit overrides are TEST-environment operations:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  limits set api --payload api-limits.json

uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  limits reset api

uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  limits production-rate-limits
```
