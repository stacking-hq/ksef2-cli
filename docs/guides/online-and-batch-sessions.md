---
title: Online and Batch Sessions
description: Use lower-level online and batch session commands when the high-level invoice workflow is not enough.
---

Most users should start with `invoices send`, `invoices status`, and
`invoices upo`. Use the `online` and `batch` groups when you need direct
control over KSeF session state.

## Open and reuse an online session

Open a session and save resumable state:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  online open \
  --state-file online-state.json
```

Send invoices through the session:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  online send invoice-1.xml invoice-2.xml \
  --state-file online-state.json \
  --keep-open
```

Check session status:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  online status --state-file online-state.json
```

List submitted invoices:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  online list --state-file online-state.json
```

Check one invoice and download its UPO:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  online invoice-status \
  --state-file online-state.json \
  --invoice-reference "$INVOICE_REFERENCE" \
  --wait

uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  online upo \
  --state-file online-state.json \
  --invoice-reference "$INVOICE_REFERENCE" \
  --out invoice-upo.xml
```

Close the session when no more invoices will be sent:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  online close --state-file online-state.json
```

## Submit and inspect a batch session

Submit a batch and save its state:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  batch submit invoice-1.xml invoice-2.xml \
  --wait \
  --state-file batch-state.json
```

Check status later:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  batch status --state-file batch-state.json --wait
```

List submitted invoices:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  batch list --state-file batch-state.json
```

Download a collective UPO page:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  batch upo \
  --state-file batch-state.json \
  --upo-reference "$UPO_REFERENCE" \
  --out batch-upo.xml
```

## Choose high-level or low-level commands

Use `invoices send` for normal invoice sending. It opens and closes online
sessions for you, can switch to batch mode with `--mode batch`, and writes a
receipt that `invoices status` and `invoices upo` understand.

Use `online` or `batch` when you need direct access to session references,
state files, per-session invoice lists, or manual close/retry behavior.
