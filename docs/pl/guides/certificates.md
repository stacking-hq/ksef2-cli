---
title: Certyfikaty
description: Sprawdź limity certyfikatów KSeF, złóż wniosek z CSR, wyszukaj i pobierz wydane certyfikaty oraz unieważnij je w KSeF2 CLI.
---

Grupa `certificates` obejmuje pracę z certyfikatami KSeF po stronie MCU: limity wniosków, dane podmiotu, których KSeF oczekuje we wniosku o certyfikat, złożenie wniosku, wyszukiwanie, pobieranie i unieważnienie. CLI wysyła żądanie i czyta odpowiedź. Nigdy nie generuje klucza prywatnego i nigdy o niego nie prosi, więc generowanie i przechowywanie klucza zostaje w twoich własnych narzędziach do certyfikatów.

Każda komenda w tej grupie potrzebuje uwierzytelnionego kontekstu logowania. Wniosek o certyfikat potrzebuje kontekstu, któremu KSeF pozwala o certyfikaty prosić.

## Najpierw sprawdź limit

```bash
uv run ksef2 --profile prod-xades --json certificates limits
```

```json
{
  "can_request": true,
  "enrollment_limit": 10,
  "enrollment_remaining": 9,
  "certificate_limit": 10,
  "certificate_remaining": 8
}
```

`enrollment_remaining` liczy wnioski, które jeszcze możesz złożyć. `certificate_remaining` liczy certyfikaty, które jeszcze możesz posiadać. `can_request` to własne tak albo nie po stronie KSeF. Wnioski, które przychodzą bez pozostałego limitu, są odrzucane, więc przeczytaj te liczby przed uruchomieniem automatycznym. W trybie tekstowym `can_request` wypisuje się jako `yes` albo `no`.

`limits get subject` podaje powiązane limity z grupy `limits`. Przeczytaj oba, zanim zmienisz proces certyfikatów.

## Odczytaj dane podmiotu do CSR

```bash
uv run ksef2 --profile prod-xades --json certificates enrollment-data
```

```json
{
  "common_name": "Example subject",
  "iso_country_code": "PL",
  "organization_identifier": "VATPL-5261040828"
}
```

Odpowiedź niesie też `name`, `surname`, `serial_number`, `unique_identifier` i `organization_name`, gdy KSeF ma je dla tego podmiotu. Użyj tych wartości jako podmiotu wniosku, który zbudujesz w następnym kroku. Nie wymyślaj własnej pisowni tych pól.

## Zbuduj klucz i wniosek

KSeF chce wniosku PKCS#10, zakodowanego w DER, a potem w Base64, w jednym pliku. CLI czyta tekst pliku i wstawia go do treści żądania tak, jak stoi, więc trzymaj go w jednym wierszu.

```bash
openssl ecparam -genkey -name prime256v1 -noout -out billing.key

openssl req -new -key billing.key \
  -subj "/CN=Example subject" \
  -outform DER | base64 | tr -d '\n' > billing.csr
```

`billing.key` to klucz prywatny. Chroń go albo wygeneruj w module sprzętowym albo w magazynie kluczy i wyeksportuj tylko wniosek. KSeF nie potrzebuje tego klucza w żadnym momencie.

## Złóż wniosek

```bash
uv run ksef2 --profile prod-xades --json \
  certificates enroll \
  --name billing-service \
  --csr-file billing.csr
```

```json
{
  "reference_number": "20260625-CERT-...",
  "timestamp": "2026-06-25T10:00:00Z"
}
```

Ta odpowiedź znaczy, że KSeF przyjął wniosek. Nie znaczy, że cokolwiek wydał. Zachowaj `reference_number`. `--type` wybiera `authentication` (domyślnie) albo `offline`, a `--valid-from` przyjmuje datę z czasem w ISO 8601, gdy certyfikat ma zacząć obowiązywać później niż teraz.

Dodaj `--wait`, żeby komenda trwała, aż KSeF skończy. Wynikiem staje się status wniosku:

```bash
uv run ksef2 --profile prod-xades --json \
  certificates enroll \
  --name billing-service \
  --csr-file billing.csr \
  --wait
```

```json
{
  "request_date": "2026-06-25T10:00:00Z",
  "status_code": 200,
  "status_description": "Completed",
  "status_details": null,
  "certificate_serial_number": "0123456789ABCDEF"
}
```

`status_code` 100 znaczy, że KSeF nadal pracuje, a 200, że certyfikat istnieje. Każdy inny kod kończy komendę błędem i podaje przy tym opis oraz szczegóły statusu. Odrzucony wniosek widać w kodzie wyjścia.

Sprawdzanie statusu wniosku czeka domyślnie 60 sekund, ze sprawdzeniem raz na sekundę. `max_poll_attempts` i `poll_interval` profilu ustawiają obie liczby, a `--auth-poll-interval` nadpisuje tylko odstęp. W odróżnieniu od `auth login` to oczekiwanie ignoruje `--auth-timeout`.

