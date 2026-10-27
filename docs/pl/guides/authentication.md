---
title: Uwierzytelnianie
description: Skonfiguruj uwierzytelnianie KSeF2 CLI profilem, tokenem, certyfikatem testowym, danymi PEM XAdES albo archiwum PKCS#12.
---

Komendy wymagające uwierzytelnienia tworzą klienta SDK na jedną operację, uwierzytelniają go wybraną metodą, wykonują komendę i zamykają klienta. Na komputerze, na którym rozwijasz integrację, trzymaj profil. W CI i w jednorazowych skryptach podawaj opcje główne albo zmienne środowiskowe.

Opcje główne muszą stać przed grupą komend:

```bash
ksef2 [ROOT OPTIONS] invoices metadata [COMMAND OPTIONS]
```

## Do którego środowiska trafia logowanie

Domyślne środowisko to `test`. Wybrany profil podaje środowisko, gdy nie przekażesz `--env`, a `--env` ma pierwszeństwo przed profilem. Dla pracy produkcyjnej nic się tu nie zmieniło: `--env production` nadal uwierzytelnia w środowisku produkcyjnym, tak samo profil z `environment = "production"`. Zmieniło się zachowanie zapasowe. Dane uwierzytelniające, które wcześniej trafiały do produkcji przez samo pominięcie środowiska, teraz trafiają do środowiska testowego. W każdej komendzie, którą zapisujesz w skrypcie albo wklejasz, nazwij środowisko albo profil, który je niesie.

Certyfikat testowy działa tylko w środowisku testowym. `--test-cert` wobec innego środowiska kończy się kodem `2`, zanim CLI wyśle jakiekolwiek żądanie. Tak samo kończy się profil, który łączy uwierzytelnianie `test_certificate` ze środowiskiem innym niż testowe. Aby wyprzeć metodę z profilu i zostawić jego pozostałe wartości domyślne, podaj prawdziwe dane uwierzytelniające.

## Profile do pracy lokalnej

Utwórz jeden profil na podmiot albo kontekst logowania w KSeF. Profil trzyma wartości domyślne, które nie są sekretami: środowisko, NIP, metodę uwierzytelniania, ścieżki certyfikatów, ustawienia cyklicznego sprawdzania statusu oraz nazwy zmiennych środowiskowych z sekretami.

Do pracy w środowisku testowym z certyfikatem generowanym przez SDK:

```bash
uv run ksef2 profile create test-company \
  --env test \
  --nip 5261040828 \
  --test-cert
```

Przy tokenie zapisz nazwę zmiennej środowiskowej. Wartość tokena zostaw poza profilem:

```bash
uv run ksef2 profile create prod-token \
  --env production \
  --nip "$KSEF2_NIP" \
  --token-env KSEF2_TOKEN
```

Dane PEM XAdES:

```bash
uv run ksef2 profile create demo-pem \
  --env demo \
  --nip "$KSEF2_NIP" \
  --cert company.pem \
  --key company.key \
  --key-password-env KSEF2_KEY_PASSWORD
```

Dane PKCS#12/PFX:

```bash
uv run ksef2 profile create prod-p12 \
  --env production \
  --nip "$KSEF2_NIP" \
  --p12 signing-credentials.p12 \
  --p12-password-env KSEF2_P12_PASSWORD
```

`profile create` domyślnie wybiera nowy profil. Inny profil na jedną komendę podajesz przez `--profile`, a na bieżącą powłokę przez `KSEF2_PROFILE`:

```bash
uv run ksef2 --profile prod-token --json auth login

export KSEF2_PROFILE=test-company
uv run ksef2 --json invoices metadata \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --all
```

`KSEF2_PROFILE` wybiera ustawienia na czas uruchomienia. Nie przepisuje zapisanego `active_profile`. Gdy chcesz utrwalić wybór w pliku konfiguracji, użyj `ksef2 profile use NAME`.

## Uwierzytelnianie bezpośrednie w skryptach

W opcjach głównych albo w zmiennych środowiskowych podaj dokładnie jedną metodę uwierzytelniania:

| Metoda | Opcje główne | Zmienne środowiskowe |
| --- | --- | --- |
| Token KSeF | `--token`, `--ksef-token` | `KSEF2_TOKEN` |
| Certyfikat testowy | `--test-cert` | `KSEF2_TEST_CERT` |
| Dane PEM XAdES | `--cert`, `--key`, opcjonalnie `--key-password` | `KSEF2_CERT`, `KSEF2_KEY`, `KSEF2_KEY_PASSWORD` |
| Archiwum PKCS#12/PFX | `--p12`, opcjonalnie `--p12-password` | `KSEF2_P12`, `KSEF2_P12_PASSWORD` |
| Zapisany stan uwierzytelnienia | `--auth-state` | `KSEF2_AUTH_STATE` |

