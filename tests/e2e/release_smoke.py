"""Opt-in installed-CLI smoke: writes three uniquely named invoices to KSeF TEST."""

import argparse
import json
import os
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--allow-test-writes", action="store_true", required=True)
    args = parser.parse_args()
    work = args.work_dir.resolve()
    work.mkdir(mode=0o700, parents=True, exist_ok=False)
    env = {key: value for key, value in os.environ.items() if not key.startswith("KSEF2_")}
    base = [str(args.cli.resolve()), "--no-config", "--env", "test", "--json"]
    state = work / "auth.json"
    results = {}

    def run(label: str, command: list[str], *, authenticated: bool = True):
        prefix = base + (["--auth-state", str(state)] if authenticated else [])
        result = subprocess.run(prefix + command, capture_output=True, text=True,
                                env=env, timeout=240)
        (work / f"{label}.stdout").write_text(result.stdout)
        (work / f"{label}.stderr").write_text(result.stderr)
        if result.returncode:
            raise RuntimeError(f"{label} exited {result.returncode}; see {work}. Do not resend.")
        value = json.loads(result.stdout)
        results[label] = value
        print(f"PASS {label}", flush=True)
        return value

    now = datetime.now(UTC)
    identifier = f"CLI-SMOKE/{now:%Y%m%d}/{uuid.uuid4().hex[:10]}"
    draft = run("draft", ["fa3", "draft-example"], authenticated=False)
    if isinstance(draft, str):
        draft = json.loads(draft)
    draft["seller"]["tax_id"] = "5261040828"
    draft["buyer"]["tax_id"] = "6880313213"
    draft["body"]["issue_date"] = now.date().isoformat()
    invoices = []
    for index in range(1, 4):
        draft["body"]["invoice_number"] = f"{identifier}/{index}"
        source = work / f"invoice-{index}.json"
        source.write_text(json.dumps(draft))
        xml = work / f"invoice-{index}.xml"
        run(f"build-{index}", ["fa3", "build", "-i", str(source), "-o", str(xml)],
            authenticated=False)
        invoices.append(xml)
    run("pdf", ["fa3", "render", "-i", str(invoices[0]), "--code-lookups",
                "--pdf", str(work / "local.pdf")],
        authenticated=False)
    assert (work / "local.pdf").read_bytes().startswith(b"%PDF-")
    try:
        run("login", ["--nip", "5261040828", "--test-cert", "auth", "login",
                      "--save-state", str(state)], authenticated=False)
        online_receipt = work / "online-receipt.json"
        sent = run("online-send", ["invoices", "send", str(invoices[0]), "--wait",
                    "--receipt", str(online_receipt), "--upo-dir", str(work / "online-upo")])
        assert sent["failed"] == 0 and sent["items"][0]["ksef_number"]
        run("online-status", ["invoices", "status", "--receipt", str(online_receipt)])
        run("online-upo", ["invoices", "upo", "--receipt", str(online_receipt),
                            "--out", str(work / "online-upo-again.xml")])
        downloaded = work / "downloaded.xml"
        run("download", ["invoices", "download", "--ksef-number", sent["items"][0]["ksef_number"],
                         "--out", str(downloaded)])
        assert downloaded.read_bytes() == invoices[0].read_bytes()
        receipt = work / "batch-receipt.json"
        batch = run("batch-send", ["invoices", "send", *map(str, invoices[1:]), "--mode", "batch",
                    "--wait", "--receipt", str(receipt), "--upo-dir", str(work / "batch-upo")])
        assert batch["failed"] == 0 and len(batch["items"]) == 2
        assert all(item["ksef_number"] for item in batch["items"])
        reference = batch["batch"]["session_reference"]
        run("batch-status", ["invoices", "status", "--receipt", str(receipt), "--wait"])
        run("batch-upo", ["invoices", "upo", "--receipt", str(receipt),
                           "--upo-dir", str(work / "batch-upo-again"), "--wait"])
        run("batch-reference-status", ["batch", "status", "--reference", reference])
        run("batch-reference-list", ["batch", "list", "--reference", reference])
        run("export-pdf", ["invoices", "export-pdf", "--date-from", f"{now.date()}T00:00:00Z",
                           "--invoice-number", f"{identifier}/1", "--out-dir", str(work / "export-pdf")])
        assert list((work / "export-pdf").rglob("*.pdf"))
    finally:
        (work / "results.json").write_text(json.dumps(results, indent=2))
        if state.exists():
            run("logout", ["auth", "logout"])
    print(f"Artifacts: {work}")


if __name__ == "__main__":
    main()
