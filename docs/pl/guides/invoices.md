---
title: Przepływy faktur
description: Zapytania, pobieranie, eksport, wysyłka i paczki faktur w KSeF2 CLI.
---

Przepływy faktur zwykle zaczynają się od grupy `invoices`. Po grupy niższego poziomu, [Sesje interaktywne](online-sessions.md) i [Sesje wsadowe](batch-sessions.md), sięgaj wtedy, gdy potrzebujesz jawnego sterowania sesją. W skrypcie albo w zadaniu CI dodawaj `--json`.

[Faktury FA(3) lokalnie](fa3.md) opisują budowanie XML faktury bez łączenia się z KSeF. [Identyfikatory zbiorcze](collective.md) opisują grupowanie faktur, które już są w KSeF.

## Zapytanie o metadane

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  invoices metadata \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --date-to 2026-01-31T23:59:59Z \
  --all
```

`invoices metadata --page-size 12` zwraca jedną stronę, do 12 pozycji. `--all` pobiera każdą stronę, z najwyżej 12 pozycjami na żądanie API. `--all` wymaga, żeby `--page-offset` było równe 0, czyli swojej wartości domyślnej. Przesunięcie inne niż zero wybiera jedną stronę i nie łączy się z `--all`.

`invoices metadata`, `invoices export`, `invoices export-download` i `invoices export-pdf` przyjmują te same filtry, więc zapytanie dostrojone na metadanych powtarza się bez zmian na eksporcie:

- Okno: `--date-from` (wymagane) i `--date-to` po polu nazwanym przez `--date-type` (`issue_date`, `invoicing_date`, `permanent_storage`)
- Kontrahent: `--seller-nip`, `--buyer-nip`, `--buyer-vat-ue`, `--buyer-other-id`
- Tożsamość: `--invoice-number`, `--ksef-number`, `--form`, `--invoice-type`, `--currency`, `--invoicing-mode`
- Kwota: `--amount-type` z `--amount-min` i `--amount-max`
- Flagi: `--role`, `--attachment yes|no`, `--self-invoicing yes|no`

Opcje dat przyjmują też daty z dniem na początku, `DD.MM.YYYY` albo `DD-MM-YYYY`, z jedną albo dwiema cyframi dnia i miesiąca. Wartość bez przesunięcia jest tu czasem zegarowym w `Europe/Warsaw`, tak jak czyta ją SDK. Sama data `2026-01-01` to północ tego dnia czasu polskiego. Gdy okno ma oznaczać UTC, zapisz postać z `Z` albo `+HH:MM`.

`--restrict-hwm` (skrót `--restrict-to-permanent-storage-hwm-date`) ogranicza wynik do znacznika HWM trwałego zapisu, więc powtórzone żądania zwracają te same faktury. Bez tej flagi zapytanie idzie po tym, co KSeF ma w chwili przetwarzania żądania. Powtórzenie zapytania w trakcie napływu faktur daje za każdym razem inny zestaw. Dodaj flagę, gdy wiersze mają zostać stabilne między żądaniami, na przykład przy przejściu metadanych strona po stronie albo przy eksporcie ponawianym po błędzie.

## Pobierz jedną przetworzoną fakturę

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices download \
  --ksef-number "$KSEF_NUMBER" \
  --out invoice.xml
```

Bez `--out` komenda zapisuje `NUMBER.xml` w bieżącym katalogu, gdzie `NUMBER` to numer KSeF. Znaki niedozwolone w nazwach plików są zastępowane podkreśleniami. Plik wybierasz przez `--out PATH` albo lokalne `-o PATH`. Pobranie pliku wypisuje zapisaną ścieżkę i liczbę bajtów, a z `--json` dotychczasowy wynik JSON.

`--out -` albo lokalne `-o -` podaje oryginalne bajty XML do innej komendy potokiem:

```bash
uv run ksef2 --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices download --ksef-number "$KSEF_NUMBER" --out - \
  | xmllint --format -
```

