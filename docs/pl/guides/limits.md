---
title: Limity
description: Odczytaj limity kontekstu logowania, podmiotu i częstości wywołań API KSeF, które cię dotyczą, oraz zarządzaj nadpisaniem limitów w środowisku testowym przez KSeF2 CLI.
---

Limity decydują, jak dużą paczkę możesz wysłać, jak często możesz wywoływać API i ile certyfikatów możesz posiadać. Grupa `limits` czyta liczby, które KSeF stosuje do bieżącego kontekstu logowania, a w środowisku testowym pozwala je nadpisać. Odczytaj obowiązujące wartości, zanim wybierzesz wielkość paczki albo odstęp ponowienia. Zaszyte w kodzie wartości domyślne z dokumentacji psują się w dniu, w którym kontekst dostaje inne.

Są trzy rodzaje i te same trzy słowa nazywają je wszędzie w tej grupie:

| Rodzaj | Co obejmuje |
| --- | --- |
| `context` | Limity rozmiaru sesji interaktywnej i wsadowej oraz limity identyfikatora zbiorczego. |
| `subject` | Liczby certyfikatów i wniosków dla tego podmiotu. |
| `api` | Częstość żądań na grupę endpointów, na sekundę, minutę i godzinę. |

## Odczytaj obowiązujące limity

```bash
uv run ksef2 --profile prod-token --json limits get context
```

```json
{
  "online_session": {
    "max_invoice_size_mb": 10,
    "max_invoice_with_attachment_size_mb": 20,
    "max_invoices": 100
  },
  "batch_session": {
    "max_invoice_size_mb": 10,
    "max_invoice_with_attachment_size_mb": 20,
    "max_invoices": 1000
  },
  "collective_identifier": {
    "max_invoices": 10
  }
}
```

`batch_session.max_invoices` to liczba faktur, które może nieść jedna sesja wsadowa, a `max_invoice_size_mb` to sufit jednej faktury. Te dwie liczby ustawiają wielkość paczki dla `invoices send --mode batch` i grupy `batch`.

Dwa pozostałe odczyty:

```bash
uv run ksef2 --profile prod-token --json limits get subject
```

```json
{
  "certificate": {
    "max_certificates": 5
  },
  "enrollment": {
    "max_enrollments": 3
  }
}
```

Oba obiekty są w odpowiedzi opcjonalne, więc podmiot bez limitu na podmiot nie zgłasza żadnego z nich. `certificates limits` podaje, na co KSeF pozwoli ci właśnie teraz, łącznie z tym, co już jest zużyte. To lepsze sprawdzenie przed złożeniem wniosku o certyfikat.

```bash
uv run ksef2 --profile prod-token --json limits get api
```

Odczyt API zwraca jeden obiekt na grupę endpointów, każdy z polami `per_second`, `per_minute` i `per_hour`. Taka jest postać. Liczby odczytujesz u siebie:

```json
{
  "invoice_send": { "per_second": 2, "per_minute": 60, "per_hour": 2000 }
}
```

Każda z tych grup pojawia się w odpowiedzi: `online_session`, `online_session_close`, `batch_session`, `batch_session_close`, `invoice_send`, `invoice_status`, `session_list`, `session_invoice_list`, `session_misc`, `invoice_metadata`, `invoice_export`, `invoice_export_status`, `invoice_download`, `collective_identifier`, `other`, `anonymous` i `global_`. Ostatnia jest sufitem nad pozostałymi, więc podniesienie jednej grupy dochodzi dokładnie do tego sufitu.

W trybie tekstowym każdy zagnieżdżony obiekt wypisuje się jako jedna zwarta wartość JSON we własnym wierszu. Da się to przeczytać. Skryptowi trudno to sparsować. Gdy skrypt potrzebuje liczby, użyj `--json` i `jq`:

```bash
uv run ksef2 --profile prod-token --json limits get api | jq '.invoice_send.per_minute'
```

## Nadpisz limity w środowisku testowym

