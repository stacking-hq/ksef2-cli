---
title: Faktury FA(3) lokalnie
description: Zbuduj, obejrzyj i wyrenderuj XML faktury FA(3) w KSeF2 CLI, bez łączenia się z KSeF.
---

Grupa `fa3` korzysta z publicznego buildera i renderera SDK. Nie otwiera klienta, więc żadna z tych komend nie potrzebuje NIP-u, tokena ani certyfikatu. Służą do zamiany szkicu JSON na XML FA(3) zgodny ze schematem, do odczytu faktury, którą ktoś ci przekazał, i do przygotowania widoku do druku. Zbudowanie faktury tutaj jej nie wysyła. Gotowy XML przekaż przez [invoices send](invoices.md#wyślij-faktury).

## 1. Zacznij od szkicu

```bash
uv run ksef2 fa3 draft-example --out draft.json
```

Bez `--out` szkic trafia na standardowe wyjście. Szkic to zwykły obiekt JSON z polami `header`, `seller`, `buyer` i `body`. W `body.rows` są pozycje, a builder liczy kwoty i podsumowanie VAT, więc w szkicu nie ma sum do utrzymywania w zgodzie.

## 2. Zbuduj XML

```bash
uv run ksef2 fa3 build --in draft.json --out invoice.xml
```

`--in -` czyta szkic ze standardowego wejścia. Tak przekażesz szkic z innego narzędzia potokiem:

```bash
cat draft.json | uv run ksef2 fa3 build --in - --out invoice.xml
```

| Opcja | Do czego służy |
| --- | --- |
| `--out FILE` | Gdzie zapisać XML. Bez tej opcji XML idzie na standardowe wyjście. |
| `--pretty` / `--no-pretty` | Wcięcie XML. Włączone domyślnie. |
| `--validate` / `--no-validate` | Sprawdzenie XML względem schematu FA(3) przed zapisem. Włączone domyślnie. |

`--no-validate` pomija tylko sprawdzenie schematu. Builder nadal odrzuca szkice, z których nie da się zrobić faktury, a komunikat nazywa brakującą część:

```text
Error: Invoice seller is required but not set.
```

## 3. Obejrzyj fakturę

```bash
uv run ksef2 fa3 inspect --in invoice.xml
```

Wynik tekstowy wypisuje po jednym wierszu dla `header`, `seller`, `buyer` i `body`. Możesz sprawdzić kontrahenta, numer faktury albo wyliczone kwoty jednej pozycji. Sekcja za szeroka na terminal schodzi do wierszy wciętych pod swoją nazwą, więc nic nie jest obcinane. `COLUMNS=80` łamie wiersze do 80 kolumn w potoku tak samo jak w terminalu. `--json` daje całą sparsowaną fakturę jako jeden obiekt:

```bash
uv run ksef2 --json fa3 inspect --in invoice.xml | jq '.body.rows[0]'
```

## 4. Wyrenderuj HTML, a PDF gdy go potrzebujesz

```bash
uv run ksef2 fa3 render --in invoice.xml --out invoice.html
```

PDF wymaga dodatku opcjonalnego:

```bash
uv sync --extra pdf              # project checkout
uv tool install "ksef2-cli[pdf]"  # installed CLI

uv run ksef2 fa3 render --in invoice.xml --out invoice.html --pdf invoice.pdf
```

Bez tych zależności komenda sprawdza je najpierw i kończy się kodem `1`, podając nazwę dodatku. Nie powstaje wtedy ani HTML, ani niedokończony PDF. Biblioteki systemowe WeasyPrint, w tym `DYLD_FALLBACK_LIBRARY_PATH`, którego kopia robocza na macOS często potrzebuje ponad Homebrew, opisuje [Generowanie PDF](../getting-started/installation.md#generowanie-pdf).

`--ksef-number` dodaje kod QR weryfikacji, który KSeF publikuje dla przyjętej faktury. Numer jest drukowany pod kodem, a kod prowadzi do strony weryfikacji KSeF dla wybranego `--env`. Pomiń tę opcję przy szkicu. PDF szkicu nie ma kodu QR.

```bash
uv run ksef2 fa3 render --in invoice.xml --pdf invoice.pdf \
  --ksef-number 5252222222-20260409-ABCDEF123456-AB
```

`--code-lookups` rozwija kody krajów, urzędów skarbowych i walut według oficjalnych list dołączonych do SDK. Dostęp do sieci i zapisy pozostają zablokowane. Nieznany adres URI wyszukania przerywa renderowanie i podaje w szczegółach nierozwiązany URI. `--no-code-lookups` zostawia wartości kodowane jako kody.

## Powiązane strony

- [Przepływy faktur](invoices.md)
- [Identyfikatory zbiorcze](collective.md)
- [Opis komend](../reference/commands.md)