Standardowe wyjście zawiera dokładnie pobrane bajty, z zachowanym kodowaniem, bez dopisanego nowego wiersza i bez podsumowania. Ten tryb nie tworzy pliku. Błędy i ewentualny postęp zostają na standardowym wyjściu błędów. Nie łącz `--out -` z globalnym `--json`, `--output json` ani `-o json`. Komenda odrzuca takie połączenie kodem wyjścia 2, zanim uwierzytelni się albo zacznie pobieranie. Błąd JSON idzie na standardowe wyjście błędów, a standardowe wyjście zostaje puste.

Dodaj `--wait`, gdy faktura może jeszcze nie być gotowa:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices download \
  --ksef-number "$KSEF_NUMBER" \
  --wait \
  --timeout 120 \
  --poll-interval 2
```

## Zaplanuj eksport i pobierz paczkę

Filtry powyżej przechodzą dalej. Eksport dodaje `--only-metadata`, które pomija treści faktur, `--compression-type zip|tar_gz` dla formatu paczki oraz `--handle-file` do zapisania pliku odszyfrowania eksportu. Najpierw zaplanuj eksport i zapisz ten plik:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  invoices export \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --handle-file export-handle.json
```

Sprawdź status:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices export-status --reference "$EXPORT_REFERENCE"
```

Pobierz i odszyfruj paczkę eksportu:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices export-fetch \
  --handle-file export-handle.json \
  --wait \
  --out-dir downloads
```

Jedna komenda, która sama czeka na eksport:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices export-download \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --timeout 300 \
  --out-dir downloads
```

`export-download` nie ma `--wait`: zawsze czeka, przez `--timeout` sekund (domyślnie `120`), ze sprawdzeniem co `--poll-interval` sekund. Osobnych komend `export` i `export-fetch` używaj, gdy między zaplanowaniem a pobraniem chcesz odejść od komputera.

## Wyrenderuj eksport do PDF

`invoices export-pdf` to `export-download` plus krok renderowania. Planuje eksport, czeka, odszyfrowuje paczkę do `--out-dir` i renderuje XML każdej faktury do PDF.

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  invoices export-pdf \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --out-dir downloads \
  --pdf-dir pdfs
```

| Opcja | Do czego służy |
| --- | --- |
| `--out-dir DIR` | Gdzie trafia odszyfrowany XML faktury. Domyślnie `downloads`. |
| `--pdf-dir DIR` | Gdzie trafiają pliki PDF. Domyślnie `--out-dir`, więc PDF leży obok swojego XML. |
| `--paper-size` | `a4`, `a4-landscape`, `a3`, `a3-landscape`, `letter` albo `letter-landscape`. Pomiń, żeby zostawić papier z arkusza stylów, zwykle A4 w poziomie. |

Każdy PDF zawiera kod QR do weryfikacji, który KSeF publikuje dla faktury. Kod powstaje z numeru KSeF, który własne `_metadata.json` paczki podaje dla tej faktury. Ten manifest jest pobierany razem z fakturami, ale nigdy nie jest renderowany. Faktura, której manifest nie opisuje, i tak jest renderowana, bez kodu QR.

