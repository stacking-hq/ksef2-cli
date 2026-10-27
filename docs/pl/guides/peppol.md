---
title: Dostawcy PEPPOL
description: Wypisz dostawców usług PEPPOL zarejestrowanych w KSeF, przejdź ich stronicami i zachowaj listę jako dane referencyjne.
---

KSeF prowadzi publiczny rejestr dostawców usług PEPPOL. Grupa `peppol` ma jedną komendę i ona czyta ten rejestr. Działa na kliencie anonimowym, więc nie potrzebuje NIP-u, tokena, certyfikatu ani profilu:

```bash
uv run ksef2 peppol providers
```

```text
id=PPL000120 name=PPL000120 date_created=2026-02-23T08:17:19.144453+00:00
```

`--env` wybiera środowisko, o które pytasz. Gdy nie podasz ani `--env`, ani profilu, dostajesz `test`. Przykład powyżej czyta więc rejestr środowiska testowego. Rejestr produkcyjny bierzesz przez `--env production`:

```bash
uv run ksef2 --env production peppol providers
```

## Przejdź rejestr strona po stronie

`--page-size` ustawia liczbę pozycji na żądanie API, także z `--all`. `--all` wymaga, żeby `--page-offset` było równe 0, czyli swojej wartości domyślnej, i odrzuca przesunięcie inne niż zero.

Pierwsza strona mieści 10 dostawców. `--page-size` przyjmuje wartości od 10 do 100, `--page-offset` pomija rekordy, a `--all` przechodzi wszystkie strony w jednej komendzie:

```bash
uv run ksef2 peppol providers --page-size 50
uv run ksef2 peppol providers --page-size 50 --page-offset 50
uv run ksef2 peppol providers --all
```

`--page-offset` za ostatnim rekordem nic nie wypisuje i kończy się kodem 0. Dzięki temu taka pętla jest bezpieczna jako zgrubne przejście:

```bash
offset=0
while :; do
  rows=$(uv run ksef2 --json peppol providers --page-size 100 --page-offset "$offset")
  [ "$rows" = "[]" ] && break
  echo "$rows"
  offset=$((offset + 100))
done
```

`--all` robi to samo przejście za ciebie i tej opcji używaj na co dzień. `--page-size` spoza zakresu od 10 do 100 kończy się błędem użycia przed żądaniem:

```text
Invalid value for '--page-size': 5 is not in the range 10<=x<=100.
```

## Czytaj wiersze jako JSON

```bash
uv run ksef2 --json peppol providers --page-size 10
```

```json
[
  {
    "id": "PPL000120",
    "name": "PPL000120",
    "date_created": "2026-02-23T08:17:19.144453Z"
  }
]
```

`id` to identyfikator PEPPOL dostawcy, `name` to nazwa wyświetlana, którą trzyma KSeF i która bywa tym samym napisem, a `date_created` to moment wpisania rekordu do rejestru. Tryb tekstowy pomija puste pola, więc `name` może zniknąć z wiersza, podczas gdy `--json` zawsze podaje to pole.

## Zachowaj listę u siebie

Rekordy dostawców to dane referencyjne. Zmieniają się powoli, a zapytanie do rejestru w środku akcji użytkownika to jeszcze jedna rzecz, która może się nie powieść. Czytaj listę według własnego harmonogramu i zachowuj identyfikatory:

```bash
uv run ksef2 --json peppol providers --all \
  | jq -r '.[] | "\(.id)\t\(.name)"' > peppol-providers.tsv
```

Dane od użytkownika sprawdzaj względem zapisanych identyfikatorów, bez wywołania rejestru przy każdym znaku. Odświeżaj listę w rytmie, który uzasadnia twoja zasada świeżości danych.

## Gdzie indziej pojawiają się identyfikatory PEPPOL

Identyfikator PEPPOL jest jednym z typów kontekstu logowania i podmiotu, które przyjmuje reszta CLI. Dlatego ten rejestr warto mieć lokalnie:

- Opcja główna `--context-type` i zmienna `KSEF2_CONTEXT_TYPE` przyjmują `peppol_id` przy uwierzytelnianiu tokenem w kontekście PEPPOL. Zobacz [Uwierzytelnianie tokenem](authentication.md#uwierzytelnianie-tokenem).
- `permissions grant-authorization` przyjmuje `--subject-type peppol_id`, gdy partnera identyfikuje numer PEPPOL. Zobacz [Uprawnienia](permissions.md).

## Powiązane strony

- [Uwierzytelnianie](authentication.md)
- [Uprawnienia](permissions.md)
- [Opis komend](../reference/commands.md)
