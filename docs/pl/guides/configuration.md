---
title: Konfiguracja
description: Profile, zmienne środowiskowe, tryby wyniku i lokalne pliki konfiguracji w KSeF2 CLI.
---

KSeF2 CLI może działać bez lokalnego pliku konfiguracji. W CI i na maszynach współdzielonych zostaw CLI bez tego pliku. Na komputerze, na którym rozwijasz integrację, utwórz nazwane profile, żeby codzienne komendy nie powtarzały `--env`, `--nip` i ścieżek uwierzytelniania. SDK czyta ten sam plik profilu przez `client.authentication.with_profile()`.

Bez profilu i bez `--env` środowisko to `test`. Profil niesie środowisko, gdy go nie nazwiesz, a `--env` ma pierwszeństwo przed profilem. Praca produkcyjna potrzebuje `--env production` albo profilu z `environment = "production"`.

## Pokaż ścieżkę aktywnej konfiguracji

```bash
uv run ksef2 config path
```

Domyślnie CLI używa:

```text
~/.config/ksef2/config.toml
```

To ten sam plik, który czyta SDK, więc `ksef2 profile create` i `client.authentication.with_profile()` korzystają z jednej konfiguracji. Konfiguracja zostawiona pod starszą ścieżką `~/.config/ksef2-cli/config.toml` jest nadal wczytywana, dopóki nie istnieje `~/.config/ksef2/config.toml`, i CLI nadal do niej zapisuje, dopóki sam jej nie przeniesiesz.

Ścieżkę nadpisujesz przez `--config` albo `KSEF2_CONFIG`:

```bash
uv run ksef2 --config ./local.ksef2.toml config path
```

## Utwórz profil

```bash
uv run ksef2 profile create demo-client \
  --env test \
  --nip 5261040828 \
  --test-cert
```

`profile create` domyślnie wybiera nowy profil. `--no-activate` tylko go zapisuje.

Profil tokena trzyma nazwę zmiennej środowiskowej. Wartość tokena zostaje poza plikiem:

```bash
uv run ksef2 profile create prod-client \
  --env production \
  --nip 5261040828 \
  --token-env KSEF2_PROD_TOKEN
```

Profil certyfikatu trzyma ścieżki plików i opcjonalne nazwy zmiennych z hasłem:

```bash
uv run ksef2 profile create demo-pem \
  --env demo \
  --nip 5261040828 \
  --cert company.pem \
  --key company.key \
  --key-password-env KSEF2_KEY_PASSWORD

uv run ksef2 profile create prod-p12 \
  --env production \
  --nip 5261040828 \
  --p12 signing-credentials.p12 \
  --p12-password-env KSEF2_P12_PASSWORD
```

Gdy domyślne oczekiwanie na uwierzytelnienie jest za krótkie, zapisz dłuższe w samym profilu. `--poll-interval` to odstęp między sprawdzeniami statusu, a `--max-poll-attempts` to liczba sprawdzeń. Profil poniżej czeka więc `2.0 * 90 = 180` sekund:

```bash
uv run ksef2 profile create slow-prod \
  --env production \
  --nip 5261040828 \
  --token-env KSEF2_PROD_TOKEN \
  --poll-interval 2.0 \
  --max-poll-attempts 90
```

Oba ustawienia zostają nieustawione, gdy je pominiesz. SDK czyta je tak samo, więc `client.authentication.with_profile()` sprawdza status do tego samego terminu. Oba pola pojawiają się w `profile show`, gdy profil je niesie.

## Wybierz profil

```bash
uv run ksef2 profile use demo-client
uv run ksef2 profile current
uv run ksef2 profile list
```

Inny profil na jedną komendę:

```bash
uv run ksef2 --profile prod-client --json \
  invoices metadata \
  --date-from 2026-01-01T00:00:00Z
```

Albo na bieżącą powłokę:

```bash
export KSEF2_PROFILE=demo-client
```

Kolejność wyboru:

1. `--profile NAME` w bieżącej komendzie.
2. `KSEF2_PROFILE` w środowisku.
3. `active_profile` zapisany w pliku konfiguracji.

`KSEF2_PROFILE` wpływa tylko na ustawienia bieżącego uruchomienia. Zapisany aktywny profil zmieniasz przez `profile use NAME`.

## Usuń profil

```bash
uv run ksef2 profile delete demo-client
```

Komenda pyta o potwierdzenie. Usunięcie wybranego profilu zostawia sytuację bez aktywnego profilu. Wynik JSON nie ma pytania, na które dałoby się odpowiedzieć, więc potrzebuje `--yes`:

```bash
uv run ksef2 --json profile delete demo-client --yes
```

## Podejrzyj lokalną konfigurację

```bash
uv run ksef2 config show
uv run ksef2 profile show demo-client
```

