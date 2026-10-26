from datetime import UTC, datetime
from typing import Any

from conftest import FakePager, FakeService, cli_args, fake_runtime, payload
from ksef2.models import (
    CollectiveIdentifierInvoiceDetails,
    GenerateCollectiveIdentifierResponse,
    CollectiveIdentifierInvoicePayment,
    CollectiveIdentifierReference,
    CollectiveIdentifierSummary,
)

from ksef2_cli.app import app

SUMMARY_JSON = {
    "collective_identifier_number": "CID-1",
    "date_created": "2026-01-02T03:04:00Z",
    "invoice_count": 2,
    "created_in_current_context": True,
}


def _runtime(**returns: Any) -> tuple[FakeService, Any]:
    service = FakeService(**returns)
    auth = type("Auth", (), {"collective_identifiers": service})()
    return service, fake_runtime(auth=auth)


def test_collective_generate_accepts_json_file_and_repeated_flags(
    runner, tmp_path
) -> None:
    service, runtime = _runtime(
        generate=GenerateCollectiveIdentifierResponse(
            collective_identifier_number="CID-1"
        )
    )
    invoices_file = tmp_path / "invoices.json"
    invoices_file.write_text(
        '[{"ksef_number": "KSEF-1", "payment": {"amount": 10.5, "currency": "PLN"},'
        ' "description": "first"}]',
        encoding="utf-8",
    )

    assert payload(
        runner.invoke(
            app,
            cli_args(
                "collective",
                "generate",
                "--invoices-file",
                str(invoices_file),
                "--invoice",
                "KSEF-2",
            ),
            obj=runtime,
        )
    ) == {"collective_identifier_number": "CID-1"}

    invoices = service.called("generate")["invoices"]
    assert [item.ksef_number for item in invoices] == ["KSEF-1", "KSEF-2"]
    assert invoices[0].payment == CollectiveIdentifierInvoicePayment(
        amount=10.5, currency="PLN"
    )
    assert invoices[0].description == "first"
    assert invoices[1].payment is None


def test_collective_generate_requires_invoices(runner) -> None:
    _service, runtime = _runtime(
        generate=GenerateCollectiveIdentifierResponse(
            collective_identifier_number="CID-1"
        )
    )

    result = runner.invoke(app, cli_args("collective", "generate"), obj=runtime)

    assert result.exit_code == 2
    assert "at least one --invoice" in result.output


def test_collective_list_builds_filters_and_pages(runner) -> None:
    summary = CollectiveIdentifierSummary(
        collective_identifier_number="CID-1",
        date_created=datetime(2026, 1, 2, 3, 4, tzinfo=UTC),
        invoice_count=2,
        created_in_current_context=True,
    )
    service, runtime = _runtime(list=FakePager([summary], [summary]))

    assert payload(
        runner.invoke(
            app,
            cli_args(
                "collective",
                "list",
                "--date-from",
                "2026-01-01T00:00:00Z",
                "--date-to",
                "2026-02-01T00:00:00Z",
                "--number",
                "CID-1",
                "--invoice-count-min",
                "2",
                "--invoice-count-max",
                "5",
                "--current-context",
                "yes",
                "--page-size",
                "20",
            ),
            obj=runtime,
        )
    ) == [SUMMARY_JSON]

    list_call = next(call for call in service.calls if call[0] == "list")
    filters = list_call[1][0]
    assert filters.date_created_from == datetime(2026, 1, 1, tzinfo=UTC)
    assert filters.date_created_to == datetime(2026, 2, 1, tzinfo=UTC)
    assert filters.collective_identifier_number == "CID-1"
    assert filters.invoice_count_from == 2
    assert filters.invoice_count_to == 5
    assert filters.created_in_current_context is True
    assert list_call[2]["params"].page_size == 20

    assert payload(
        runner.invoke(
            app,
            cli_args(
                "collective", "list", "--date-from", "2026-01-01T00:00:00Z", "--all"
            ),
            obj=runtime,
        )
    ) == [SUMMARY_JSON, SUMMARY_JSON]


def test_collective_list_defaults_creation_end_to_now(runner) -> None:
    service, runtime = _runtime(list=FakePager([]))

    assert (
        payload(
            runner.invoke(
                app,
                cli_args("collective", "list", "--date-from", "2026-01-01T00:00:00Z"),
                obj=runtime,
            )
        )
        == []
    )

    filters = next(call for call in service.calls if call[0] == "list")[1][0]
    assert filters.date_created_from == datetime(2026, 1, 1, tzinfo=UTC)
    assert filters.date_created_to <= datetime.now(UTC)
    assert filters.date_created_to > filters.date_created_from


def test_collective_list_reads_a_bare_date_as_midnight_utc(runner) -> None:
    """KSeF needs one instant, so a date-only filter must reach it timezone-aware."""

    service, runtime = _runtime(list=FakePager([]))

    for date_from in ("2026-10-20", "20.10.2026", "20-10-2026"):
        assert (
            payload(
                runner.invoke(
                    app,
                    cli_args("collective", "list", "--date-from", date_from),
                    obj=runtime,
                )
            )
            == []
        )

    filters = [call[1][0] for call in service.calls if call[0] == "list"]
    assert len(filters) == 3
    for item in filters:
        assert item.date_created_from == datetime(2026, 10, 20, tzinfo=UTC)
        assert item.date_created_from.tzinfo is UTC
        assert item.date_created_to.tzinfo is UTC


