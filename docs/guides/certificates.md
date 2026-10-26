---
title: Certificates
description: Check KSeF certificate quotas, enroll a certificate from a CSR, query and download issued certificates, and revoke them with KSeF2 CLI.
---

The `certificates` group covers MCU certificate work: enrollment quotas, the
subject data KSeF expects in a certificate request, enrollment, search,
download, and revocation. The CLI sends the request and reads the answer. It
never generates a private key and never asks for one, so key generation and key
storage stay in your own certificate tooling.

Every command in this group needs an authenticated context, and enrollment needs
one that KSeF allows to request certificates.

## Check the quota first

```bash
uv run ksef2 --profile prod-xades --json certificates limits
```

```json
{
  "can_request": true,
  "enrollment_limit": 10,
  "enrollment_remaining": 9,
  "certificate_limit": 10,
  "certificate_remaining": 8
}
```

`enrollment_remaining` counts requests you may still submit, `certificate_remaining`
counts certificates you may still hold, and `can_request` is KSeF's own yes or
no. Enrollment requests that arrive with no quota left are rejected, so read
these numbers before an automated run. In text mode `can_request` prints as
`yes` or `no`.

`limits get subject` reports related caps from the limits branch. Read both
before changing a certificate process.

## Read the subject data for your CSR

```bash
uv run ksef2 --profile prod-xades --json certificates enrollment-data
```

```json
{
  "common_name": "Example subject",
  "iso_country_code": "PL",
  "organization_identifier": "VATPL-5261040828"
}
```

The response also carries `name`, `surname`, `serial_number`,
`unique_identifier`, and `organization_name` when KSeF has them for this
subject. Use these values as the subject of the request you build in the next
step, and do not invent your own spelling of them.

## Build the key and the request

KSeF wants a PKCS#10 request, DER-encoded and then Base64-encoded, in one file.
The CLI reads the file text and puts it in the request body as it stands, so keep
it on a single line.

```bash
openssl ecparam -genkey -name prime256v1 -noout -out billing.key

openssl req -new -key billing.key \
  -subj "/CN=Example subject" \
  -outform DER | base64 | tr -d '\n' > billing.csr
```

`billing.key` is the private key. Protect it, or generate it in your hardware
security module or keystore and only export the request. KSeF does not need it
at any point.

## Enroll

```bash
uv run ksef2 --profile prod-xades --json \
  certificates enroll \
  --name billing-service \
  --csr-file billing.csr
```

```json
{
  "reference_number": "20260625-CERT-...",
  "timestamp": "2026-06-25T10:00:00Z"
}
```

That response means KSeF accepted the request, not that it issued anything. Keep
the `reference_number`. `--type` selects `authentication` (the default) or
`offline`, and `--valid-from` takes an ISO 8601 datetime when the certificate
should start later than now.

Add `--wait` to hold the command until KSeF finishes. The output becomes the
enrollment status instead of the accepted request:

```bash
uv run ksef2 --profile prod-xades --json \
  certificates enroll \
  --name billing-service \
  --csr-file billing.csr \
  --wait
```

```json
{
  "request_date": "2026-06-25T10:00:00Z",
  "status_code": 200,
  "status_description": "Completed",
  "status_details": null,
  "certificate_serial_number": "0123456789ABCDEF"
}
```

`status_code` 100 means KSeF is still working and 200 means the certificate
exists. Any other code fails the command and reports the description and the
status details with it, so a rejected request is visible in the exit status
rather than buried in the output.

Enrollment polling waits 60 seconds by default, checked once per second. A
profile's `max_poll_attempts` and `poll_interval` set both numbers, and
`--auth-poll-interval` overrides only the interval. Unlike `auth login`, this
wait ignores `--auth-timeout`.

## Check enrollment later

```bash
uv run ksef2 --profile prod-xades --json \
  certificates enrollment-status --reference "$ENROLLMENT_REFERENCE"
```

Use this after a command you ran without `--wait`, or after a run that timed out
while KSeF was still deciding. It reads the same status object without submitting
anything again.

## Find certificates

```bash
uv run ksef2 --profile prod-xades certificates list \
  --status active \
  --page-size 50
```

Filters: `--serial-number`, `--name`, `--type` (`authentication` or `offline`),
`--status` (`active`, `blocked`, `revoked`, `expired`), and `--expires-after`
with an ISO 8601 datetime, which is how you ask for what is about to run out.
`--page-size` takes 10 to 100, `--page-offset` skips records, and `--all` walks
every page.

`--page-size` sets the number of items per API request, including with `--all`.
`--all` requires `--page-offset` to be 0, its default, and rejects a nonzero offset.

Text output prints one `key: value` block per certificate, with `serial_number`,
`name`, `common_name`, `type`, `status`, `subject_identifier`, `valid_from`,
`valid_to`, and `request_date`. `last_use_date` appears only for a certificate
KSeF has seen in use, and `subject_identifier` prints as one compact JSON object.
Use `--json` when you want the serial numbers in a pipe.

Serial numbers are exactly 16 hexadecimal characters, upper case. The CLI checks
the shape before sending anything, so a lower-case or truncated serial fails with
a validation message instead of an API error.

## Download a certificate

Serial numbers are positional arguments, and one call takes several of them:

```bash
uv run ksef2 --profile prod-xades --json \
  certificates retrieve 0123456789ABCDEF ABCDEF1234567890
```

Add `--out-dir` to write each certificate to a file as well. The CLI creates the
directory and saves one `<serial_number>.b64` file per certificate, holding the
Base64 of the DER-encoded X.509 certificate as KSeF returned it:

```bash
uv run ksef2 --profile prod-xades \
  certificates retrieve 0123456789ABCDEF \
  --out-dir issued
```

That file is not PEM, so decode it before you hand the certificate to a tool
that expects one, and pair it with the private key you generated yourself:

```bash
base64 --decode < issued/0123456789ABCDEF.b64 \
  | openssl x509 -inform DER -out issued/0123456789ABCDEF.pem

openssl pkcs12 -export -out issued/billing-service.p12 \
  -inkey billing.key -in issued/0123456789ABCDEF.pem
```

`openssl pkcs12 -export` asks for an export password, and `-passout` takes it on
the command line when you do not want a prompt. The resulting archive is what the
`--p12` root option and the profile's PKCS#12 settings take. See
[Authentication](authentication.md) for the password environment variables that
go with it.

When KSeF answers with a body the installed SDK cannot read, the command exits 1
with `KSeF response could not be parsed`, one line per rejected field, and hints to
upgrade and to re-run with `--verbose`, which then carries the SDK traceback. With
SDK 1.0.0, valid issued certificates could trigger this error because the SDK
decoded binary DER as UTF-8. The CLI requires SDK 1.1 or newer, which fixes
[ksef2#323](https://github.com/stacking-hq/ksef2/issues/323) and preserves the Base64
certificate text.

## Revoke

```bash
uv run ksef2 --profile prod-xades --json \
  certificates revoke \
  --serial-number 0123456789ABCDEF \
  --reason key_compromise
```

```json
{
  "serial_number": "0123456789ABCDEF",
  "reason": "key_compromise",
  "revoked": true
}
```

`--reason` is optional and takes `unspecified`, `superseded`, or
`key_compromise`. Pass `key_compromise` when the private key may have leaked;
revoking does not clean up the key, so stop using it as well.

## Related pages

- [Authentication](authentication.md)
- [Limits](limits.md)
- [Permissions](permissions.md)
- [Command reference](../reference/commands.md)