Plik konfiguracji trzyma nazwy profili, środowiska, NIP-y, ścieżki plików z danymi uwierzytelniającymi, ustawienia cyklicznego sprawdzania oraz nazwy zmiennych środowiskowych z sekretami. Nie powinien zawierać wartości tokenów ani haseł.

Przykładowa konfiguracja:

```toml
active_profile = "demo-client"

[profiles.demo-client]
environment = "test"
nip = "5261040828"

[profiles.demo-client.auth]
type = "test_certificate"

[profiles.prod-client]
environment = "production"
nip = "5261040828"
poll_interval = 2.0
max_poll_attempts = 90

[profiles.prod-client.auth]
type = "token"
token_env = "KSEF2_PROD_TOKEN"
context_type = "nip"

[profiles.demo-pem]
environment = "demo"
nip = "5261040828"

[profiles.demo-pem.auth]
type = "xades_pem"
cert = "company.pem"
key = "company.key"
key_password_env = "KSEF2_KEY_PASSWORD"

[profiles.prod-p12]
environment = "production"
nip = "5261040828"

[profiles.prod-p12.auth]
type = "xades_p12"
p12 = "signing-credentials.p12"
p12_password_env = "KSEF2_P12_PASSWORD"
```

Nazwy profili, wartości środowiska, napisy typu uwierzytelniania i nazwy pól pochodzą z modeli profilu SDK. CLI nie trzyma ich osobnej kopii. `poll_interval` to odstęp między sprawdzeniami statusu, a `max_poll_attempts` to liczba sprawdzeń, więc uwierzytelnianie profilem `prod-client` czeka `2.0 * 90 = 180` sekund.

Starsze wydania CLI zapisywały płaskie `auth_timeout = 180.0` sekund. Ten klucz nie należy do schematu SDK i jest ignorowany. Przenieś go do `max_poll_attempts = round(auth_timeout / poll_interval)`, żeby zachować to samo oczekiwanie.

## Pomiń lokalną konfigurację w jednym wywołaniu

```bash
uv run ksef2 --no-config --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices metadata --role seller --date-from 2026-01-01T00:00:00Z
```

`--no-config` razem z `--profile` kończy się kodem `2`. Tak samo kończy się `--profile` o nazwie, której nie ma w pliku konfiguracji.

## Tryby wyniku

Domyślny tryb wyniku to zwykły tekst dla człowieka:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" \
  invoices metadata --date-from 2026-01-01T00:00:00Z
