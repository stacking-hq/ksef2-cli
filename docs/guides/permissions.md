---
title: Permissions
description: Grant, list, and revoke KSeF permissions for people, entities, authorizations, subunits, and EU entities with KSeF2 CLI.
---

KSeF separates authentication from authorization: a credential that logs in
cleanly still fails a call outside its scope. The `permissions` group changes
that scope. It has one command per grant target, separate listing commands, and
two revocations.

Every grant and revoke is asynchronous. The command returns a KSeF operation
reference as soon as the request is accepted, and the change applies later.
Nothing here says "the permission is active"; only the operation status does.

| Command | Target | Identifier kinds for the target |
| --- | --- | --- |
| `grant-person` | A named person, directly. | `nip`, `pesel`, `fingerprint` |
| `grant-entity` | Another company. | `--subject-value` is its NIP |
| `grant-authorization` | An invoice authorization such as self-invoicing. | `nip`, `peppol_id` |
| `grant-indirect` | A person acting for a specific counterparty. | `nip`, `pesel`, `fingerprint` |
| `grant-subunit` | A person inside one subunit context. | `nip`, `pesel`, `fingerprint` |
| `grant-eu-entity` | An EU entity identified by certificate fingerprint. | `fingerprint` |
| `grant-eu-admin` | Administration of an EU entity. | `fingerprint` |

Pick the command that matches how the access is supposed to be held. A grant
made through the wrong command shows up in a different listing and is revoked
through a different path.

## Grant to a person

```bash
uv run ksef2 --profile prod-xades --json \
  permissions grant-person \
  --subject-type pesel \
  --subject-value 90010112345 \
  --first-name Jan \
  --last-name Kowalski \
  --description "Accounting read access" \
  --permission invoice_read
```

Repeat `--permission` for more scopes. Accepted values are `invoice_read`,
`invoice_write`, `introspection`, `credentials_read`, `credentials_manage`,
`enforcement_operations`, and `subunit_manage`. At least one is required, and the
command fails before the request if you leave them all out.

## Grant to another entity

```bash
uv run ksef2 --profile prod-xades --json \
  permissions grant-entity \
  --subject-value 1234567890 \
  --entity-name "Accounting Sp. z o.o." \
  --description "Bookkeeping for 2026" \
  --permission invoice_read \
  --permission invoice_write
```

`--subject-value` is the other company's NIP. `--permission` takes
`invoice_read`, `invoice_write`, or `collective_identifier_manage`. Add
`--can-delegate` to apply delegation to every scope in the same call, which
matters only on the permission paths where KSeF allows delegation.

## Grant an invoice authorization

Authorizations cover the special invoicing modes rather than read or write
access:

```bash
uv run ksef2 --profile prod-xades --json \
  permissions grant-authorization \
  --subject-type nip \
  --subject-value 1234567890 \
  --permission self_invoicing \
  --entity-name "Partner Sp. z o.o." \
  --description "Self-invoicing agreement"
```

`--permission` takes one value here: `self_invoicing`, `rr_invoicing`,
`tax_representative`, or `pef_invoicing`. Use `--subject-type peppol_id` when the
partner is identified by a PEPPOL id instead of a NIP.

## Grant indirect permissions

Indirect permissions bind a person to a counterparty:

```bash
uv run ksef2 --profile prod-xades --json \
  permissions grant-indirect \
  --subject-type nip \
  --subject-value 9876543210 \
  --first-name Anna \
  --last-name Nowak \
  --description "Broker for selected buyers" \
  --permission invoice_read \
  --target-type nip \
  --target-value 1234567890
```

`--target-type` is `nip`, `all_partners`, or `internal_id`, and `--target-value`
names the counterparty. Leave both out when the grant should not be limited to
one target. `--permission` takes `invoice_read`, `invoice_write`, or
`collective_identifier_manage`.

## Grant subunit permissions

A subunit grant names the context it applies in, which is what separates it from
a plain person grant:

```bash
uv run ksef2 --profile prod-xades --json \
  permissions grant-subunit \
  --subject-type pesel \
  --subject-value 90010112345 \
  --first-name Jan \
  --last-name Kowalski \
  --context-type nip \
  --context-value 1234567890 \
  --subunit-name "Warehouse Wawer" \
  --description "Subunit access"
```

`--context-type` is `nip` or `internal_id`. `--subunit-name` is optional and
labels the subunit.

## Grant to an EU entity

```bash
uv run ksef2 --profile prod-xades --json \
  permissions grant-eu-entity \
  --subject-value "$FINGERPRINT" \
  --description "EU entity read access" \
  --permission invoice_read
```

`--subject-value` is a certificate fingerprint, and `--permission` takes
`invoice_read` or `invoice_write`. Administration rights are a separate call,
because they are held in a VAT UE context:

```bash
uv run ksef2 --profile prod-xades --json \
  permissions grant-eu-admin \
  --subject-value "$FINGERPRINT" \
  --context-value "PL1234567890" \
  --eu-entity-name "Example EU Entity" \
  --description "EU entity administrator"
```

`--context-type` defaults to `nip_vat_ue` and that is the only value it accepts,
so you can leave it out.

## Wait for the operation

Add `--wait` to any grant or revoke. The output becomes the final status instead
of the accepted reference:

