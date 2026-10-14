"""Option declarations shared by the invoice filtering commands.

``invoices metadata``, ``invoices export`` and ``invoices export-download`` all send the
same SDK ``InvoicesFilter``, so their options are declared once here. Each command still
lists the options it accepts in its own signature, which keeps ``--help`` accurate per
command while the names, help text and defaults stay in one place.
"""

from typing import Annotated

import typer

from ksef2_cli.commands.invoices.models import (
    InvoiceAmountTypeChoice,
    InvoiceDateTypeChoice,
    InvoiceRoleChoice,
    InvoiceTypeChoice,
    InvoicingModeChoice,
)
from ksef2_cli.config import FORM_SCHEMA_NAMES, FormSchemaChoice

DateFromOption = Annotated[
    str, typer.Option("--date-from", help="Start datetime/date, ISO format.")
]
DateToOption = Annotated[
    str | None, typer.Option("--date-to", help="End datetime/date, ISO format.")
]
RoleOption = Annotated[
    InvoiceRoleChoice,
    typer.Option("--role", help="buyer, seller, third_subject, authorized_subject."),
]
DateTypeOption = Annotated[
    InvoiceDateTypeChoice,
    typer.Option("--date-type", help="issue_date, invoicing_date, permanent_storage."),
]
AmountTypeOption = Annotated[
    InvoiceAmountTypeChoice,
    typer.Option("--amount-type", help="brutto, netto, or vat."),
]
PermanentStorageHwmOption = Annotated[
    bool,
    typer.Option(
        "--restrict-to-permanent-storage-hwm-date",
        "--restrict-hwm",
        help=(
            "Restrict results to the permanent-storage high-water mark, so repeated "
            "requests return a stable set."
        ),
    ),
]
CurrencyOption = Annotated[
    list[str], typer.Option("--currency", help="Currency code. Repeat for multiple.")
]
InvoiceTypeOption = Annotated[
    list[InvoiceTypeChoice],
    typer.Option("--invoice-type", help="Invoice type. Repeat for multiple."),
]
SellerNipOption = Annotated[
    str | None, typer.Option("--seller-nip", help="Match this seller NIP.")
]
BuyerNipOption = Annotated[
    str | None, typer.Option("--buyer-nip", help="Match this buyer NIP.")
]
BuyerVatUeOption = Annotated[
    str | None, typer.Option("--buyer-vat-ue", help="Match this buyer EU VAT ID.")
]
BuyerOtherIdOption = Annotated[
    str | None,
    typer.Option(
        "--buyer-other-id", help="Match this buyer identifier of another kind."
    ),
]
InvoiceNumberOption = Annotated[
    str | None,
    typer.Option("--invoice-number", help="Match this seller invoice number."),
]
KsefNumberOption = Annotated[
    str | None, typer.Option("--ksef-number", help="Match this KSeF number.")
]
AmountMinOption = Annotated[
    float | None,
    typer.Option("--amount-min", help="Minimum amount of the chosen amount type."),
]
AmountMaxOption = Annotated[
    float | None,
    typer.Option("--amount-max", help="Maximum amount of the chosen amount type."),
]
FormOption = Annotated[
    FormSchemaChoice | None,
    typer.Option("--form", help=f"Form schema: {FORM_SCHEMA_NAMES}."),
]
InvoicingModeOption = Annotated[
    InvoicingModeChoice | None,
    typer.Option("--invoicing-mode", help="online or offline."),
]
AttachmentOption = Annotated[
    str | None,
    typer.Option("--attachment", help="Filter by attachment presence: yes or no."),
]
SelfInvoicingOption = Annotated[
    str | None,
    typer.Option("--self-invoicing", help="Filter by self-invoicing flag: yes or no."),
]