Większość metod uwierzytelniania potrzebuje też NIP podatnika albo NIP kontekstu logowania:

```bash
export KSEF2_NIP=5261040828
```

## Uwierzytelnianie tokenem

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  invoices metadata \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --all
```

Gdy uwierzytelnianie tokenem wymaga kontekstu logowania innego niż domyślny `nip`, użyj `--context-type` albo `KSEF2_CONTEXT_TYPE`.

## Uwierzytelnianie certyfikatem testowym

```bash
uv run ksef2 --env test --nip 5261040828 --test-cert --json auth login
```

Ta metoda służy tylko przepływom w środowisku testowym.

## Dane uwierzytelniające PEM XAdES

```bash
uv run ksef2 --env production --nip "$KSEF2_NIP" \
  --cert cert.pem \
  --key private-key.pem \
  --json auth login
```

Dla zaszyfrowanego klucza prywatnego podaj `--key-password` albo ustaw `KSEF2_KEY_PASSWORD`.

## Dane uwierzytelniające PKCS#12/PFX

```bash
uv run ksef2 --env production --nip "$KSEF2_NIP" \
  --p12 signing-credentials.p12 \
  --p12-password "$KSEF2_P12_PASSWORD" \
  --json auth login
```

## Odśwież token dostępu

Wskaż globalną opcją `--auth-state` zapisany plik stanu. CLI weźmie z niego token odświeżający (`refreshToken`):

```bash
uv run ksef2 --env production --auth-state "$XDG_RUNTIME_DIR/ksef2-auth.json" --json auth refresh
```

Tej postaci używaj w skrypcie. `auth refresh` przyjmuje też `--refresh-token` oraz zmienną `KSEF2_REFRESH_TOKEN`, gdy nie masz pliku stanu. Token w wierszu polecenia widzi każdy proces na maszynie i zostaje w historii powłoki, więc w pierwszej kolejności korzystaj z pliku. Oba źródła wykluczają się wzajemnie, a sprawdzenie odbywa się przed wysłaniem żądania.

Odpowiedź jest zamaskowana w obu trybach wyniku, tak samo jak przy `auth login`. Nowy token dostępu (`accessToken`) pokazuje tylko pierwsze osiem i ostatnie cztery znaki obok `valid_until`, chyba że podasz `--show-tokens`. `--save-state FILE` pozwala skryptowi zachować odświeżoną wartość bez wypisywania jej. Przy `--auth-state` i bez `--save-state` odświeżony stan zastępuje plik źródłowy w miejscu. Kopia zapisana gdzie indziej potrzebuje tego samego pliku stanu, bo tylko on nadal niesie token odświeżający i termin jego ważności. `--save-state` bez `--auth-state` kończy się błędem, bo taki zapis zgubiłby ten termin:

```bash
uv run ksef2 --env production --auth-state "$XDG_RUNTIME_DIR/ksef2-auth.json" --json \
  auth refresh --save-state ./refreshed.json
```

`auth refresh` nie wymaga pozostałych opcji metody uwierzytelniania na poziomie głównym.

## Wznów zapisane uwierzytelnienie

`auth login` podaje terminy ważności i maskuje oba tokeny w obu trybach wyniku. Każde pole tokena zostawia tylko pierwsze osiem i ostatnie cztery znaki, obok `access_token_valid_until` i `refresh_token_valid_until`. Zamaskowane pola są domyślnie całą odpowiedzią, więc przechwycony wynik logowania nie nadaje się jako dane uwierzytelniające. `--show-tokens` wypisuje surowe tokeny na okaziciela. Traktuj tę flagę tak, jak token w wierszu polecenia: dane uwierzytelniające trafiają do historii terminala, do zapisu sesji i do każdego logu, do którego przekierujesz komendę.

Dane uwierzytelniające zachowuje `auth login --save-state`. Zapisuje stan wznowienia uwierzytelniania SDK. W tym stanie są token dostępu i token odświeżający jako **tokeny na okaziciela zapisane otwartym tekstem** oraz ich terminy ważności. CLI tworzy plik z trybem `0600` i traktuje go jak materiał uwierzytelniający. Ten tryb nie pozwala innym użytkownikom maszyny otworzyć pliku. Zawartość pozostaje zapisana otwartym tekstem, więc czytelna kopia na wolumenie współdzielonym, w kopii zapasowej, w warstwie kontenera albo w commicie jest ujawnionymi danymi uwierzytelniającymi, niezależnie od uprawnień po drodze. Trzymaj plik w miejscu prywatnym. Na współdzielonym stanowisku nadaje się `"$XDG_RUNTIME_DIR"`. Trzymaj go też poza każdym repozytorium:

```bash
uv run ksef2 --profile prod-token --json \
  auth login --save-state "$XDG_RUNTIME_DIR/ksef2-auth.json"