```

W skryptach użyj `--json` albo `--output json`:

```bash
uv run ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  invoices metadata --date-from 2026-01-01T00:00:00Z
```

### Dokąd trafia wynik

Sukces jest zapisywany na standardowe wyjście: postać tekstowa albo jeden dokument JSON w trybie `--json`. Nic innego tam nie trafia, więc `ksef2 --json ... > out.json` przechwytuje dokładnie jedną wartość.

Błędy komendy idą na standardowe wyjście błędów i zostawiają standardowe wyjście puste. Sprawdź kod wyjścia, zanim zaczniesz parsować standardowe wyjście. Dokończone `invoices send` z odrzuconymi pozycjami zapisuje wynik na standardowe wyjście i kończy się kodem 1. Przy błędach komendy tryb tekstowy wypisuje wiersze dla człowieka, a `--json` jeden obiekt:

```bash
uv run ksef2 --json auth login --token 2>error.json
```

```json
{
  "error": {
    "type": "RemoteServiceError",
    "title": "KSeF rejected the request",
    "message": "KSeF rejected the request.",
    "details": [],
    "hints": [],
    "exit_code": 1,
    "ksef": {
      "status_code": 400,
      "exception_code": 21405,
      "message": "Validation error",
      "ksef_code": 21405,
      "trace_id": "0f6c…"
    }
  }
}
```

| Klucz | Zawartość |
| --- | --- |
| `type` | Klasa błędu CLI, na przykład `RemoteServiceError`, `AuthenticationConfigError`, `ConfigError` albo `FileCliError`. `UsageError`, gdy odrzucono sam wiersz polecenia. |
| `title` | Krótki opis, który CLI wybrało dla tej porażki. |
| `message` | Jedno zdanie o porażce, czytelne dla człowieka. |
| `details`, `hints`, `exit_code` | Zawsze obecne. Obie listy są puste, gdy CLI nie ma nic do dodania. |
| `ksef` | Obecne, gdy KSeF odpowiedział. Niesie `status_code`, `exception_code` i `message` tej usługi oraz `ksef_code`, `trace_id`, `details` albo `response`, gdy CLI je ma. Przy zgłoszeniu incydentu podaj `trace_id`. |
| `report_url` | Obecne przy błędzie, który CLI traktuje jak usterkę własną. |
| `traceback` | Obecne z `--verbose` i tylko przy takim błędzie. |

Każdy sekret, który CLI rozpoznało w wierszu polecenia albo w swoich zmiennych środowiskowych z sekretami, jest przed zakodowaniem wyniku zastępowany przez `<redacted>`.

### Kody wyjścia

| Kod wyjścia | Znaczenie |
| --- | --- |
| `0` | Sukces. |
| `1` | Błąd wykonania: KSeF odrzucił żądanie albo przekroczył czas, brakuje danych uwierzytelniających albo są sprzeczne, operacja na pliku się nie powiodła. |
| `2` | Błąd użycia: nieznana opcja albo komenda, brakujący argument, wartość, która nie przechodzi sprawdzenia, na przykład NIP ze złą sumą kontrolną, albo `--profile`, którego nie ma. |
| `130` | Przerwanie przez Ctrl-C. |

Wysyłka przez `invoices send` to osobny przypadek: komenda wypisuje wynik każdego pliku, a potem kończy się kodem `1`, gdy którykolwiek plik się nie powiódł. Przeczytaj pozycje, zanim uznasz, że nic nie zostało wysłane. `130` też niczego nie cofa. Zobacz [Przerwana wysyłka nie oznacza, że faktury nie przyjęto](invoices.md#przerwana-wysyłka-nie-oznacza-że-faktury-nie-przyjęto).

## Sekrety w plikach, które zapisuje CLI

Każdy plik kontynuacji, który zapisuje CLI, jest materiałem uwierzytelniającym. Każdy powstaje z trybem `0600`:

| Plik | Co zawiera |
| --- | --- |
| `auth login --save-state` | Token dostępu i token odświeżający na okaziciela, otwartym tekstem. |
| `online open --state-file`, `online send --save-state` | Klucz AES sesji interaktywnej i IV. |
| `--receipt`, `--receipt-dir` z wysyłki w sesji interaktywnej | Ten sam stan sesji, bo plik `--receipt` sesji interaktywnej jest stanem sesji do wznowienia. |
| `--handle-file` przy eksporcie | Klucz odszyfrowania eksportu i IV. |
| `batch prepare --out` | Klucz sesji wsadowej, obok zaszyfrowanych treści faktur. |
| `batch submit --state-file` | Klucz sesji wsadowej i skrót przygotowanej paczki. |

`0600` mówi tylko tyle, że inni użytkownicy tej maszyny nie otworzą pliku. Bajty zostają zapisane otwartym tekstem i są czytelne dla właściciela pliku oraz dla wszystkiego, co działa jako ten użytkownik. Tryb nie przeżywa kopii zachowującej `chmod`, archiwum tar, warstwy Dockera ani commitu. Trzymaj te pliki poza repozytorium, wpisz je do `.gitignore`, na maszynie współdzielonej preferuj katalog prywatny taki jak `$XDG_RUNTIME_DIR` i usuń je, gdy przepływ się skończy. `auth logout` usuwa plik stanu uwierzytelnienia, na który został wskazany, gdy KSeF potwierdzi zakończenie sesji.

## Częste zmienne środowiskowe

| Zmienna | Do czego służy |
| --- | --- |
| `KSEF2_CONFIG` | Ścieżka lokalnego pliku konfiguracji |
| `KSEF2_PROFILE` | Nazwa profilu dla tej powłoki albo sesji |
| `KSEF2_NIP` | Nadpisanie NIP podatnika albo NIP kontekstu logowania |
| `KSEF2_TOKEN` | Nadpisanie sekretu uwierzytelniania tokenem KSeF |
| `KSEF2_CONTEXT_TYPE` | Nadpisanie typu kontekstu logowania przy uwierzytelnianiu tokenem |
| `KSEF2_AUTH_STATE` | Zapisany stan uwierzytelnienia do wznowienia, bez ponownego logowania |
| `KSEF2_REFRESH_TOKEN` | Token odświeżający dla `auth refresh`, poza wierszem polecenia |
| `KSEF2_TEST_CERT` | Włącza uwierzytelnianie certyfikatem testowym generowanym przez SDK |
| `KSEF2_CERT` | Nadpisanie ścieżki certyfikatu PEM |
| `KSEF2_KEY` | Nadpisanie ścieżki klucza prywatnego PEM |
| `KSEF2_KEY_PASSWORD` | Nadpisanie hasła klucza prywatnego PEM |
| `KSEF2_P12` | Nadpisanie ścieżki archiwum PKCS#12/PFX |
| `KSEF2_P12_PASSWORD` | Nadpisanie hasła PKCS#12/PFX |

Nazwy `KSEF2_*` powyżej to te, które CLI czyta samodzielnie. Profil nazywa własne zmienne z sekretami, na przykład `auth.token_env`, i te nazwy wybierasz sam.