```bash
uv run ksef2 --profile prod-xades --json \
  permissions grant-entity \
  --subject-value 1234567890 \
  --entity-name "Accounting Sp. z o.o." \
  --description "Bookkeeping for 2026" \
  --permission invoice_read \
  --wait
```

```json
{
  "status": {
    "code": 200,
    "description": "Completed"
  }
}
```

Code `100` means KSeF is still applying the change and `200` means it is done.
Anything else, such as `400` or `500`, ends the command as a failure and the
message carries the description KSeF returned. `--wait` polls for 60 seconds at
one-second intervals, and no CLI option changes that budget.

Without `--wait`, or after a wait that timed out, check the reference yourself:

```bash
uv run ksef2 --profile prod-xades --json \
  permissions operation-status --reference "$OPERATION_REFERENCE"
```

Until that status reads `200`, do not show the permission as active in your own
system, and do not let a dependent job run on it.

## List what is granted

Roles held by the authenticated entity:

```bash
uv run ksef2 --profile prod-xades permissions entity-roles --all
```

Everything else goes through `permissions query` with a JSON payload. The kind
selects the query shape, `--payload` names the file, and `--page-size`,
`--page-offset`, and `--all` page the result the same way as the other list
commands.

`--page-size` sets the number of items per API request, including with `--all`.
`--all` requires `--page-offset` to be 0, its default, and rejects a nonzero offset.

| Kind | Payload model | Required fields |
| --- | --- | --- |
| `personal` | `PersonalPermissionsQuery` | none |
| `entities` | `EntityPermissionsQuery` | none |
| `persons` | `PersonPermissionsQuery` | `query_type` |
| `authorizations` | `AuthorizationPermissionsQuery` | `query_type` |
| `eu-entities` | `EuEntityPermissionsQuery` | none |
| `subordinate-entities` | `SubordinateEntityRolesQuery` | none |
| `subunits` | `SubunitPermissionsQuery` | none |

Your own active read grants, in a file named `personal.json`:

```json
{
  "permission_types": ["invoice_read"],
  "permission_state": "active"
}
```

```bash
uv run ksef2 --profile prod-xades --json \
  permissions query personal --payload personal.json --all
```

Grants given out in one company's context, in `entities.json`:

```json
{
  "context_type": "nip",
  "context_value": "5261040828"
}
```

```bash
uv run ksef2 --profile prod-xades --json \
  permissions query entities --payload entities.json
```

Authorizations are split by direction, so `query_type` is required. In
`authorizations.json`, `granted` means issued by this subject and `received`
means issued to it:

```json
{
  "query_type": "granted",
  "permission_types": ["self_invoicing"]
}
```

```bash
uv run ksef2 --profile prod-xades \
  permissions query authorizations --payload authorizations.json
```

For the kinds with no required fields, `{}` is a valid payload and returns
everything KSeF will list for the current context. Each kind reports the fields
its own API defines, and these are the ones you act on later:

| Kind | Fields you will actually read |
| --- | --- |
| `personal` | `id`, `permission_type`, `permission_state`, `authorized_value`, `target_value` |
| `entities` | `id`, `context_type`, `context_value`, `permission_type`, `can_delegate` |
| `persons` | `id`, `permission_type`, `permission_state`, `person_first_name`, `person_last_name` |
| `authorizations` | `id`, `authorization_scope`, `authorized_entity_value`, `authorizing_entity_value` |
| `eu-entities` | `id`, `vat_ue_identifier`, `authorized_fingerprint_identifier`, `permission_type` |
| `subordinate-entities` | `subordinate_entity_type`, `subordinate_entity_value`, `role` |
| `subunits` | `id`, `subunit_type`, `subunit_value`, `permission_type`, `subunit_name` |

Every `id` is a 36-character string, so read it out of a listing instead of
writing one yourself. `subordinate-entities` rows carry no `id` at all, which
means they tell you about roles and nothing about revoking them.

Text mode prints one `key: value` block per record and leaves out fields that
carry nothing, so `--json` is what a script should ask for.

## Revoke

Revoke by the `id` you read from a listing, not by the description you wrote when
granting:

```bash
uv run ksef2 --profile prod-xades --json \
  permissions revoke-common --permission-id "$PERMISSION_ID" --wait
```

Authorization grants have their own revocation, and using the wrong one leaves
the grant in place:

```bash
uv run ksef2 --profile prod-xades --json \
  permissions revoke-authorization --permission-id "$AUTHORIZATION_ID" --wait
```

Both return an operation reference without `--wait`, so the same status rule
applies: the revocation counts when the operation reports `200`.

## Check attachment rights

Attachment permissions are a state on the current subject rather than a grant
list, so they have their own read-only command:

```bash
uv run ksef2 --profile prod-xades --json permissions attachment-status
```

```json
{
  "is_attachment_allowed": true,
  "revoked_date": null
}
```

A subject with `is_attachment_allowed` false cannot send invoices with
attachments, and `revoked_date` tells you when that started. Changing the state is
TEST-environment test data work, not part of this group.

## Related pages

- [Tokens](tokens.md)
- [Certificates](certificates.md)
- [Authentication](authentication.md)
- [Command reference](../reference/commands.md)