## Sprawdź wniosek później

```bash
uv run ksef2 --profile prod-xades --json \
  certificates enrollment-status --reference "$ENROLLMENT_REFERENCE"
```

Użyj tego po komendzie uruchomionej bez `--wait` albo po uruchomieniu, które przekroczyło czas, gdy KSeF nadal decydował. Komenda czyta ten sam obiekt statusu i niczego nie składa ponownie.

## Znajdź certyfikaty

```bash
uv run ksef2 --profile prod-xades certificates list \
  --status active \
  --page-size 50
```

Filtry: `--serial-number`, `--name`, `--type` (`authentication` albo `offline`), `--status` (`active`, `blocked`, `revoked`, `expired`) oraz `--expires-after` z datą i czasem w ISO 8601. Tak pytasz o to, co niedługo się skończy. `--page-size` przyjmuje wartości od 10 do 100, `--page-offset` pomija rekordy, a `--all` przechodzi wszystkie strony.

`--page-size` ustawia liczbę pozycji na żądanie API, także z `--all`. `--all` wymaga, żeby `--page-offset` było równe 0, czyli swojej wartości domyślnej, i odrzuca przesunięcie inne niż zero.

Wynik tekstowy wypisuje jeden blok `key: value` na certyfikat, z polami `serial_number`, `name`, `common_name`, `type`, `status`, `subject_identifier`, `valid_from`, `valid_to` i `request_date`. `last_use_date` pojawia się tylko przy certyfikacie, który KSeF widział w użyciu, a `subject_identifier` wypisuje się jako jeden zwarty obiekt JSON. Użyj `--json`, gdy chcesz numery seryjne w potoku.

Numery seryjne mają dokładnie 16 znaków szesnastkowych, wielkimi literami. CLI sprawdza postać numeru, zanim cokolwiek wyśle. Numer małymi literami albo obcięty kończy się komunikatem walidacji.

## Pobierz certyfikat

Numery seryjne są argumentami pozycyjnymi. Jedno wywołanie przyjmuje ich kilka:

```bash
uv run ksef2 --profile prod-xades --json \
  certificates retrieve 0123456789ABCDEF ABCDEF1234567890
```

`--out-dir` zapisuje każdy certyfikat także do pliku. CLI tworzy katalog i zapisuje jeden plik `<serial_number>.b64` na certyfikat. Plik zawiera Base64 certyfikatu X.509 zakodowanego w DER, tak jak zwrócił go KSeF:

```bash
uv run ksef2 --profile prod-xades \
  certificates retrieve 0123456789ABCDEF \
  --out-dir issued
```

Ten plik nie jest PEM, więc zdekoduj go, zanim podasz certyfikat narzędziu, które PEM oczekuje, i sparuj go z kluczem prywatnym, który wygenerowałeś sam:

```bash
base64 --decode < issued/0123456789ABCDEF.b64 \
  | openssl x509 -inform DER -out issued/0123456789ABCDEF.pem

openssl pkcs12 -export -out issued/billing-service.p12 \
  -inkey billing.key -in issued/0123456789ABCDEF.pem
```

`openssl pkcs12 -export` pyta o hasło eksportu, a `-passout` przyjmuje je w wierszu polecenia, gdy nie chcesz pytania. Powstałe archiwum przyjmuje główna opcja `--p12` i ustawienia PKCS#12 profilu. Zmienne środowiskowe z hasłem, które do tego należą, opisuje [Uwierzytelnianie](authentication.md).

Gdy KSeF odpowie treścią, której zainstalowane SDK nie umie odczytać, komenda kończy się kodem 1 z komunikatem `KSeF response could not be parsed`, jednym wierszem na odrzucone pole, i ze wskazówkami, żeby zaktualizować SDK oraz uruchomić ponownie z `--verbose`. Wtedy w wyniku jest też ślad stosu SDK. Przy SDK 1.0.0 poprawne wydane certyfikaty mogły wywołać ten błąd, bo SDK dekodowało binarny DER jako UTF-8. CLI wymaga SDK 1.1 albo nowszego, które naprawia [ksef2#323](https://github.com/stacking-hq/ksef2/issues/323) i zachowuje tekst certyfikatu w Base64.

## Unieważnij

```bash
uv run ksef2 --profile prod-xades --json \
  certificates revoke \
  --serial-number 0123456789ABCDEF \
  --reason key_compromise
```

```json
{
  "serial_number": "0123456789ABCDEF",
  "reason": "key_compromise",
  "revoked": true
}
```

`--reason` jest opcjonalne i przyjmuje `unspecified`, `superseded` albo `key_compromise`. Podaj `key_compromise`, gdy klucz prywatny mógł wyciec. Unieważnienie nie sprząta klucza, więc przestań go też używać.

## Powiązane strony

- [Uwierzytelnianie](authentication.md)
- [Limity](limits.md)
- [Uprawnienia](permissions.md)
- [Opis komend](../reference/commands.md)