```

`auth resume` czyta ten plik z powrotem. Gdy zapisany token dostępu wygasł, a token odświeżający jest nadal ważny, wymienia token dostępu na nowy przez endpoint odświeżania:

```bash
uv run ksef2 --env production --json auth resume --state-file "$XDG_RUNTIME_DIR/ksef2-auth.json"
```

`auth login`, `auth resume` i `auth refresh` maskują tokeny w tekście i w JSON. Surowe wartości wypisuje `--show-tokens`. Dane, których da się użyć ponownie, zachowuje `--save-state FILE` przy logowaniu i wznowieniu. Z `--save-state` wynik zostaje zamaskowany także przy `--show-tokens` i dochodzi pole `state_file` z zapisaną ścieżką. `auth resume` zachowuje się poza tym jak `auth login`. Gdy zapisuje z powrotem do pliku, który odczytał, ten plik zachowuje tryb `0600`.

Każda inna komenda może użyć tego samego stanu. Wskaż go globalną opcją `--auth-state` albo zmienną `KSEF2_AUTH_STATE`, bez nazywania metody uwierzytelniania:

```bash
uv run ksef2 --env production --auth-state "$XDG_RUNTIME_DIR/ksef2-auth.json" --json \
  invoices metadata \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --all
```

Plik stanu zapisuje tokeny. Środowiska, w którym je wydano, w tym pliku nie ma. Środowisko nadal pochodzi z `--env` albo z profilu. Wznawiany stan potrzebuje tego samego środowiska, w którym się zalogowano. Gdy nie nazwiesz żadnego z nich, jest to teraz środowisko testowe.

`--auth-state` jest jedną z metod uwierzytelniania, więc połączenie go z `--token`, `--test-cert`, `--cert`/`--key` albo `--p12` kończy się błędem. Komenda, która wznawia stan, odświeża własny token dostępu i zapisuje stan końcowy z powrotem do tego samego pliku. Plik zostaje aktualny i zachowuje tryb `0600`. Komenda, która się nie powiedzie, zostawia plik bez zmian. Gdy zapisany token odświeżający też wygasł, komenda zatrzymuje się i prosi o nowe `auth login --save-state`.

`auth logout` kończy sesję KSeF stojącą za plikiem stanu i usuwa ten plik:

```bash
uv run ksef2 --env production --auth-state "$XDG_RUNTIME_DIR/ksef2-auth.json" --json auth logout
```

KSeF musi najpierw przyjąć zakończenie. Stan, który KSeF odrzuci albo zgłosi jako wygasły, zostaje na dysku, żebyś usunął go samodzielnie. Komenda dotyczy tej jednej sesji uwierzytelniania, czyli tej, której zakończenia żąda od KSeF. Nie mówi nic o innych tokenach ani sesjach tego samego podmiotu.

## Opcje cyklicznego sprawdzania

Komendy uwierzytelniania sprawdzają status, dopóki KSeF przetwarza uwierzytelnianie. Opcje główne nadpisują ustawienia profilu albo wartości domyślne:

```bash
uv run ksef2 --profile prod-token \
  --auth-poll-interval 2 \
  --auth-timeout 180 \
  --json auth login
```

`--auth-timeout` to łączna liczba sekund oczekiwania na zakończenie uwierzytelniania. `--auth-poll-interval` to odstęp między sprawdzeniami. Bez nich o obu wartościach decydują `poll_interval` i `max_poll_attempts` profilu. Profil bez tych pól czeka domyślne `60` sekund, ze sprawdzeniem co `1` sekundę.

## Kolejność

Gdy ustawienie jest dostępne w kilku miejscach, CLI rozstrzyga je w tej kolejności:

1. Opcja CLI.
2. Zmienna środowiskowa.
3. Wybrany profil.
4. Wbudowana wartość domyślna. Dla środowiska jest to `test`.

`--no-config` pomija profile na czas jednego wywołania. Koliduje z `--profile` i kończy się wtedy kodem `2`, bez cichego odrzucenia profilu.