def test_collective_list_rejects_a_naive_datetime(runner) -> None:
    _service, runtime = _runtime(list=FakePager([]))

    result = runner.invoke(
        app,
        cli_args("collective", "list", "--date-from", "2026-10-20T08:00:00"),
        obj=runtime,
    )

    assert result.exit_code == 2
    assert "--date-from must include a UTC offset" in result.output
    assert "midnight UTC" in result.output


def test_collective_list_rejects_invalid_dates(runner) -> None:
    _service, runtime = _runtime(list=FakePager([]))

    result = runner.invoke(
        app,
        cli_args(
            "collective", "list", "--date-from", "2026-01-01", "--date-to", "not-a-date"
        ),
        obj=runtime,
    )

    assert result.exit_code == 2
    assert "--date-to must be a date like" in result.output


def test_collective_list_for_invoice(runner) -> None:
    reference = CollectiveIdentifierReference(
        collective_identifier_number="CID-1",
        date_created=datetime(2026, 1, 2, 3, 4, tzinfo=UTC),
        created_in_current_context=False,
    )
    service, runtime = _runtime(list_for_invoice=FakePager([reference]))

    assert payload(
        runner.invoke(
            app,
            cli_args("collective", "list-for-invoice", "--ksef-number", "KSEF-1"),
            obj=runtime,
        )
    ) == [
        {
            "collective_identifier_number": "CID-1",
            "date_created": "2026-01-02T03:04:00Z",
            "created_in_current_context": False,
        }
    ]
    assert service.calls[0][0] == "list_for_invoice"
    assert service.calls[0][1] == ("KSEF-1",)
    assert service.calls[0][2]["params"].page_size == 10


def test_collective_list_invoices(runner) -> None:
    details = CollectiveIdentifierInvoiceDetails(
        ksef_number="KSEF-1",
        payment=CollectiveIdentifierInvoicePayment(amount=10.5, currency="PLN"),
        description="first",
        details_hidden=False,
    )
    service, runtime = _runtime(list_invoices=FakePager([details]))

    assert payload(
        runner.invoke(
            app, cli_args("collective", "list-invoices", "CID-1"), obj=runtime
        )
    ) == [
        {
            "ksef_number": "KSEF-1",
            "payment": {"amount": 10.5, "currency": "PLN"},
            "description": "first",
            "details_hidden": False,
        }
    ]
    assert service.calls[0][1] == (["CID-1"],)


def test_collective_list_invoices_caps_identifier_numbers(runner) -> None:
    _service, runtime = _runtime(list_invoices=FakePager([]))

    result = runner.invoke(
        app,
        cli_args(
            "collective", "list-invoices", *[f"CID-{index}" for index in range(11)]
        ),
        obj=runtime,
    )

    assert result.exit_code == 2
    assert "at most 10 collective" in result.output


def test_collective_list_invoices_renders_text_rows(runner) -> None:
    details = CollectiveIdentifierInvoiceDetails(
        ksef_number="KSEF-1",
        payment=None,
        description=None,
        details_hidden=False,
    )
    _service, runtime = _runtime(list_invoices=FakePager([details]))

    result = runner.invoke(
        app, ["--no-config", "collective", "list-invoices", "CID-1"], obj=runtime
    )

    assert result.exit_code == 0
    assert result.output == (
        "KSEF NUMBER  PAYMENT  DESCRIPTION  HIDDEN\n"
        "KSEF-1                             no\n"
    )


def test_collective_commands_render_text_rows(runner) -> None:
    summary = CollectiveIdentifierSummary(
        collective_identifier_number="CID-1",
        date_created=datetime(2026, 1, 2, 3, 4, tzinfo=UTC),
        invoice_count=2,
        created_in_current_context=True,
    )
    reference = CollectiveIdentifierReference(
        collective_identifier_number="CID-1",
        date_created=datetime(2026, 1, 2, 3, 4, tzinfo=UTC),
        created_in_current_context=False,
    )
    service = FakeService(
        generate=GenerateCollectiveIdentifierResponse(
            collective_identifier_number="CID-1"
        ),
        list=FakePager([summary]),
        list_for_invoice=FakePager([reference]),
    )
    runtime = fake_runtime(auth=type("Auth", (), {"collective_identifiers": service})())

    generated = runner.invoke(
        app,
        ["--no-config", "collective", "generate", "--invoice", "KSEF-1"],
        obj=runtime,
    )
    listed = runner.invoke(
        app,
        ["--no-config", "collective", "list", "--date-from", "2026-01-01T00:00:00Z"],
        obj=runtime,
    )
    references = runner.invoke(
        app,
        ["--no-config", "collective", "list-for-invoice", "--ksef-number", "KSEF-1"],
        obj=runtime,
    )

    assert generated.output.strip() == "collective_identifier_number: CID-1"
    assert listed.output.startswith("IDENTIFIER  CREATED (UTC)")
    assert "CID-1       2026-01-02 03:04:00" in listed.output
    assert listed.output.splitlines()[1].split()[-2:] == ["2", "yes"]
    assert references.output.splitlines()[1].endswith("no")
