---
title: KSeF2 CLI
description: Interfejs wiersza poleceń dla SDK ksef2 w Pythonie.
---

KSeF2 CLI udostępnia SDK `ksef2` dla Pythona jako narzędzie wiersza poleceń, z którego da się korzystać w skryptach. Przyda się do pracy lokalnej, zadań CI i skryptów operacyjnych, gdy trzeba uwierzytelnić się w KSeF, zapytać o faktury, wysłać faktury, podejrzeć sesje albo zarządzać zasobami administracyjnymi bez pisania kodu w Pythonie.

CLI domyślnie nie pamięta stanu między wywołaniami. Komendy wymagające uwierzytelnienia biorą dane uwierzytelniające z opcji globalnych albo ze zmiennych środowiskowych. Na komputerze, na którym rozwijasz integrację, możesz trzymać lokalny plik konfiguracji. W środowisku współdzielonym sekrety podawaj zmiennymi środowiskowymi albo z zaufanego magazynu sekretów.

Domyślne środowisko to `test`. Wybrany profil niesie środowisko, gdy nie podasz `--env`, a `--env` ma pierwszeństwo przed profilem. Dlatego nadal działają `--env production` i profil z `environment = "production"`. W wersji 1.0 zmieniło się tylko zachowanie zapasowe: komenda bez `--env` i bez profilu łączy się ze środowiskiem testowym. Wcześniej w takiej sytuacji CLI wybierało środowisko produkcyjne.

Wynik zależy od tego, czy komenda się powiodła. Sukces trafia na standardowe wyjście, jako zwykły tekst albo jako jeden dokument JSON z `--json`. Błąd trafia na standardowe wyjście błędów, a standardowe wyjście zostaje puste. W trybie JSON błąd to jeden obiekt: `{"error": {"type": ..., "title": ..., "message": ..., "details": [...], "hints": [...], "exit_code": ..., "ksef": {"ksef_code": ..., "trace_id": ..., "status_code": ...}}}`. Kody wyjścia to `0` przy sukcesie, `1` przy błędzie wykonania, `2` przy błędzie użycia i `130` po Ctrl-C. Zobacz [Tryby wyniku](guides/configuration.md#tryby-wyniku).

Pliki, którymi CLI pozwala dokończyć przepływ, czyli stan uwierzytelnienia, stan sesji, pliki `--handle-file` i pliki `--receipt`, trzymają dane uwierzytelniające albo klucze sesji otwartym tekstem. CLI nadaje im tryb `0600`. To uprawnienie do pliku. Zawartość pozostaje zapisana otwartym tekstem. Trzymaj te pliki poza commitami, logami i wątkami zgłoszeń.

## Zacznij tutaj

- [Zainstaluj CLI i uruchom je](getting-started/installation.md)
- [Przejdź szybki start](getting-started/quickstart.md)
- [Wybierz metodę uwierzytelniania](guides/authentication.md)
- [Użyj lokalnej konfiguracji](guides/configuration.md)
- [Pracuj z fakturami i sesjami](guides/invoices.md)
- [Zbuduj faktury FA(3) lokalnie](guides/fa3.md)
- [Grupuj faktury identyfikatorami zbiorczymi](guides/collective.md)
- [Przejrzyj opis komend](reference/commands.md)

## Postać komendy

Pakiet udostępnia dwa równoważne programy:

```bash
ksef2
ksef2-cli
```

Opcje globalne stoją przed grupą komend:

```bash
ksef2 --env test --nip 5261040828 --test-cert --json auth login
```

`--version` wypisuje wersję CLI i wersję SDK, którą CLI wczytało. Nie czyta przy tym pliku konfiguracji.

Grupy komend odpowiadają obszarom SDK:

- `auth`
- `invoices`
- `collective`
- `fa3`
- `online`
- `batch`
- `tokens`
- `sessions`
- `certificates`
- `permissions`
- `limits`
- `peppol`
- `encryption`
- `testdata`
- `config`
- `profile`

## Wynik list

Komendy listujące i odpytujące rekordy pokazują tabele tekstowe. Identyfikatory zostają w całości, a długie nazwy i opisy mogą kończyć się znakiem `…`. W wąskim terminalu CLI może ukryć kolumny opcjonalne. Wynik przekierowany używa układu o szerokości 120 kolumn. Pusta lista wypisuje `No results.`. Nagłówki daty i czasu oznaczają UTC, daty mają postać `YYYY-MM-DD`, a kwoty dwa miejsca po przecinku. Dostępne metadane stronicowania pojawiają się pod tabelą.

`--json` przed grupą komend zwraca wszystkie pola i wartości SDK bez zmian, łącznie z nullami. Na przykład `ksef2 --profile test-company --json tokens list`.

Pojedynczy rekord nie jest tabelą, więc CLI zachowuje każdy znak. Wartość szersza niż terminal schodzi do wierszy wciętych pod swoją nazwą. Terminal podaje własną szerokość, a wynik przekierowany bierze ją z `COLUMNS`, więc `COLUMNS=80 ksef2 fa3 inspect --in faktura.xml` łamie wiersze do 80 kolumn. Wynik bez podanej szerokości zostaje jednym polem na wiersz.
