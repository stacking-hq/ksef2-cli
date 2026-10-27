---
title: Szybki start
description: Uwierzytelnij się w środowisku testowym, pobierz metadane faktur i wyślij fakturę przez KSeF2 CLI.
---

Ten szybki start korzysta ze środowiska testowego i z certyfikatu testowego generowanego przez SDK. W środowisku przedprodukcyjnym (demo) i produkcyjnym użyj prawdziwego certyfikatu XAdES albo tokena KSeF. Domyślne środowisko to już `test`, więc `--env test` poniżej jest podane wprost i nie jest wymagane. Komenda, która nie nazywa środowiska ani profilu, łączy się ze środowiskiem testowym. Jawne `--env production` albo profil z `environment = "production"` nadal oznacza środowisko produkcyjne.

## 1. Sprawdź CLI

```bash
uv run ksef2 --help
uv run ksef2 --version
```

`--version` wypisuje wersję CLI i wersję SDK `ksef2`, którą CLI wczytało, po jednej pozycji w wierszu. Nie czyta pliku konfiguracji ani danych uwierzytelniających.

## 2. Utwórz profil środowiska testowego

Profil trzyma powtarzane opcje, które nie są sekretami, w jednym lokalnym pliku konfiguracji. Uwierzytelnianie certyfikatem testowym nadaje się do pracy lokalnej:

```bash
uv run ksef2 profile create test-company \
  --env test \
  --nip 5261040828 \
  --test-cert
```

Uwierzytelnij się tym profilem i wypisz zamaskowane tokeny wraz z czasem wygaśnięcia:

```bash
uv run ksef2 --profile test-company --json auth login
```

Każdy token wraca skrócony do przedrostka i przyrostka, obok czasu wygaśnięcia. Log albo wklejony komentarz nie zawiera wtedy niczego, czym dałoby się ponownie uwierzytelnić. `--show-tokens` wypisuje surowe tokeny na okaziciela. Komenda, która zapisuje stan, zostaje zamaskowana także z tą flagą.

Aby zachować dane uwierzytelniające na kolejne komendy, zapisz je:

```bash
uv run ksef2 --profile test-company --json auth login --save-state ksef2-auth.json
```

Zapisany plik trzyma tokeny na okaziciela otwartym tekstem i powstaje z trybem `0600`. Ten tryb odcina innych użytkowników. Zawartość pozostaje zapisana otwartym tekstem, więc trzymaj plik poza repozytorium i poza commitem.

Opcje globalne, takie jak `--profile`, `--env`, `--nip`, `--test-cert` i `--json`, muszą stać przed grupą komend.

Aby użyć tego stanu bez logowania przy każdej komendzie, wskaż plik globalną opcją `--auth-state`, jak w `ksef2 --profile test-company --auth-state ksef2-auth.json --json auth logout`. Zobacz [Uwierzytelnianie](../guides/authentication.md#wznów-zapisane-uwierzytelnienie).

## 3. Pobierz metadane faktur

```bash
uv run ksef2 --profile test-company --json \
  invoices metadata \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --all
```

Przy uwierzytelnianiu tokenem w CI pomiń profil i podaj opcje główne wprost, z jawnie nazwanym środowiskiem:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  invoices metadata \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --all
```

## 4. Wyślij jedną fakturę i pobierz UPO

Potrzebujesz XML faktury do wysyłki? `fa3 draft-example` i `fa3 build` tworzą go lokalnie, bez danych uwierzytelniających. Zobacz [Faktury FA(3) lokalnie](../guides/fa3.md).

```bash
uv run ksef2 --profile test-company \
  invoices send invoice.xml \
  --wait \
  --upo-dir upos \
  --receipt invoice-receipt.json
```

Domyślnie `invoices send` działa w trybie sesji interaktywnej. Plik `--receipt` pozwala później sprawdzić status albo pobrać UPO (Urzędowe Poświadczenie Odbioru) bez samodzielnego prowadzenia sesji:

```bash
uv run ksef2 --profile test-company \
  invoices status --receipt invoice-receipt.json --wait

uv run ksef2 --profile test-company \
  invoices upo --receipt invoice-receipt.json --out invoice-upo.xml
```

## 5. Wyślij katalog albo paczkę

```bash
uv run ksef2 --profile test-company \
  invoices send invoices/ --receipt-dir receipts
```

Wejście z katalogu obejmuje bezpośrednie pliki potomne `*.xml`. `--recursive` dodaje katalogi zagnieżdżone. `--mode batch` wysyła pliki jako jedną paczkę faktur w sesji wsadowej:

```bash
uv run ksef2 --profile test-company \
  invoices send invoices/ --mode batch --wait --upo-dir upos
```

Plik `--receipt` to stan do wznowienia. Plik z sesji interaktywnej niesie klucz AES sesji i IV otwartym tekstem, więc CLI zapisuje te pliki z trybem `0600`. Należą poza repozytorium, tak jak stan uwierzytelnienia.

Gdy wysyłka zostanie przerwana albo `--wait` wyczerpie czas, to jeszcze nie dowód, że faktury nie przyjęto. KSeF może już ją mieć. Zanim wyślesz ten sam XML ponownie, odczytaj plik `--receipt` albo zapytaj przez `invoices status --receipt FILE`.

## Co wypisuje CLI

Udane wywołanie pisze na standardowe wyjście: domyślnie zwykły tekst, a z `--json` jeden dokument JSON. Błędy komendy idą na standardowe wyjście błędów i zostawiają standardowe wyjście puste. Dokończone `invoices send` z odrzuconymi pozycjami zapisuje wynik na standardowe wyjście i kończy się kodem 1. W trybie JSON błąd komendy to jeden obiekt:

```json
{"error": {"type": "RemoteServiceError", "title": "KSeF rejected the request", "message": "...", "details": [], "hints": [], "exit_code": 1, "ksef": {"status_code": 400, "ksef_code": 21405, "trace_id": "..."}}}
```

`type` nazywa klasę błędu CLI, a `title` podaje krótki opis. `details`, `hints` i `exit_code` są zawsze. Obiekt `ksef` pojawia się tylko wtedy, gdy KSeF odpowiedział, i niesie `status_code`, `ksef_code` oraz `trace_id` tej usługi. Nieoczekiwany błąd CLI dodaje `report_url`, a `--verbose` dodaje `traceback`. Odrzucony wiersz polecenia zgłasza `"type": "UsageError"` z `"exit_code": 2`.

| Kod wyjścia | Znaczenie |
| --- | --- |
| `0` | Sukces. |
| `1` | Błąd wykonania: odrzucone żądanie, przekroczenie czasu po stronie KSeF, brakujące albo sprzeczne dane uwierzytelniające, zły plik. |
| `2` | Błąd użycia: nieznana opcja, brakujący argument albo niedozwolona wartość, na przykład NIP ze złą sumą kontrolną. |
| `130` | Przerwanie przez Ctrl-C. Nie cofa niczego, co KSeF już przyjął. |

`invoices send` kończy się kodem `1`, gdy którykolwiek plik się nie powiódł, po wypisaniu wyniku każdego pliku.

## Powiązane strony

- [Uwierzytelnianie](../guides/authentication.md)
- [Konfiguracja](../guides/configuration.md)
- [Przepływy faktur](../guides/invoices.md)
- [Faktury FA(3) lokalnie](../guides/fa3.md)
- [Identyfikatory zbiorcze](../guides/collective.md)
- [Opis komend](../reference/commands.md)
