---
title: Sesje i UPO
description: Sprawdź, co stało się z wysłanymi fakturami, pobierz UPO, które je poświadcza, i odnajdź sesje oraz sesje uwierzytelniania w KSeF2 CLI.
---

Wysyłka to tylko połowa przepływu. Potem potrzebujesz dwóch odpowiedzi: co KSeF zrobił z fakturami oraz dokumentu UPO (Urzędowe Poświadczenie Odbioru), który poświadcza każdą przyjętą fakturę. Grupy `sessions` używasz, gdy proces wysyłki już nie działa. Czyta ona UPO dowolnej dawnej sesji, wypisuje sesje interaktywne i wsadowe, które KSeF jeszcze pamięta, i pokazuje sesje uwierzytelniania otwarte przez twoje dane uwierzytelniające.

Odpowiedzi ze statusem można logować. Pliki stanu sesji, pliki `--receipt` i katalogi przygotowanej paczki zawierają klucze sesji **otwartym tekstem** (`0600` na każdym pliku, który zapisuje CLI; to uprawnienie, a zawartość zostaje zapisana otwartym tekstem). Trzymaj je jak dane uwierzytelniające i nigdy nie wklejaj ich do raportu. Numery referencyjne z listy poniżej nadają się do przekazania dalej. Zobacz [Przepływy faktur](invoices.md#komendy-sesji-niższego-poziomu).

## Która komenda UPO pasuje

Wybierz według tego, co zachowałeś przy wysyłce faktury:

| Co masz | Komenda |
| --- | --- |
| Plik `--receipt` z `invoices send` | `invoices upo --receipt FILE --out FILE` dla jednej faktury z sesji interaktywnej, `--upo-dir DIR` dla sesji wsadowej |
| Plik stanu sesji interaktywnej | `online upo --state-file FILE --out FILE` |
| Sesję wsadową i jeden z numerów referencyjnych strony UPO | `batch upo (--reference R \| --state-file FILE) --upo-reference R --out FILE` |
| Same numery referencyjne: sesji oraz faktury, numeru KSeF albo UPO | `sessions upo --session R --out FILE` |

Pierwsze trzy potrzebują czegoś, co wytworzył proces wysyłki. `sessions upo` potrzebuje samych numerów referencyjnych, więc działa po restarcie, na innej maszynie albo z zadania cron, które zna tylko numery zapisane w twojej bazie.

### UPO z samych numerów referencyjnych

```bash
uv run ksef2 --profile prod-token \
  sessions upo --session "$SESSION_REFERENCE" \
  --ksef-number "$KSEF_NUMBER" \
  --out invoice-upo.xml
```

`--session` i `--out` są wymagane. Dokument wybiera dokładnie jedno z poniższych:

- `--ksef-number` czyta UPO faktury dla jednej przyjętej faktury, gdy KSeF nadał już numer.
- `--invoice-reference` czyta ten sam dokument, wybrany numerem referencyjnym, który sesja zwróciła przy wysłaniu faktury. Użyj go, dopóki numer KSeF jest ci jeszcze nieznany.
- `--upo-reference` czyta jedną stronę UPO sesji, czyli zbiorcze poświadczenie całej sesji. Status sesji wymienia te numery pod `upo.pages[].reference_number`.

Komenda działa tak samo dla sesji interaktywnych i wsadowych i nadal się uwierzytelnia, bo prosi KSeF o dokument. Nigdy nie czeka. Niedokończone przetwarzanie oznacza kod wyjścia `1` pod nagłówkiem `KSeF has not finished processing yet`, ze wskazówką, żeby spróbować później.

### Sprawdź status, zanim ponowisz

Ponowne pytanie ma sens tylko wtedy, gdy KSeF nadal pracuje. Faktura odrzucona przez KSeF nigdy nie dostanie UPO, więc raz odczytaj status i pozwól mu rozstrzygnąć sprawę:

```bash
uv run ksef2 --profile prod-token invoices status --receipt invoice-receipt.json --wait
uv run ksef2 --profile prod-token batch status --state-file batch-state.json --wait
uv run ksef2 --profile prod-token online invoice-status \
  --state-file online-state.json --invoice-reference "$INVOICE_REFERENCE" --wait
```

Odrzucona faktura zgłasza kod statusu 400 albo wyższy. Przyjęta ma `ksef_number`. Wyczerpany `--timeout` też nie jest odrzuceniem. Oznacza tylko tyle, że KSeF nie skończył w twoim terminie, więc numery referencyjne zostają ważne i pytasz później. `batch status` to jedyna komenda tutaj, która potrzebuje pliku stanu sesji. Numer referencyjny jej nie wystarcza. Zobacz [Sesje wsadowe](batch-sessions.md#odczytaj-status-i-wyniki-poszczególnych-faktur).

## Znajdź sesje po restarcie

`sessions invoice-list` czyta historię dawnych sesji faktur. Tak odzyskujesz numer referencyjny sesji, gdy proces wysyłki dawno się skończył:

```bash
uv run ksef2 --profile prod-token \
  sessions invoice-list \
  --type online \
  --status in_progress \
  --created-from 2026-03-01T00:00:00Z \
  --all
```

- `--type online` albo `--type batch` jest wymagane. Obie historie są osobne.
- `--status` filtruje po `in_progress`, `succeeded`, `failed` albo `cancelled` i powtarza się dla kilku wartości naraz.
- `--reference` szuka jednej, konkretnej sesji.
- `--created-from`, `--created-to`, `--closed-from`, `--closed-to`, `--modified-from` i `--modified-to` przyjmują datę albo datę z czasem w ISO 8601. Sama data staje się północą bez przesunięcia UTC, więc gdy okno ma znaczenie, użyj jawnej postaci `2026-03-01T00:00:00Z`.
- `--page-size` przyjmuje wartości od 10 do 100 i domyślnie wynosi 10, a `--all` przechodzi wszystkie strony w jednej komendzie.

Wynik tekstowy wypisuje jeden blok na sesję:

```text
reference_number: 20260302-BATCH-...
status: {"code":200,"description":"Processed","details":null}
date_created: 2026-03-02T09:00:00Z
date_updated: 2026-03-02T09:05:00Z
total_invoice_count: 2
successful_invoice_count: 2
failed_invoice_count: 0
```

`reference_number` stąd przekazujesz do `sessions upo`. Sesja, która nadal jest `in_progress`, nie ma jeszcze stron UPO. Sesja, która skończyła się z błędami, ma mniej przyjętych faktur, niż wysłało uruchomienie `invoices send`. Porównaj `total_invoice_count` z `failed_invoice_count`, zanim uznasz, że paczka przeszła.

## Zamknij sesje uwierzytelniania

Uwierzytelnienie otwiera po stronie KSeF sesję uwierzytelniania. Stanowisko albo zadanie, które loguje się często, może uzbierać ich kilka.

```bash
uv run ksef2 --profile prod-token sessions auth-list --all
```

Jeden blok na aktywną sesję, z `reference_number`, `start_date`, metodą uwierzytelniania, `status_description` oraz `is_current` dla sesji, której te dane uwierzytelniające używają właśnie teraz. `--page-size` przyjmuje wartości od 10 do 100. ksef2 1.0 stronicuje tę listę wewnętrznie, więc `--continuation-token` jest odrzucany, a całość zobaczysz przez `--all`.

Aby zakończyć jedną:

```bash
uv run ksef2 --profile prod-token \
  sessions auth-close --reference "$AUTH_SESSION_REFERENCE"

uv run ksef2 --profile prod-token sessions auth-terminate-current
```

`auth-close` kończy sesję, którą wskażesz, także taką, którą zostawił laptop, który odszedł. Zamknięcie sesji, w której jesteś uwierzytelniony, kończy twój własny dostęp, a następna komenda po prostu uwierzytelnia się ponownie. `auth-terminate-current` kończy sesję stojącą za używanymi danymi uwierzytelniającymi i zostawia te dane na dysku. Aby zakończyć sesję i razem z nią usunąć zapisany plik stanu uwierzytelnienia, użyj `auth logout --state-file FILE`, opisanego w [Uwierzytelnianiu](authentication.md#wznów-zapisane-uwierzytelnienie).

## Co warto zachować

Wyślij raz, a potem zachowaj tyle, żeby później odpowiedzieć bez pierwotnego procesu:

- numer referencyjny sesji, z pliku `--receipt`, z pliku stanu albo z `sessions invoice-list`;
- numer referencyjny faktury dla każdej wysyłki oraz numer KSeF, gdy zostanie nadany;
- numery referencyjne UPO ze statusu sesji oraz sam XML UPO;
- dla sesji wsadowej nazwy plików faktur, które zwrócił KSeF, bo tak odrzucona część mapuje się na plik na dysku;
- ostatni status, który zaobserwowałeś, do audytu.

Przechowuj pobrany XML UPO. Adres URL pobrania z KSeF ma termin ważności, a XML jest dokumentem podpisanym przez ministerstwo.

## Powiązane strony

- [Przepływy faktur](invoices.md)
- [Sesje interaktywne](online-sessions.md)
- [Sesje wsadowe](batch-sessions.md)
- [Uwierzytelnianie](authentication.md)
- [Opis komend](../reference/commands.md)