Renderowanie PDF używa WeasyPrint, które przychodzi z opcjonalnym dodatkiem `pdf`. Przed tą komendą zainstaluj CLI jako `ksef2-cli[pdf]`. Bez dodatku komenda podaje polecenie instalacji i zatrzymuje się. Każda inna komenda nadal działa. Zobacz [Instalacja](../getting-started/installation.md#generowanie-pdf).

Plik, który już masz, renderujesz bez łączenia się z KSeF przez [`fa3 render`](fa3.md).

## Wyślij faktury

Domyślnie `invoices send` otwiera sesję interaktywną, wysyła plik XML, zamyka sesję i wypisuje jeden wiersz na fakturę:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  invoices send invoice.xml
```

Poczekaj na końcowe przetworzenie i pobierz UPO do katalogu:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  invoices send invoice.xml \
  --wait \
  --upo-dir upos
```

Zapisz plik `--receipt`, gdy status albo UPO chcesz pobrać później:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  invoices send invoice.xml \
  --receipt invoice-receipt.json

uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  invoices status --receipt invoice-receipt.json --wait

uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  invoices upo --receipt invoice-receipt.json --out invoice-upo.xml
```

Wyślij każdy plik XML leżący bezpośrednio w katalogu:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --test-cert \
  invoices send invoices/ --receipt-dir receipts
```

`--recursive` obejmuje katalogi zagnieżdżone. Gdy w sesji interaktywnej któryś plik się nie powiedzie, komenda i tak próbuje pozostałe pliki, a po wypisaniu wyników poszczególnych plików kończy się kodem `1`.

Dwa połączenia zatrzymują się, zanim cokolwiek zostanie wysłane. `--upo-dir` wymaga `--wait`, bo UPO nie ma czego pobierać, dopóki przetwarzanie się nie skończy. `--receipt` wskazuje jeden plik, więc kilka faktur potrzebuje `--receipt-dir`.

### Wyślij XML ze standardowego wejścia

Jedno `-` czyta fakturę ze standardowego wejścia, w sesji interaktywnej albo wsadowej:

```bash
ksef2 --profile test-company invoices send - --wait --receipt receipt.json < invoice.xml
```

CLI trzyma oryginalne bajty w pamięci i w wynikach oraz plikach `--receipt` używa nazwy `stdin.xml`. Gdy inne wejście ma tę nazwę, używa `stdin-2.xml` albo kolejnego wolnego numeru. Nie powstaje tymczasowy plik faktury otwartym tekstem. Puste wejście, BOM UTF-8 i wejście UTF-16 są odrzucane przed uwierzytelnieniem. Przed podpisaniem wyeksportuj XML ponownie jako UTF-8 bez BOM.

### Przerwana wysyłka nie oznacza, że faktury nie przyjęto

KSeF przyjmuje fakturę w chwili, gdy dochodzi żądanie wysyłki. Wszystko później to CLI, które obserwuje wynik. Ctrl-C, `--wait`, które wyczerpie `--timeout`, zamknięty terminal i zabity kontener kończą komendę, a faktura zostaje wysłana. Żadne z tych zdarzeń nie mówi, że faktury nie wysłano.

Komenda jest na to zbudowana. W sesji interaktywnej zapisuje plik `--receipt`, który zawiera stan sesji i numer referencyjny faktury, gdy tylko KSeF przyjmie plik. W sesji wsadowej zapisuje plik `--receipt` z numerem referencyjnym sesji, zanim zacznie sprawdzać status. Przerwana w trakcie `--wait` wysyłka mówi o tym wprost (`... was submitted, but waiting stopped: ... do not submit the invoice again`) i kończy się kodem `130` przy Ctrl-C albo `1` w pozostałych przypadkach. Bez `--receipt` numery referencyjne zostają tylko w tym komunikacie błędu.

Gdy wysyłka kończy się źle, sprawdź, co ma KSeF, zanim wyślesz cokolwiek ponownie:

```bash
uv run ksef2 --profile test-company --json \
  invoices status --receipt invoice-receipt.json --wait
```

Bez pliku `--receipt` nie ma czego odczytać. Weź numer referencyjny sesji z tego błędu i zapytaj przez `sessions invoice-list --type online --reference REF` albo, dla paczki, przez `batch status --reference REF`. `online list` i `online invoice-status` chcą pliku stanu. Numer referencyjny im nie wystarcza. Druga wysyłka tworzy w KSeF drugą fakturę. Pierwsza zostaje bez zmian. Sprawdzenie kosztuje jeden odczyt. Zgadywanie zostawia dokument, który trzeba potem wyjaśnić. Wyślij plik ponownie dopiero wtedy, gdy zobaczysz, że KSeF go nie ma albo ma go jako fakturę odrzuconą.

Między trybami jest jedna różnica, ważna przy wznowieniu. `invoices send` w sesji interaktywnej prowadzi własną sesję i zamyka ją przy wyjściu także wtedy, gdy oczekiwanie zostało przerwane. Sesja, którą prowadzisz przez grupę `online`, zostaje otwarta, dopóki jej nie zamkniesz. Zobacz [Sesje interaktywne](online-sessions.md).

## Wyślij faktury jako paczkę

`--mode batch` przygotowuje pliki wejściowe i wysyła je jako jedną sesję wsadową:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices send invoices/ \
  --mode batch \
  --wait \
  --upo-dir upos \
  --receipt batch-receipt.json
```

Plik `--receipt` sesji wsadowej nadaje się ponownie do statusu i do pobrania UPO:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices status --receipt batch-receipt.json --wait

uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices upo --receipt batch-receipt.json --upo-dir upos
```

`invoices upo` przy pliku `--receipt` sesji wsadowej potrzebuje `--upo-dir`. KSeF zwraca potwierdzenie stronami, a `--out` mieści jeden plik. `--offline` i `--max-part-size` należą do tego trybu i kończą się błędem przy `--mode online`.

Obie komendy wznawiają sesję wsadową ze stanu wewnątrz pliku `--receipt`. Dlatego ten plik jest materiałem uwierzytelniającym. Plik zapisany przez wersję CLI, która trzymała tylko numer referencyjny sesji, nie potrafi jej wznowić i tak właśnie to zgłasza. Dokończ pracę przez `batch status` albo `batch upo` z `--state-file` albo wyślij faktury ponownie.

Aby samemu trzymać stan sesji, przygotować paczkę raz i przesłać ją więcej niż raz albo odzyskać przesłanie, które KSeF odrzucił, użyj [Sesji wsadowych](batch-sessions.md).

## Komendy sesji niższego poziomu

Wszystko powyżej prowadzi sesję, którą `invoices send` otwiera i zamyka za ciebie. Gdy potrzebujesz samej sesji, dwie grupy niższego poziomu działają na niej bezpośrednio, a trzecia podpowiada, która komenda UPO pasuje:

- [Sesje interaktywne](online-sessions.md): `online open`, `send`, `status`, `list`, `invoice-status`, `upo` i `close`, z `--state-file` i `--keep-open` dla sesji, która ma trwać dłużej niż jedna komenda.
- [Sesje wsadowe](batch-sessions.md): `batch submit`, `prepare`, `upload`, `status`, `list` i `upo`, łącznie z trybem offline i z odzyskaniem przesłania, które KSeF odrzucił.
- [Sesje i UPO](sessions-and-upo.md): UPO dowolnej dawnej sesji z samego numeru referencyjnego, historia sesji faktur i sesje uwierzytelniania.

Pliki stanu sesji (`--state-file`, `--save-state`), pliki `--receipt` przepływu faktur (`--receipt`, `--receipt-dir`) i pliki `--handle-file` to stan kontynuacji zapisany **otwartym tekstem**, z uprawnieniami tylko dla właściciela (`0600`). Plik `--receipt` sesji interaktywnej zawiera stan sesji do wznowienia, więc jej klucz AES i IV, dokładnie tak jak `online open --state-file`. Plik `--handle-file` zawiera klucz eksportu i IV. Plik `--receipt` sesji wsadowej jest wyjątkiem i trzyma numery referencyjne. Tryb `0600` decyduje, kto może otworzyć plik. O zawartości nie mówi nic. Kopia w kopii zapasowej, w artefakcie CI, w warstwie Dockera albo w commicie jest ujawnionym kluczem, niezależnie od uprawnień po drodze. Katalog zapisany przez `batch prepare` trzyma ten klucz razem z zaszyfrowanymi treściami faktur.

Traktuj je wszystkie tak, jak token. Trzymaj je poza repozytorium i wpisz do `.gitignore`. Nie wklejaj ich do zgłoszeń ani logów i usuń, gdy przepływ się skończy. Do przekazania dalej nadaje się numer referencyjny: sesji, faktury albo numer KSeF. `sessions upo` i `invoices status` potrafią z nimi dużo zrobić. Zobacz [Która komenda UPO pasuje](sessions-and-upo.md#która-komenda-upo-pasuje).
