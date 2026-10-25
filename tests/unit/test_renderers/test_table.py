from datetime import datetime
from types import SimpleNamespace

from rich.cells import cell_len

from ksef2_cli.renderers.lists import render_list
from ksef2_cli.renderers.table import Column, amount, clean, render_table, utc_datetime
from ksef2.models import SessionInvoicesResponse, QueryInvoicesMetadataResponse


def test_unicode_alignment_and_right_aligned_amounts():
    rows = [("東京", 1230), ("Żółć", 2.5)]
    text = render_table(
        rows,
        (
            Column("NAME", lambda r: r[0]),
            Column("GROSS", lambda r: amount(r[1], "PLN"), right=True),
        ),
        width=80,
    )
    assert text == "NAME        GROSS\n東京  1230.00 PLN\nŻółć     2.50 PLN"
    assert [cell_len(line) for line in text.splitlines()] == [17, 17, 17]


def test_free_text_shrinks_and_ids_overflow_without_truncation():
    columns = (
        Column("ID", lambda r: r[0]),
        Column("NAME", lambda r: r[1], maximum=30, minimum=4),
    )
    assert render_table(
        [("identifier-1234567890", "東京東京東京")], columns, width=28
    ) == ("ID                     NAME\nidentifier-1234567890  東京…")
    assert "identifier-1234567890" in render_table(
        [("identifier-1234567890", "abcdef")],
        columns,
        width=5,
    )


def test_terminal_width_and_redirected_default(monkeypatch):
    import ksef2_cli.renderers.table as table

    monkeypatch.setattr(table.sys, "stdout", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(
        table, "get_terminal_size", lambda fallback: SimpleNamespace(columns=12)
    )
    columns = (
        Column("ID", lambda r: r[0]),
        Column("NAME", lambda r: r[1], maximum=30, minimum=4),
    )
    rows = [("1234", "abcdefghijklmnop")]
    assert render_table(rows, columns) == "ID    NAME\n1234  abcde…"
    monkeypatch.setattr(table.sys, "stdout", SimpleNamespace(isatty=lambda: False))
    assert render_table(rows, columns) == "ID    NAME\n1234  abcdefghijklmnop"


def test_controls_and_dates():
    assert clean("Żółć\n\r\t\x00\x1b[31mred\x1b[0m\u2028\u202e!") == "Żółć    red  !"
    assert utc_datetime(None) == ""
    assert utc_datetime(datetime(2026, 1, 2, 3, 4, 5, 999)) == "2026-01-02 03:04:05"


def test_empty_envelopes_keep_flags_without_inventing_counts_or_hints():
    assert (
        render_list(
            "batch list", SessionInvoicesResponse(invoices=[], continuation_token=None)
        )
        == "No results."
    )
    assert (
        render_list(
            "invoices metadata",
            QueryInvoicesMetadataResponse(
                invoices=[],
                has_more=False,
                is_truncated=False,
            ),
        )
        == "No results.\nMore results: no\nTruncated: no"
    )
    assert render_list("permissions query", [], kind="entities") == "No results."
