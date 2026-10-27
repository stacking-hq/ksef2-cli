---
title: Identyfikatory zbiorcze
description: Grupuj wysłane faktury pod identyfikatorem zbiorczym i odczytaj grupowanie w obie strony przez KSeF2 CLI.
---

Identyfikator zbiorczy to numer KSeF, który grupuje faktury należące do siebie, na przykład rozliczane jedną płatnością. Grupa `collective` generuje takie identyfikatory i odczytuje grupowanie w obie strony. Wszystkie komendy w tej grupie wskazują faktury po numerze KSeF. Ta grupa nie przyjmuje lokalnych plików XML, więc najpierw wyślij faktury i zachowaj ich numery KSeF z UPO albo z `invoices metadata`.

## Wygeneruj identyfikator

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  collective generate \
  --invoice "$KSEF_NUMBER_1" \
  --invoice "$KSEF_NUMBER_2"
```

`--invoice` powtarzasz raz na fakturę, którą chcesz zgrupować. Wynikiem jest nowy `collective_identifier_number`. Komenda kończy się błędem, gdy ani `--invoice`, ani `--invoices-file` nie poda choć jednej faktury.

## Dołącz płatność i opis

`--invoices-file` przyjmuje tablicę JSON, jeden obiekt na fakturę. Tylko tak dodasz płatność i opis przy konkretnej fakturze:

```json
[
  {
    "ksef_number": "PASTE_A_KSEF_NUMBER",
    "payment": { "amount": 1230.0, "currency": "PLN" },
    "description": "March consulting"
  }
]
```

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  collective generate \
  --invoices-file invoices.json \
  --invoice "$KSEF_NUMBER_3"
```

Oba źródła schodzą się w jednym żądaniu: najpierw wpisy z pliku, potem wartości `--invoice`, które nie mają płatności ani opisu.

## Wypisz identyfikatory

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  collective list \
  --date-from 2026-03-01 \
  --date-to 2026-03-31 \
  --all
```

`--date-from` jest wymagane i filtruje po czasie utworzenia. `--date-to` domyślnie oznacza teraz, więc sama data w `--date-from` bez `--date-to` oznacza „od tego dnia do teraz”. KSeF chce jednej jednoznacznej chwili dla obu granic. Data bez godziny, zapisana jako `2026-03-01` albo `01.03.2026`, to północ tego dnia w UTC. Data z czasem musi mieć przesunięcie, więc `2026-03-01T08:00:00Z` i `2026-03-01T08:00:00+01:00` są przyjmowane, a `2026-03-01T08:00:00` jest odrzucane, zanim cokolwiek zostanie wysłane. Dalej zawężasz przez `--number` dla jednego dokładnego identyfikatora, `--invoice-count-min` i `--invoice-count-max` dla wielkości grupy oraz `--current-context yes` dla identyfikatorów utworzonych w tym kontekście logowania albo `no` dla pozostałych.

## Idź za grupowaniem

Od jednej faktury do identyfikatorów, które na nią wskazują:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  collective list-for-invoice --ksef-number "$KSEF_NUMBER_1"
```

Od identyfikatorów do faktur pod nimi, z kilkoma identyfikatorami w jednym żądaniu:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  collective list-invoices "$IDENTIFIER_1" "$IDENTIFIER_2"
```

KSeF przyjmuje najwyżej 10 numerów identyfikatorów na żądanie. Większa liczba kończy się błędem przed wywołaniem i mówi, żeby resztę uruchomić osobnymi komendami.

## Uwagi do skryptów

Trzy komendy listujące stronicują tak samo jak reszta CLI: `--page-size` od 10 do 200, `--all` przechodzi wszystkie strony, a `--json` daje wiersze do dalszego przetwarzania. W wyniku tekstowym `list-invoices` wypisuje przy fakturze `ksef_number`, `payment`, `description` i `hidden`, a `list` wypisuje identyfikator, czas utworzenia i liczbę zgrupowanych faktur.

## Powiązane strony

- [Przepływy faktur](invoices.md)
- [Faktury FA(3) lokalnie](fa3.md)
- [Opis komend](../reference/commands.md)