`limits set` i `limits reset` zmieniają liczby, które KSeF stosuje do twojego kontekstu logowania w środowisku testowym. To operacje administracyjne i obowiązują każdy inny proces korzystający z tego kontekstu. KSeF przyjmuje je tylko z kontekstu, który może zarządzać limitami, więc zwykły podmiot środowiska testowego dostaje błąd. Trzymaj je w opisie procedury obok kroku, który je cofa, i nigdy nie wywołuj ich z kodu wysyłającego faktury.

`limits set` czyta nowe wartości z pliku JSON wskazanego przez `--payload`. Plik musi spełniać ten sam model, który zwraca komenda odczytu. Częściowa treść kończy się błędem i nie podmienia jednego pola.

Nadpisanie kontekstu potrzebuje wszystkich trzech grup. W `context.json`:

```json
{
  "online_session": {
    "max_invoice_size_mb": 10,
    "max_invoice_with_attachment_size_mb": 20,
    "max_invoices": 100
  },
  "batch_session": {
    "max_invoice_size_mb": 10,
    "max_invoice_with_attachment_size_mb": 20,
    "max_invoices": 1000
  },
  "collective_identifier": {
    "max_invoices": 10
  }
}
```

```bash
uv run ksef2 --env test --profile test-admin --json \
  limits set context --payload context.json
```

```json
{
  "kind": "context",
  "updated": true
}
```

Nadpisanie podmiotu jest najmniej wymagające, bo oba obiekty są opcjonalne. W `subject.json`:

```json
{
  "certificate": { "max_certificates": 5 },
  "enrollment": { "max_enrollments": 3 }
}
```

```bash
uv run ksef2 --env test --profile test-admin --json \
  limits set subject --payload subject.json
```

Nadpisanie API potrzebuje każdej grupy wymienionej powyżej, każdej z trzema oknami. Praktyczna droga do tego pliku to odczyt bieżących wartości i ich edycja:

```bash
uv run ksef2 --env test --profile test-admin --json \
  limits get api > api.json

uv run ksef2 --env test --profile test-admin --json \
  limits set api --payload api.json
```

## Odczytaj limit po ustawieniu

`limits set` zgłasza, że wywołanie się powiodło, i nic więcej. Zawsze potwierdź to zgodnym odczytem:

```bash
uv run ksef2 --env test --profile test-admin --json limits get context
```

Gdy nadpisanie nie chwyciło, odczyt i tak zwraca wartość, którą stosuje KSeF. Tak też sprawdzisz, że twój podmiot w ogóle nie może nadpisywać.

## Cofnij nadpisania

Reset zdejmuje nadpisanie i wraca do wartości domyślnej środowiska:

```bash
uv run ksef2 --env test --profile test-admin --json limits reset subject
```

```json
{
  "kind": "subject",
  "reset": true
}
```

Komenda resetu przyjmuje `api`, `session` i `subject`, a `limits get` i `limits set` przyjmują `api`, `context` i `subject`. Sesja i kontekst nazywają to samo dwoma różnymi słowami, więc `limits set context` idzie w parze z `limits reset session`. Odczyt złego rodzaju w złej komendzie kończy się na liście wyboru, zanim cokolwiek zostanie wysłane.

## Skopiuj częstości produkcyjne do środowiska testowego

Testy limitów częstości potrzebują liczb zbliżonych do produkcyjnych. Ręczne ich wpisywanie kończy się testem czegoś innego. Ta komenda prosi KSeF, żeby jednym wywołaniem zastosował produkcyjne wartości domyślne do limitów API w środowisku testowym:

```bash
uv run ksef2 --env test --profile test-admin --json \
  limits production-rate-limits
```

```json
{
  "api_rate_limits": "production"
}
```

Podmienia tylko nadpisania API. Limity kontekstu i podmiotu zostają takie, jakie ustawiłeś, a `limits reset api` cofa je z powrotem.

## Powiązane strony

- [Certyfikaty](certificates.md)
- [Przepływy faktur](invoices.md)
- [Konfiguracja](configuration.md)
- [Opis komend](../reference/commands.md)
