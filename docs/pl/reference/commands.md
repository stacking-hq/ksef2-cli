---
title: Komendy
description: Grupy komend i komendy podrzędne udostępniane przez KSeF2 CLI.
---

Angielski opis komend zapisuje `scripts/generate_command_reference.py`, który czyta aplikację Typer. Uruchom ten skrypt po dodaniu, usunięciu albo zmianie komendy lub opcji. Test kończy się błędem, gdy plik `docs/reference/commands.md` się zestarzeje.

Opcje globalne muszą stać przed grupą komend:

```bash
ksef2 [GLOBAL OPTIONS] COMMAND [ARGS]...
```

## Opcje globalne

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--version` | - | false | - | Pokaż wersje CLI i SDK. |
| `--env`, `-e` | [production\|demo\|test] | - | - | Środowisko KSeF. Domyślnie wybrany profil albo środowisko testowe. |
| `--output`, `-o` | [text\|json] | - | - | Tryb wyniku. Domyślnie text. |
| `--json` | - | false | - | Skrót --output json. |
| `--verbose`, `-v` | - | false | - | Pokaż ślad stosu przy błędach CLI. |
| `--config` | FILE | - | KSEF2_CONFIG | Lokalny plik konfiguracji. Domyślnie ~/.config/ksef2/config.toml. |
| `--no-config` | - | false | - | Pomiń profile lokalnej konfiguracji. |
| `--profile` | TEXT | - | - | Użyj nazwanego profilu w tym wywołaniu. |
| `--nip` | TEXT | - | KSEF2_NIP | NIP podatnika albo NIP kontekstu logowania. |
| `--token`, `--ksef-token` | TEXT | - | KSEF2_TOKEN | Token KSeF do uwierzytelniania tokenem. |
| `--context-type` | [nip\|internal_id\|nip_vat_ue\|peppol_id] | - | KSEF2_CONTEXT_TYPE | Typ kontekstu logowania przy uwierzytelnianiu tokenem. |
| `--auth-state` | FILE | - | KSEF2_AUTH_STATE | Użyj stanu uwierzytelnienia zapisanego przez --save-state, bez ponownego uwierzytelniania. |
| `--test-cert` | - | false | KSEF2_TEST_CERT | Uwierzytelnij się certyfikatem testowym generowanym przez SDK. |
| `--cert` | FILE | - | KSEF2_CERT | Certyfikat PEM do uwierzytelniania XAdES. |
| `--key` | FILE | - | KSEF2_KEY | Klucz prywatny PEM do uwierzytelniania XAdES. |
| `--key-password` | TEXT | - | KSEF2_KEY_PASSWORD | Hasło do zaszyfrowanego klucza prywatnego PEM. |
| `--p12` | FILE | - | KSEF2_P12 | Archiwum PKCS#12/PFX do uwierzytelniania XAdES. |
| `--p12-password` | TEXT | - | KSEF2_P12_PASSWORD | Hasło do archiwum PKCS#12/PFX. |
| `--auth-poll-interval` | FLOAT RANGE | - | - | Odstęp sprawdzania statusu uwierzytelniania. |
| `--auth-timeout` | FLOAT RANGE | - | - | Sekundy oczekiwania na zakończenie uwierzytelniania. |

## Grupy komend

| Grupa | Do czego służy |
| --- | --- |
| `auth` | Uwierzytelnianie, wznowienie i odświeżanie tokena dostępu KSeF. |
| `batch` | Wysyłka i podgląd sesji wsadowych faktur. |
| `certificates` | Zarządzanie certyfikatami MCU. |
| `collective` | Generowanie i wyszukiwanie identyfikatorów zbiorczych faktur. |
| `config` | Podgląd i tworzenie lokalnego pliku konfiguracji CLI. |
| `encryption` | Odczyt publicznych certyfikatów szyfrowania KSeF. |
| `fa3` | Lokalne budowanie, podgląd i generowanie widoku faktur FA(3), bez dostępu do KSeF. |
| `invoices` | Wysyłka, potwierdzanie, zapytania, pobieranie i eksport faktur. |
| `limits` | Odczyt obowiązujących limitów KSeF i zarządzanie nimi. |
| `online` | Otwieranie, wznawianie i prowadzenie sesji interaktywnych faktur. |
| `peppol` | Zapytania o publicznych dostawców PEPPOL. |
| `permissions` | Nadawanie, wyszukiwanie i cofanie uprawnień. |
| `profile` | Tworzenie, podgląd i wybór lokalnych profili CLI. |
| `sessions` | Podgląd sesji uwierzytelniania i historycznych sesji faktur. |
| `testdata` | Zarządzanie danymi testowymi środowiska testowego. |
| `tokens` | Zarządzanie tokenami KSeF. |

## `auth`

### `auth login`

Uwierzytelnij się i pokaż zamaskowane tokeny. --save-state zachowuje dane uwierzytelniające.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--show-tokens` | - | false | - | Wypisz surowy token dostępu i token odświeżający. To tokeny na okaziciela. Trzymaj je poza logami. |
| `--save-state` | FILE | - | - | Zapisz stan uwierzytelnienia do wznowienia w tym pliku. Trzyma tokeny na okaziciela otwartym tekstem. |

### `auth logout`

Zakończ zapisaną sesję i usuń jej plik stanu uwierzytelnienia.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--state-file`, `--auth-state` | FILE | - | - | Zapisany stan uwierzytelnienia do wznowienia. Domyślnie globalne --auth-state. |

### `auth refresh`

Odśwież token dostępu z zapisanego stanu albo z podanego tokena odświeżającego. Wynik zostaje zamaskowany.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--refresh-token` | TEXT | - | KSEF2_REFRESH_TOKEN | Token odświeżający. W pierwszej kolejności użyj --auth-state, żeby token nie trafił do argumentów procesu. |
| `--auth-state`, `--state-file` | FILE | - | - | Zapisany stan uwierzytelnienia do wznowienia. Domyślnie globalne --auth-state. |
| `--save-state` | FILE | - | - | Zapisz stan uwierzytelnienia do wznowienia w tym pliku. Trzyma tokeny na okaziciela otwartym tekstem. |
| `--show-tokens` | - | false | - | Wypisz surowy token dostępu i token odświeżający. To tokeny na okaziciela. Trzymaj je poza logami. |

### `auth resume`

Użyj zapisanego stanu uwierzytelnienia i odśwież token dostępu, gdy wygasł.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--state-file`, `--auth-state` | FILE | - | - | Zapisany stan uwierzytelnienia do wznowienia. Domyślnie globalne --auth-state. |
| `--show-tokens` | - | false | - | Wypisz surowy token dostępu i token odświeżający. To tokeny na okaziciela. Trzymaj je poza logami. |
| `--save-state` | FILE | - | - | Zapisz wznowiony stan, łącznie z odświeżonym tokenem dostępu, jeśli został odświeżony. |

## `batch`

### `batch list`

Wypisz faktury wysłane w sesji wsadowej.

Czytaj po numerze referencyjnym albo otwórz ponownie stan zapisany przez batch submit.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--reference` | TEXT | - | - | Numer referencyjny sesji wsadowej. Użyj go w miejsce --state-file. |
| `--state-file` | FILE | - | - | Stan sesji wsadowej zapisany przez batch submit --state-file. |
| `--page-size` | INTEGER RANGE | 10 | - | - |
| `--continuation-token` | TEXT | - | - | - |
| `--failed` | - | false | - | Wypisz tylko odrzucone faktury. |

### `batch prepare`

Użycie: `ksef2 batch prepare [OPTIONS] INVOICE_PATHS...`

Zbuduj i zaszyfruj części paczki, a potem zapisz je do późniejszego submit.

Części zależą od klucza szyfrowania KSeF. Od sesji nie zależą, więc przygotowanie przed wysłaniem pozwala ponowić odrzucone przesłanie bez ponownego pakowania i szyfrowania faktur. Artefakt trzyma klucz sesji i treści faktur. Chroń go tak, jak plik z danymi uwierzytelniającymi.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `INVOICE_PATHS...` | - | required | - | - |
| `--out`, `-o` | DIRECTORY | required | - | Katalog artefaktu. |
| `--form` | [FA2\|FA3\|FA_RR1\|PEF3\|PEF_KOR3] | FA3 | - | Struktura: FA2, FA3, FA_RR1, PEF3, PEF_KOR3. |
| `--offline` | - | false | - | Zadeklaruj tryb offline. |
| `--max-part-size` | INTEGER RANGE | - | - | Maksymalny rozmiar zaszyfrowanej części paczki w bajtach. |

### `batch status`

Pobierz status sesji wsadowej albo na niego poczekaj.

Czytaj po numerze referencyjnym albo otwórz ponownie stan zapisany przez batch submit.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--reference` | TEXT | - | - | Numer referencyjny sesji wsadowej. Użyj go w miejsce --state-file. |
| `--state-file` | FILE | - | - | Stan sesji wsadowej zapisany przez batch submit --state-file. |
| `--wait` | - | false | - | Czekaj na zakończenie. |
| `--timeout` | FLOAT RANGE | 120.0 | - | - |
| `--poll-interval` | FLOAT RANGE | 2.0 | - | - |

### `batch submit`

Użycie: `ksef2 batch submit [OPTIONS] [INVOICE_PATHS]...`

Przygotuj sesję wsadową, prześlij części, zamknij ją i opcjonalnie poczekaj.

Podaj pliki faktur, żeby przygotować je za jednym razem, albo --prepared, żeby przesłać paczkę zapisaną przez batch prepare. To droga ponowienia po nieudanym przesłaniu.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `[INVOICE_PATHS]...` | - | - | - | Pliki XML faktur do przygotowania i wysłania. Pomiń je przy --prepared. |
| `--prepared` | DIRECTORY | - | - | Katalog artefaktu zapisany przez batch prepare. Jego części są przesyłane tak, jak stoją, a --form, --offline i --max-part-size nie mają tu zastosowania. |
| `--state-file` | FILE | - | - | - |
| `--form` | [FA2\|FA3\|FA_RR1\|PEF3\|PEF_KOR3] | FA3 | - | Struktura: FA2, FA3, FA_RR1, PEF3, PEF_KOR3. |
| `--offline` | - | false | - | Zadeklaruj tryb offline. |
| `--max-part-size` | INTEGER RANGE | - | - | Maksymalny rozmiar zaszyfrowanej części paczki w bajtach. |
| `--wait` | - | false | - | Czekaj na zakończenie przetwarzania sesji wsadowej. |
| `--timeout` | FLOAT RANGE | 120.0 | - | - |
| `--poll-interval` | FLOAT RANGE | 2.0 | - | - |

### `batch upload`

Wyślij zapisane części ponownie do sesji wsadowej, której przesłanie się nie powiodło.

Plik stanu niesie numer referencyjny sesji, klucze i instrukcje przesłania. Artefakt niesie dokładnie te części, których oczekuje KSeF. Odzyskanie nie potrzebuje nowych faktur ani nowej paczki.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--prepared` | DIRECTORY | required | - | Katalog artefaktu zapisany przez batch prepare. |
| `--state-file` | FILE | required | - | Stan sesji wsadowej zostawiony przez nieudane submit albo zapisany przez dowolną komendę, która podaje stan sesji. |
| `--wait` | - | false | - | Czekaj na zakończenie przetwarzania sesji wsadowej. |
| `--timeout` | FLOAT RANGE | 120.0 | - | - |
| `--poll-interval` | FLOAT RANGE | 2.0 | - | - |

### `batch upo`

Pobierz stronę zbiorczego UPO sesji wsadowej.

KSeF odpowiada na to żądanie numerem sesji. Działa zarówno --reference, jak i --state-file, i sesja nie jest otwierana ponownie.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--upo-reference` | TEXT | required | - | - |
| `--out`, `-o` | FILE | required | - | - |
| `--reference` | TEXT | - | - | Numer referencyjny sesji wsadowej. Użyj go w miejsce --state-file. |
| `--state-file` | FILE | - | - | Stan sesji wsadowej. Tutaj używany jest tylko jego numer referencyjny. |

## `certificates`

### `certificates enroll`

Złóż wniosek o certyfikat z plikiem CSR zakodowanym w Base64.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--name` | TEXT | required | - | Nazwa certyfikatu. |
| `--csr-file` | FILE | required | - | - |
| `--type` | [authentication\|offline] | authentication | - | authentication albo offline. |
| `--valid-from` | TEXT | - | - | Data i czas w ISO. |
| `--wait` | - | false | - | Czekaj, aż wniosek o certyfikat się zakończy. |

### `certificates enrollment-data`

Użycie: `ksef2 certificates enrollment-data`

Odczytaj dane podmiotu potrzebne do wygenerowania CSR wniosku o certyfikat.

### `certificates enrollment-status`

Pobierz status wniosku o certyfikat.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--reference` | TEXT | required | - | - |

### `certificates limits`

Użycie: `ksef2 certificates limits`

Odczytaj limity wniosków o certyfikat i limity wydanych certyfikatów.

### `certificates list`

Wyszukaj certyfikaty.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--serial-number` | TEXT | - | - | - |
| `--name` | TEXT | - | - | - |
| `--type` | [authentication\|offline] | - | - | - |
| `--status` | [active\|blocked\|revoked\|expired] | - | - | - |
| `--expires-after` | TEXT | - | - | Data i czas w ISO. |
| `--page-size` | INTEGER RANGE | 10 | - | Liczba pozycji na żądanie API, także z --all. |
| `--page-offset` | INTEGER RANGE | 0 | - | Przesunięcie jednej strony. Z --all musi wynosić 0. |
| `--all` | - | false | - | Pobierz wszystkie strony. |

### `certificates retrieve`

Użycie: `ksef2 certificates retrieve [OPTIONS] SERIAL_NUMBERS...`

Pobierz wydane certyfikaty po numerze seryjnym.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `SERIAL_NUMBERS...` | - | required | - | Numer albo numery seryjne certyfikatu. |
| `--out-dir` | DIRECTORY | - | - | Zapisz certyfikaty jako pliki tekstowe w postaci zbliżonej do PEM. |

### `certificates revoke`

Unieważnij certyfikat.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--serial-number` | TEXT | required | - | - |
| `--reason` | [unspecified\|superseded\|key_compromise] | - | - | unspecified, superseded albo key_compromise. |

## `collective`

### `collective generate`

Wygeneruj identyfikator zbiorczy dla zestawu faktur.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--invoice` | TEXT | [] | - | Numer KSeF faktury do zgrupowania. Powtórz dla kolejnych faktur. |
| `--invoices-file` | FILE | - | - | Tablica JSON faktur. Dodaje płatność i opis przy każdej fakturze. |

### `collective list`

Wyszukaj identyfikatory zbiorcze widoczne w bieżącym kontekście logowania.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--date-from` | TEXT | required | - | Początek utworzenia, data albo data z czasem w ISO 8601. Sama data to północ UTC. |
| `--date-to` | TEXT | - | - | Koniec utworzenia, data albo data z czasem w ISO 8601. Sama data to północ UTC. Domyślnie teraz. |
| `--number` | TEXT | - | - | Dokładny numer identyfikatora. |
| `--invoice-count-min` | INTEGER RANGE | - | - | Minimalna liczba zgrupowanych faktur. |
| `--invoice-count-max` | INTEGER RANGE | - | - | Maksymalna liczba zgrupowanych faktur. |
| `--current-context` | TEXT | - | - | Ogranicz do identyfikatorów utworzonych w tym kontekście logowania: yes albo no. |
| `--page-size` | INTEGER RANGE | 10 | - | - |
| `--all` | - | false | - | Pobierz wszystkie strony. |

### `collective list-for-invoice`

Wypisz identyfikatory zbiorcze, które wskazują jedną fakturę w KSeF.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--ksef-number` | TEXT | required | - | - |
| `--page-size` | INTEGER RANGE | 10 | - | - |
| `--all` | - | false | - | Pobierz wszystkie strony. |

### `collective list-invoices`

Użycie: `ksef2 collective list-invoices [OPTIONS] NUMBERS...`

Wypisz faktury zgrupowane pod identyfikatorami zbiorczymi.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `NUMBERS...` | - | required | - | Numer albo numery identyfikatora zbiorczego, do 10 na żądanie. |
| `--page-size` | INTEGER RANGE | 10 | - | - |
| `--all` | - | false | - | Pobierz wszystkie strony. |

## `config`

### `config init`

Utwórz pusty lokalny plik konfiguracji.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--force` | - | false | - | Nadpisz istniejący plik konfiguracji. |

### `config path`

Użycie: `ksef2 config path`

Pokaż ścieżkę lokalnej konfiguracji użytej w tym wywołaniu.

### `config show`

Użycie: `ksef2 config show`

Pokaż wartości lokalnej konfiguracji.

## `encryption`

### `encryption certificates`

Wypisz publiczne certyfikaty szyfrowania KSeF.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--usage` | [ksef_token_encryption\|symmetric_key_encryption] | [] | - | Filtr zastosowania certyfikatu. Powtórz dla kilku zastosowań. |

## `fa3`

### `fa3 build`

Zbuduj XML FA(3) ze szkicu faktury w JSON.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--in`, `-i` | PATH | required | - | Plik JSON szkicu faktury albo - , żeby czytać szkic ze standardowego wejścia. |
| `--out`, `-o` | FILE | - | - | Gdzie zapisać XML FA(3). Domyślnie standardowe wyjście. |
| `--pretty`, `--no-pretty` | - | true | - | Wcinaj wygenerowany XML. |
| `--validate`, `--no-validate` | - | true | - | Sprawdź XML względem schematu FA(3) przed zapisem. |

### `fa3 draft-example`

Wypisz minimalny szkic faktury, który przyjmuje fa3 build.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--out`, `-o` | FILE | - | - | Gdzie zapisać szkic. Domyślnie standardowe wyjście. |

### `fa3 inspect`

Użycie: `ksef2 fa3 inspect [OPTIONS] [INVOICE_PATH]`

Odczytaj XML faktury i wypisz fakturę, którą opisuje.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--in`, `-i` | FILE | - | - | Plik XML faktury FA(3). Zamiennik ścieżki pozycyjnej. |
| `[INVOICE_PATH]` | - | - | - | Plik XML faktury FA(3). |

### `fa3 render`

Wyrenderuj XML faktury do HTML, a opcjonalnie także do PDF.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--in`, `-i` | FILE | required | - | Plik XML faktury FA(3). |
| `--out`, `-o` | FILE | - | - | Gdzie zapisać HTML. Domyślnie standardowe wyjście, gdy nie używasz --pdf. |
| `--pdf` | FILE | - | - | Zapisz tu także PDF. Potrzebuje opcjonalnych zależności ksef2[pdf]. |
| `--code-lookups`, `--no-code-lookups` | - | false | - | Rozwiń kody krajów i urzędów skarbowych według oficjalnych list dołączonych do SDK, bez dostępu do sieci. |
| `--ksef-number` | TEXT | - | - | Z --pdf: numer KSeF przyjętej faktury. Jest drukowany pod kodem QR weryfikacji dla wybranego --env. Pomiń go przy PDF szkicu. |

## `invoices`

### `invoices download`

Użycie: `ksef2 invoices download [OPTIONS] [NUMBER]`

Pobierz przetworzony XML faktury po numerze KSeF.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--ksef-number` | TEXT | - | - | Numer KSeF faktury. Zamiennik numeru pozycyjnego. |
| `--out`, `-o` | FILE | - | - | Docelowy plik XML (domyślnie NUMBER.xml w bieżącym katalogu). Użyj - dla surowych bajtów XML na standardowym wyjściu. Diagnostyka zostaje na standardowym wyjściu błędów. Nie łączy się z globalnym wynikiem JSON. |
| `--wait` | - | false | - | Sprawdzaj status, aż fakturę da się pobrać. |
| `--timeout` | FLOAT RANGE | 120.0 | - | Maksymalny czas oczekiwania w sekundach. |
| `--poll-interval` | FLOAT RANGE | 2.0 | - | Sekundy między sprawdzeniami statusu. |
| `[NUMBER]` | - | - | - | Numer KSeF faktury. |

### `invoices export`

Zaplanuj eksport faktur i opcjonalnie zapisz jego stan do wznowienia.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--date-from` | TEXT | required | - | Początkowa data albo data z czasem w ISO. Bez przesunięcia jest czytana w Europe/Warsaw. Maksymalny zakres: 100 dni. |
| `--date-to` | TEXT | - | - | Końcowa data albo data z czasem w ISO. Domyślnie teraz, w UTC. Bez przesunięcia jest czytana w Europe/Warsaw. |
| `--role` | [seller\|buyer\|third_subject\|authorized_subject] | seller | - | buyer, seller, third_subject albo authorized_subject. |
| `--date-type` | [issue_date\|invoicing_date\|permanent_storage] | issue_date | - | issue_date, invoicing_date albo permanent_storage. |
| `--amount-type` | [brutto\|netto\|vat] | brutto | - | brutto, netto albo vat. |
| `--restrict-to-permanent-storage-hwm-date`, `--restrict-hwm` | - | false | - | Ogranicz wyniki do znacznika HWM trwałego zapisu, żeby powtórzone żądania zwracały stabilny zestaw. |
| `--currency` | TEXT | [] | - | Kod waluty. Powtórz dla kilku wartości. |
| `--invoice-type` | [vat\|zal\|kor\|roz\|upr\|kor_zal\|kor_roz\|vat_pef\|vat_pef_sp\|kor_pef\|vat_rr\|kor_vat_rr] | [] | - | Typ faktury. Powtórz dla kilku wartości. |
| `--seller-nip` | TEXT | - | - | Dopasuj ten NIP sprzedawcy. |
| `--buyer-nip` | TEXT | - | - | Dopasuj ten NIP nabywcy. |
| `--buyer-vat-ue` | TEXT | - | - | Dopasuj ten identyfikator VAT UE nabywcy. |
| `--buyer-other-id` | TEXT | - | - | Dopasuj ten identyfikator nabywcy innego rodzaju. |
| `--invoice-number` | TEXT | - | - | Dopasuj ten numer faktury sprzedawcy. |
| `--ksef-number` | TEXT | - | - | Dopasuj ten numer KSeF. |
| `--amount-min` | FLOAT | - | - | Minimalna kwota wybranego rodzaju kwoty. |
| `--amount-max` | FLOAT | - | - | Maksymalna kwota wybranego rodzaju kwoty. |
| `--form` | [FA2\|FA3\|FA_RR1\|PEF3\|PEF_KOR3] | - | - | Struktura: FA2, FA3, FA_RR1, PEF3, PEF_KOR3. |
| `--invoicing-mode` | [online\|offline] | - | - | online albo offline. |
| `--attachment` | TEXT | - | - | Filtruj po obecności załącznika: yes albo no. |
| `--self-invoicing` | TEXT | - | - | Filtruj po fladze samofakturowania: yes albo no. |
| `--only-metadata` | - | false | - | Eksportuj tylko metadane. |
| `--compression-type` | [zip\|tar_gz] | - | - | Format archiwum eksportu: zip albo tar_gz. |
| `--handle-file` | FILE | - | - | Zapisz plik --handle-file potrzebny do późniejszego pobrania. |

### `invoices export-download`

Zaplanuj eksport faktur, poczekaj, pobierz go i odszyfruj.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--date-from` | TEXT | required | - | Początkowa data albo data z czasem w ISO. Bez przesunięcia jest czytana w Europe/Warsaw. Maksymalny zakres: 100 dni. |
| `--date-to` | TEXT | - | - | Końcowa data albo data z czasem w ISO. Domyślnie teraz, w UTC. Bez przesunięcia jest czytana w Europe/Warsaw. |
| `--role` | [seller\|buyer\|third_subject\|authorized_subject] | seller | - | buyer, seller, third_subject albo authorized_subject. |
| `--date-type` | [issue_date\|invoicing_date\|permanent_storage] | issue_date | - | issue_date, invoicing_date albo permanent_storage. |
| `--amount-type` | [brutto\|netto\|vat] | brutto | - | brutto, netto albo vat. |
| `--restrict-to-permanent-storage-hwm-date`, `--restrict-hwm` | - | false | - | Ogranicz wyniki do znacznika HWM trwałego zapisu, żeby powtórzone żądania zwracały stabilny zestaw. |
| `--currency` | TEXT | [] | - | Kod waluty. Powtórz dla kilku wartości. |
| `--invoice-type` | [vat\|zal\|kor\|roz\|upr\|kor_zal\|kor_roz\|vat_pef\|vat_pef_sp\|kor_pef\|vat_rr\|kor_vat_rr] | [] | - | Typ faktury. Powtórz dla kilku wartości. |
| `--seller-nip` | TEXT | - | - | Dopasuj ten NIP sprzedawcy. |
| `--buyer-nip` | TEXT | - | - | Dopasuj ten NIP nabywcy. |
| `--buyer-vat-ue` | TEXT | - | - | Dopasuj ten identyfikator VAT UE nabywcy. |
| `--buyer-other-id` | TEXT | - | - | Dopasuj ten identyfikator nabywcy innego rodzaju. |
| `--invoice-number` | TEXT | - | - | Dopasuj ten numer faktury sprzedawcy. |
| `--ksef-number` | TEXT | - | - | Dopasuj ten numer KSeF. |
| `--amount-min` | FLOAT | - | - | Minimalna kwota wybranego rodzaju kwoty. |
| `--amount-max` | FLOAT | - | - | Maksymalna kwota wybranego rodzaju kwoty. |
| `--form` | [FA2\|FA3\|FA_RR1\|PEF3\|PEF_KOR3] | - | - | Struktura: FA2, FA3, FA_RR1, PEF3, PEF_KOR3. |
| `--invoicing-mode` | [online\|offline] | - | - | online albo offline. |
| `--attachment` | TEXT | - | - | Filtruj po obecności załącznika: yes albo no. |
| `--self-invoicing` | TEXT | - | - | Filtruj po fladze samofakturowania: yes albo no. |
| `--out-dir` | DIRECTORY | downloads | - | Katalog na pobrane pliki eksportu. |
| `--only-metadata` | - | false | - | Eksportuj metadane bez plików XML faktur. |
| `--compression-type` | [zip\|tar_gz] | - | - | Format archiwum eksportu: zip albo tar_gz. |
| `--timeout` | FLOAT RANGE | 120.0 | - | Maksymalny czas oczekiwania w sekundach. |
| `--poll-interval` | FLOAT RANGE | 2.0 | - | Sekundy między sprawdzeniami statusu. |
| `--handle-file` | FILE | - | - | Zapisz stan eksportu do wznowienia w tym chronionym pliku. |

### `invoices export-fetch`

Pobierz i odszyfruj paczkę eksportu z zapisanego pliku --handle-file.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--handle-file` | FILE | required | - | Zapisany plik --handle-file ze stanem odszyfrowania. |
| `--out-dir` | DIRECTORY | downloads | - | Katalog na pobrane pliki eksportu. |
| `--wait` | - | false | - | Czekaj na paczkę eksportu. |
| `--timeout` | FLOAT RANGE | 120.0 | - | Maksymalny czas oczekiwania w sekundach. |
| `--poll-interval` | FLOAT RANGE | 2.0 | - | Sekundy między sprawdzeniami statusu. |

### `invoices export-pdf`

Pobierz eksport faktur i wyrenderuj każdą fakturę do PDF.

Potrzebny jest opcjonalny dodatek pdf: zainstaluj ``ksef2-cli[pdf]``, który dociąga WeasyPrint i jego biblioteki systemowe. Odszyfrowany XML zostaje w --out-dir, a każdy PDF jest zapisywany obok niego albo do --pdf-dir, gdy je podasz.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--date-from` | TEXT | required | - | Początkowa data albo data z czasem w ISO. Bez przesunięcia jest czytana w Europe/Warsaw. Maksymalny zakres: 100 dni. |
| `--date-to` | TEXT | - | - | Końcowa data albo data z czasem w ISO. Domyślnie teraz, w UTC. Bez przesunięcia jest czytana w Europe/Warsaw. |
| `--role` | [seller\|buyer\|third_subject\|authorized_subject] | seller | - | buyer, seller, third_subject albo authorized_subject. |
| `--date-type` | [issue_date\|invoicing_date\|permanent_storage] | issue_date | - | issue_date, invoicing_date albo permanent_storage. |
| `--amount-type` | [brutto\|netto\|vat] | brutto | - | brutto, netto albo vat. |
| `--restrict-to-permanent-storage-hwm-date`, `--restrict-hwm` | - | false | - | Ogranicz wyniki do znacznika HWM trwałego zapisu, żeby powtórzone żądania zwracały stabilny zestaw. |
| `--currency` | TEXT | [] | - | Kod waluty. Powtórz dla kilku wartości. |
| `--invoice-type` | [vat\|zal\|kor\|roz\|upr\|kor_zal\|kor_roz\|vat_pef\|vat_pef_sp\|kor_pef\|vat_rr\|kor_vat_rr] | [] | - | Typ faktury. Powtórz dla kilku wartości. |
| `--seller-nip` | TEXT | - | - | Dopasuj ten NIP sprzedawcy. |
| `--buyer-nip` | TEXT | - | - | Dopasuj ten NIP nabywcy. |
| `--buyer-vat-ue` | TEXT | - | - | Dopasuj ten identyfikator VAT UE nabywcy. |
| `--buyer-other-id` | TEXT | - | - | Dopasuj ten identyfikator nabywcy innego rodzaju. |
| `--invoice-number` | TEXT | - | - | Dopasuj ten numer faktury sprzedawcy. |
| `--ksef-number` | TEXT | - | - | Dopasuj ten numer KSeF. |
| `--amount-min` | FLOAT | - | - | Minimalna kwota wybranego rodzaju kwoty. |
| `--amount-max` | FLOAT | - | - | Maksymalna kwota wybranego rodzaju kwoty. |
| `--form` | [FA2\|FA3\|FA_RR1\|PEF3\|PEF_KOR3] | - | - | Struktura: FA2, FA3, FA_RR1, PEF3, PEF_KOR3. |
| `--invoicing-mode` | [online\|offline] | - | - | online albo offline. |
| `--attachment` | TEXT | - | - | Filtruj po obecności załącznika: yes albo no. |
| `--self-invoicing` | TEXT | - | - | Filtruj po fladze samofakturowania: yes albo no. |
| `--out-dir` | DIRECTORY | downloads | - | Katalog na pobrane pliki eksportu. |
| `--pdf-dir` | DIRECTORY | - | - | Gdzie zapisać pliki PDF. Domyślnie --out-dir. |
| `--paper-size` | [a4\|a4-landscape\|a3\|a3-landscape\|letter\|letter-landscape] | - | - | Rozmiar papieru PDF. Domyślnie ustawienie arkusza stylów. |
| `--only-metadata` | - | false | - | Eksportuj metadane bez plików XML faktur. |
| `--compression-type` | [zip\|tar_gz] | - | - | Format archiwum eksportu: zip albo tar_gz. |
| `--timeout` | FLOAT RANGE | 120.0 | - | Maksymalny czas oczekiwania w sekundach. |
| `--poll-interval` | FLOAT RANGE | 2.0 | - | Sekundy między sprawdzeniami statusu. |
| `--handle-file` | FILE | - | - | Zapisz stan eksportu do wznowienia w tym chronionym pliku. |

### `invoices export-status`

Pobierz status eksportu faktur.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--reference` | TEXT | required | - | Numer referencyjny eksportu. |

### `invoices metadata`

Zapytaj o metadane faktur.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--date-from` | TEXT | required | - | Początkowa data albo data z czasem w ISO. Bez przesunięcia jest czytana w Europe/Warsaw. Maksymalny zakres: 100 dni. |
| `--date-to` | TEXT | - | - | Końcowa data albo data z czasem w ISO. Domyślnie teraz, w UTC. Bez przesunięcia jest czytana w Europe/Warsaw. |
| `--role` | [seller\|buyer\|third_subject\|authorized_subject] | seller | - | buyer, seller, third_subject albo authorized_subject. |
| `--date-type` | [issue_date\|invoicing_date\|permanent_storage] | issue_date | - | issue_date, invoicing_date albo permanent_storage. |
| `--amount-type` | [brutto\|netto\|vat] | brutto | - | brutto, netto albo vat. |
| `--restrict-to-permanent-storage-hwm-date`, `--restrict-hwm` | - | false | - | Ogranicz wyniki do znacznika HWM trwałego zapisu, żeby powtórzone żądania zwracały stabilny zestaw. |
| `--currency` | TEXT | [] | - | Kod waluty. Powtórz dla kilku wartości. |
| `--invoice-type` | [vat\|zal\|kor\|roz\|upr\|kor_zal\|kor_roz\|vat_pef\|vat_pef_sp\|kor_pef\|vat_rr\|kor_vat_rr] | [] | - | Typ faktury. Powtórz dla kilku wartości. |
| `--seller-nip` | TEXT | - | - | Dopasuj ten NIP sprzedawcy. |
| `--buyer-nip` | TEXT | - | - | Dopasuj ten NIP nabywcy. |
| `--buyer-vat-ue` | TEXT | - | - | Dopasuj ten identyfikator VAT UE nabywcy. |
| `--buyer-other-id` | TEXT | - | - | Dopasuj ten identyfikator nabywcy innego rodzaju. |
| `--invoice-number` | TEXT | - | - | Dopasuj ten numer faktury sprzedawcy. |
| `--ksef-number` | TEXT | - | - | Dopasuj ten numer KSeF. |
| `--amount-min` | FLOAT | - | - | Minimalna kwota wybranego rodzaju kwoty. |
| `--amount-max` | FLOAT | - | - | Maksymalna kwota wybranego rodzaju kwoty. |
| `--form` | [FA2\|FA3\|FA_RR1\|PEF3\|PEF_KOR3] | - | - | Struktura: FA2, FA3, FA_RR1, PEF3, PEF_KOR3. |
| `--invoicing-mode` | [online\|offline] | - | - | online albo offline. |
| `--attachment` | TEXT | - | - | Filtruj po obecności załącznika: yes albo no. |
| `--self-invoicing` | TEXT | - | - | Filtruj po fladze samofakturowania: yes albo no. |
| `--page-size` | INTEGER RANGE | 10 | - | Liczba pozycji na żądanie API, także z --all. |
| `--page-offset` | INTEGER RANGE | 0 | - | Przesunięcie jednej strony. Z --all musi wynosić 0. |
| `--sort-order` | [asc\|desc] | asc | - | asc albo desc. |
| `--all` | - | false | - | Pobierz wszystkie pozycje metadanych. |

### `invoices send`

Użycie: `ksef2 invoices send [OPTIONS] INVOICE_PATHS...`

Wyślij jeden albo kilka plików XML faktury w sesji interaktywnej albo wsadowej.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `INVOICE_PATHS...` | - | required | - | Pliki XML faktur, katalogi albo - dla jednej faktury ze standardowego wejścia. |
| `--mode` | [online\|batch] | online | - | online albo batch. |
| `--recursive` | - | false | - | Uwzględnij pliki XML w katalogach zagnieżdżonych. |
| `--wait` | - | false | - | Czekaj na końcowy status przetwarzania. |
| `--upo-dir` | DIRECTORY | - | - | Katalog na pliki XML UPO. |
| `--receipt` | FILE | - | - | Zapisz jeden plik --receipt. |
| `--receipt-dir` | DIRECTORY | - | - | Katalog na pliki --receipt. |
| `--form` | [FA2\|FA3\|FA_RR1\|PEF3\|PEF_KOR3] | FA3 | - | Struktura: FA2, FA3, FA_RR1, PEF3, PEF_KOR3. |
| `--offline` | - | false | - | Zadeklaruj tryb offline sesji wsadowej. |
| `--max-part-size` | INTEGER RANGE | - | - | Maksymalny rozmiar zaszyfrowanej części paczki w bajtach. Tylko tryb wsadowy. |
| `--timeout` | FLOAT RANGE | 120.0 | - | Maksymalny czas oczekiwania na przetwarzanie w sekundach. |
| `--poll-interval` | FLOAT RANGE | 2.0 | - | Sekundy między sprawdzeniami statusu przetwarzania. |

### `invoices status`

Sprawdź status pliku --receipt z przepływu invoices.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--receipt` | FILE | required | - | Plik --receipt. |
| `--wait` | - | false | - | Czekaj na zakończenie. |
| `--timeout` | FLOAT RANGE | 120.0 | - | - |
| `--poll-interval` | FLOAT RANGE | 2.0 | - | - |

### `invoices upo`

Pobierz pliki XML UPO dla pliku --receipt z przepływu invoices.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--receipt` | FILE | required | - | Plik --receipt. |
| `--out`, `-o` | FILE | - | - | Docelowy plik XML UPO. |
| `--upo-dir` | DIRECTORY | - | - | Katalog na pliki XML UPO. |
| `--wait` | - | false | - | Czekaj, aż UPO będzie gotowe. |
| `--timeout` | FLOAT RANGE | 120.0 | - | - |
| `--poll-interval` | FLOAT RANGE | 2.0 | - | - |

## `limits`

### `limits get`

Użycie: `ksef2 limits get KIND:{api|context|subject}`

Odczytaj obowiązujące limity.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `KIND:{api|context|subject}` | - | required | - | api, context albo subject. |

### `limits production-rate-limits`

Użycie: `ksef2 limits production-rate-limits`

Ustaw limity częstości API w środowisku testowym na wartości zbliżone do produkcyjnych.

### `limits reset`

Użycie: `ksef2 limits reset KIND:{api|session|subject}`

Cofnij nadpisane limity środowiska testowego.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `KIND:{api|session|subject}` | - | required | - | api, session albo subject. |

### `limits set`

Użycie: `ksef2 limits set [OPTIONS] KIND:{api|context|subject}`

Ustaw nadpisane limity środowiska testowego z JSON.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `KIND:{api|context|subject}` | - | required | - | api, context albo subject. |
| `--payload` | FILE | required | - | Treść JSON z limitami. |

## `online`

### `online close`

Zamknij wznowioną sesję interaktywną.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--state-file` | FILE | required | - | - |

### `online invoice-status`

Pobierz status jednej faktury w sesji interaktywnej albo na niego poczekaj.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--state-file` | FILE | required | - | - |
| `--invoice-reference` | TEXT | required | - | - |
| `--wait` | - | false | - | Sprawdzaj status, aż będzie gotowe. |
| `--timeout` | FLOAT RANGE | 60.0 | - | Maksymalny czas oczekiwania w sekundach. |
| `--poll-interval` | FLOAT RANGE | 2.0 | - | Sekundy między sprawdzeniami statusu. |

### `online list`

Wypisz faktury wysłane w sesji interaktywnej.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--state-file` | FILE | required | - | - |
| `--page-size` | INTEGER RANGE | 10 | - | - |
| `--continuation-token` | TEXT | - | - | - |
| `--failed` | - | false | - | Wypisz tylko odrzucone faktury. |

### `online open`

Otwórz sesję interaktywną i opcjonalnie zapisz stan do wznowienia.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--state-file` | FILE | - | - | - |
| `--form` | [FA2\|FA3\|FA_RR1\|PEF3\|PEF_KOR3] | FA3 | - | Struktura: FA2, FA3, FA_RR1, PEF3, PEF_KOR3. |

### `online send`

Użycie: `ksef2 online send [OPTIONS] INVOICE_PATHS...`

Wyślij pliki XML faktur. Nowe sesje się zamykają. Wznowione sesje zostają domyślnie otwarte.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `INVOICE_PATHS...` | - | required | - | - |
| `--state-file` | FILE | - | - | Wznów istniejącą sesję interaktywną. |
| `--save-state` | FILE | - | - | Zapisz stan otwartej albo wznowionej sesji. |
| `--form` | [FA2\|FA3\|FA_RR1\|PEF3\|PEF_KOR3] | FA3 | - | Struktura: FA2, FA3, FA_RR1, PEF3, PEF_KOR3. |
| `--wait` | - | false | - | Czekaj, aż każda faktura skończy przetwarzanie. |
| `--keep-open` | - | false | - | Zostaw sesję otwartą po wysłaniu. |
| `--close` | - | false | - | Zamknij sesję po wysłaniu, także sesję wznowioną. |
| `--timeout` | FLOAT RANGE | 60.0 | - | Maksymalny czas oczekiwania w sekundach. |
| `--poll-interval` | FLOAT RANGE | 2.0 | - | Sekundy między sprawdzeniami statusu. |

### `online status`

Pobierz bieżący status wznowionej sesji interaktywnej.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--state-file` | FILE | required | - | - |

### `online upo`

Pobierz UPO faktury po numerze referencyjnym faktury albo po numerze KSeF.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--state-file` | FILE | required | - | - |
| `--out`, `-o` | FILE | required | - | - |
| `--invoice-reference` | TEXT | - | - | - |
| `--ksef-number` | TEXT | - | - | - |

## `peppol`

### `peppol providers`

Wypisz dostawców PEPPOL.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--all` | - | false | - | Pobierz wszystkie strony. |
| `--page-size` | INTEGER RANGE | 10 | - | Liczba pozycji na żądanie API, także z --all. |
| `--page-offset` | INTEGER RANGE | 0 | - | Przesunięcie jednej strony. Z --all musi wynosić 0. |

## `permissions`

### `permissions attachment-status`

Użycie: `ksef2 permissions attachment-status`

Odczytaj status uprawnienia do załączników.

### `permissions entity-roles`

Wypisz role przypisane uwierzytelnionemu podmiotowi.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--page-size` | INTEGER RANGE | 10 | - | Liczba pozycji na żądanie API, także z --all. |
| `--page-offset` | INTEGER RANGE | 0 | - | Przesunięcie jednej strony. Z --all musi wynosić 0. |
| `--all` | - | false | - | Pobierz wszystkie strony. |

### `permissions grant-authorization`

Nadaj podmiotowi upoważnienie do fakturowania.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--subject-type` | [nip\|peppol_id] | required | - | nip albo peppol_id. |
| `--subject-value` | TEXT | required | - | - |
| `--permission` | [self_invoicing\|rr_invoicing\|tax_representative\|pef_invoicing] | required | - | - |
| `--entity-name` | TEXT | required | - | - |
| `--description` | TEXT | required | - | - |
| `--wait` | - | false | - | Czekaj, aż operacja się skończy. |

### `permissions grant-entity`

Nadaj uprawnienia podmiotowi.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--subject-value` | TEXT | required | - | NIP podmiotu. |
| `--entity-name` | TEXT | required | - | - |
| `--description` | TEXT | required | - | - |
| `--permission` | [invoice_read\|invoice_write\|collective_identifier_manage] | [] | - | invoice_read albo invoice_write. Powtórz. |
| `--can-delegate` | - | false | - | Zastosuj delegację do wszystkich zakresów uprawnień. |
| `--wait` | - | false | - | Czekaj, aż operacja się skończy. |

### `permissions grant-eu-admin`

Nadaj prawa administracyjne podmiotu unijnego.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--subject-value` | TEXT | required | - | Identyfikator odcisku palca certyfikatu. |
| `--context-value` | TEXT | required | - | Wartość kontekstu logowania VAT UE. |
| `--eu-entity-name` | TEXT | required | - | - |
| `--description` | TEXT | required | - | - |
| `--context-type` | [nip_vat_ue] | nip_vat_ue | - | - |
| `--wait` | - | false | - | Czekaj, aż operacja się skończy. |

### `permissions grant-eu-entity`

Nadaj uprawnienia podmiotowi unijnemu.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--subject-value` | TEXT | required | - | Identyfikator odcisku palca certyfikatu. |
| `--description` | TEXT | required | - | - |
| `--permission` | [invoice_read\|invoice_write] | [] | - | invoice_read albo invoice_write. Powtórz. |
| `--wait` | - | false | - | Czekaj, aż operacja się skończy. |

### `permissions grant-indirect`

Nadaj uprawnienia pośrednie.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--subject-type` | [nip\|pesel\|fingerprint] | required | - | nip, pesel albo fingerprint. |
| `--subject-value` | TEXT | required | - | - |
| `--first-name` | TEXT | required | - | - |
| `--last-name` | TEXT | required | - | - |
| `--description` | TEXT | required | - | - |
| `--permission` | [invoice_read\|invoice_write\|collective_identifier_manage] | [] | - | invoice_read albo invoice_write. Powtórz. |
| `--target-type` | [nip\|all_partners\|internal_id] | - | - | - |
| `--target-value` | TEXT | - | - | - |
| `--wait` | - | false | - | Czekaj, aż operacja się skończy. |

### `permissions grant-person`

Nadaj uprawnienia bezpośrednio osobie.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--subject-type` | [nip\|pesel\|fingerprint] | required | - | nip, pesel albo fingerprint. |
| `--subject-value` | TEXT | required | - | - |
| `--first-name` | TEXT | required | - | - |
| `--last-name` | TEXT | required | - | - |
| `--description` | TEXT | required | - | - |
| `--permission` | [invoice_read\|invoice_write\|introspection\|credentials_read\|credentials_manage\|enforcement_operations\|subunit_manage] | [] | - | Zakres uprawnienia. Powtórz. |
| `--wait` | - | false | - | Czekaj, aż operacja się skończy. |

### `permissions grant-subunit`

Nadaj uprawnienia jednostki podrzędnej.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--subject-type` | [nip\|pesel\|fingerprint] | required | - | nip, pesel albo fingerprint. |
| `--subject-value` | TEXT | required | - | - |
| `--context-type` | [nip\|internal_id] | required | - | nip albo internal_id. |
| `--context-value` | TEXT | required | - | - |
| `--first-name` | TEXT | required | - | - |
| `--last-name` | TEXT | required | - | - |
| `--description` | TEXT | required | - | - |
| `--subunit-name` | TEXT | - | - | - |
| `--wait` | - | false | - | Czekaj, aż operacja się skończy. |

### `permissions operation-status`

Odczytaj status asynchronicznej operacji na uprawnieniach.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--reference` | TEXT | required | - | - |

### `permissions query`

Użycie: `ksef2 permissions query [OPTIONS] KIND:{entities|persons|authorizations|personal|eu-entities|subordinate-entities|subunits}`

Uruchom zapytanie o uprawnienia z treści JSON.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `KIND:{entities|persons|authorizations|personal|eu-entities|subordinate-entities|subunits}` | - | required | - | entities, persons, authorizations, personal, eu-entities, subordinate-entities albo subunits. |
| `--payload` | FILE | required | - | Treść JSON dla modelu zapytania SDK. |
| `--page-size` | INTEGER RANGE | 10 | - | Liczba pozycji na żądanie API, także z --all. |
| `--page-offset` | INTEGER RANGE | 0 | - | Przesunięcie jednej strony. Z --all musi wynosić 0. |
| `--all` | - | false | - | Pobierz wszystkie strony. |

### `permissions revoke-authorization`

Cofnij nadane upoważnienie.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--permission-id` | TEXT | required | - | - |
| `--wait` | - | false | - | Czekaj, aż operacja się skończy. |

### `permissions revoke-common`

Cofnij zwykłe nadanie uprawnienia.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--permission-id` | TEXT | required | - | - |
| `--wait` | - | false | - | Czekaj, aż operacja się skończy. |

## `profile`

### `profile create`

Użycie: `ksef2 profile create [OPTIONS] NAME`

Utwórz profil i opcjonalnie go wybierz.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `NAME` | - | required | - | Nazwa profilu. |
| `--env`, `-e` | [production\|demo\|test] | - | - | Środowisko KSeF dla tego profilu. |
| `--nip` | TEXT | - | - | NIP podatnika albo NIP kontekstu logowania. |
| `--token-env` | TEXT | - | - | Zmienna środowiskowa z tokenem KSeF. |
| `--context-type` | [nip\|internal_id\|nip_vat_ue\|peppol_id] | - | - | Typ kontekstu logowania przy uwierzytelnianiu tokenem. |
| `--test-cert` | - | false | - | Użyj uwierzytelniania certyfikatem testowym generowanym przez SDK. |
| `--cert` | FILE | - | - | Certyfikat PEM. |
| `--key` | FILE | - | - | Klucz prywatny PEM. |
| `--key-password-env` | TEXT | - | - | Zmienna środowiskowa z hasłem klucza PEM. |
| `--p12` | FILE | - | - | Archiwum PKCS#12/PFX. |
| `--p12-password-env` | TEXT | - | - | Zmienna środowiskowa z hasłem PKCS#12/PFX. |
| `--activate`, `--no-activate` | - | true | - | Wybierz ten profil po zapisaniu. |
| `--poll-interval` | FLOAT RANGE | - | - | Sekundy między sprawdzeniami statusu uwierzytelniania wykonywanymi z tym profilem. |
| `--max-poll-attempts` | INTEGER RANGE | - | - | Ile sprawdzeń statusu uwierzytelniania ten profil ma odczekać. |
| `--force` | - | false | - | Zastąp istniejący profil. |

### `profile current`

Użycie: `ksef2 profile current`

Pokaż aktywny profil.

### `profile delete`

Użycie: `ksef2 profile delete [OPTIONS] NAME`

Usuń profil. Gdy był wybrany, nie zostaje żaden aktywny profil.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `NAME` | - | required | - | Nazwa profilu. |
| `--yes`, `-y` | - | false | - | Usuń bez pytania o potwierdzenie. |

### `profile list`

Użycie: `ksef2 profile list`

Wypisz skonfigurowane profile.

### `profile show`

Użycie: `ksef2 profile show [NAME]`

Pokaż jeden profil albo profil aktywny, gdy nie podasz nazwy.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `[NAME]` | - | - | - | Nazwa profilu. |

### `profile use`

Użycie: `ksef2 profile use NAME`

Wybierz aktywny profil.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `NAME` | - | required | - | Nazwa profilu. |

## `sessions`

### `sessions auth-close`

Zamknij sesję uwierzytelniania po numerze referencyjnym.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--reference` | TEXT | required | - | - |

### `sessions auth-list`

Wypisz aktywne sesje uwierzytelniania.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--page-size` | INTEGER RANGE | - | - | - |
| `--continuation-token` | TEXT | - | - | Niewspierane od ksef2 1.0. Stronicowanie odbywa się wewnętrznie. |
| `--all` | - | false | - | Pobierz wszystkie strony. |

### `sessions auth-terminate-current`

Użycie: `ksef2 sessions auth-terminate-current`

Zakończ bieżącą sesję uwierzytelniania.

### `sessions invoice-list`

Wypisz historyczne sesje interaktywne albo wsadowe faktur.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--type` | [online\|batch] | required | - | online albo batch. |
| `--status` | [in_progress\|succeeded\|failed\|cancelled] | [] | - | Filtr statusu sesji. Powtórz dla kilku wartości. |
| `--reference` | TEXT | - | - | - |
| `--created-from` | TEXT | - | - | Utworzona w tej chwili albo później, data albo data z czasem w ISO. |
| `--created-to` | TEXT | - | - | Utworzona w tej chwili albo wcześniej, data albo data z czasem w ISO. |
| `--closed-from` | TEXT | - | - | Zamknięta w tej chwili albo później, data albo data z czasem w ISO. |
| `--closed-to` | TEXT | - | - | Zamknięta w tej chwili albo wcześniej, data albo data z czasem w ISO. |
| `--modified-from` | TEXT | - | - | Zmieniona w tej chwili albo później, data albo data z czasem w ISO. |
| `--modified-to` | TEXT | - | - | Zmieniona w tej chwili albo wcześniej, data albo data z czasem w ISO. |
| `--page-size` | INTEGER RANGE | 10 | - | - |
| `--all` | - | false | - | Pobierz wszystkie strony. |

### `sessions upo`

Pobierz UPO po numerze referencyjnym sesji, bez zapisanego stanu sesji.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--session` | TEXT | required | - | - |
| `--out`, `-o` | FILE | required | - | - |
| `--ksef-number` | TEXT | - | - | - |
| `--invoice-reference` | TEXT | - | - | - |
| `--upo-reference` | TEXT | - | - | - |

## `testdata`

### `testdata block-context`

Zablokuj kontekst logowania w środowisku testowym.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--context-type` | [nip\|internal_id\|nip_vat_ue\|peppol_id] | required | - | - |
| `--context-value` | TEXT | required | - | - |

### `testdata create-person`

Utwórz osobę w środowisku testowym.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--nip` | TEXT | required | - | - |
| `--pesel` | TEXT | required | - | - |
| `--description` | TEXT | required | - | - |
| `--bailiff` | - | false | - | - |
| `--deceased` | - | false | - | - |

### `testdata create-subject`

Utwórz podmiot w środowisku testowym.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--nip` | TEXT | required | - | - |
| `--type` | [enforcement_authority\|vat_group\|jst] | required | - | enforcement_authority, vat_group albo jst. |
| `--description` | TEXT | required | - | - |
| `--subunit` | TEXT | [] | - | Jednostka podrzędna w postaci NIP:description. Powtórz dla kilku. |

### `testdata delete-person`

Usuń osobę w środowisku testowym.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--nip` | TEXT | required | - | - |

### `testdata delete-subject`

Usuń podmiot w środowisku testowym.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--nip` | TEXT | required | - | - |

### `testdata enable-attachments`

Włącz załączniki dla podmiotu w środowisku testowym.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--nip` | TEXT | required | - | - |

### `testdata grant-permissions`

Nadaj uprawnienia w środowisku testowym.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--grant-to-type` | [nip\|pesel\|fingerprint\|system] | required | - | - |
| `--grant-to-value` | TEXT | required | - | - |
| `--context-type` | [nip\|pesel\|fingerprint\|system] | required | - | - |
| `--context-value` | TEXT | required | - | - |
| `--permission` | [invoice_read\|invoice_write\|pef_invoice_write\|introspection\|credentials_read\|credentials_manage\|enforcement_operations\|subunit_manage\|vat_ue_manage\|collective_identifier_manage] | [] | - | Typ uprawnienia. Powtórz. |
| `--description` | TEXT | Granted by ksef2-cli | - | - |

### `testdata revoke-attachments`

Cofnij załączniki podmiotowi w środowisku testowym.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--nip` | TEXT | required | - | - |
| `--expected-end-date` | TEXT | - | - | YYYY-MM-DD. |

### `testdata revoke-permissions`

Cofnij uprawnienia w środowisku testowym.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--revoke-from-type` | [nip\|pesel\|fingerprint\|system] | required | - | - |
| `--revoke-from-value` | TEXT | required | - | - |
| `--context-type` | [nip\|pesel\|fingerprint\|system] | required | - | - |
| `--context-value` | TEXT | required | - | - |

### `testdata sandbox`

Utwórz tymczasowy podmiot w środowisku testowym, z danymi uwierzytelniającymi i sprzątaniem przy wyjściu.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--nip` | TEXT | - | - | NIP tymczasowego podmiotu. Domyślnie wygenerowany NIP. |
| `--type` | [enforcement_authority\|vat_group\|jst] | enforcement_authority | - | enforcement_authority, vat_group albo jst. |
| `--description` | TEXT | ksef2-cli sandbox | - | Opis podmiotu w środowisku testowym. |
| `--out-dir` | DIRECTORY | .ksef2-sandbox | - | Katalog na wygenerowany certyfikat, klucz i pliki env. |
| `--token-permission` | [invoice_read\|invoice_write\|introspection\|credentials_read\|credentials_manage\|subunit_manage\|enforcement_operations\|collective_identifier_manage] | [] | - | Uprawnienie tokena. Powtórz dla kolejnych uprawnień. |
| `--token-description` | TEXT | ksef2-cli sandbox token | - | Opis wygenerowanego tokena. |
| `--hold`, `--no-hold` | - | true | - | Utrzymuj tymczasowy podmiot środowiska testowego, dopóki nie naciśniesz Enter. |

### `testdata unblock-context`

Odblokuj kontekst logowania w środowisku testowym.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--context-type` | [nip\|internal_id\|nip_vat_ue\|peppol_id] | required | - | - |
| `--context-value` | TEXT | required | - | - |

### `testdata update-certificate-valid-to`

Skróć ważność certyfikatu w środowisku testowym.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--serial-number` | TEXT | required | - | 16 znaków szesnastkowych, na przykład ABCDEF1234567890. |
| `--valid-to` | TEXT | required | - | Data z czasem w ISO 8601 z przesunięciem UTC, na przykład 2026-03-01T12:00:00Z, albo sama data, czyli północ UTC. |

## `tokens`

### `tokens generate`

Wygeneruj nowy token KSeF.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--description` | TEXT | required | - | Opis tokena. |
| `--permission`, `--permissions` | [invoice_read\|invoice_write\|introspection\|credentials_read\|credentials_manage\|subunit_manage\|enforcement_operations\|collective_identifier_manage] | [] | - | Uprawnienie do nadania. Powtórz dla kolejnych uprawnień. |
| `--wait` | - | false | - | Czekaj, aż token stanie się aktywny. |

### `tokens list`

Wypisz tokeny KSeF.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--status` | [pending\|active\|revoking\|revoked\|failed] | [] | - | Filtr statusu tokena. Powtórz dla kilku wartości. |
| `--description` | TEXT | - | - | - |
| `--author-identifier` | TEXT | - | - | - |
| `--author-identifier-type` | [nip\|pesel\|fingerprint] | - | - | - |
| `--page-size` | INTEGER RANGE | 10 | - | - |
| `--all` | - | false | - | Pobierz wszystkie strony. |

### `tokens revoke`

Unieważnij token KSeF.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--reference` | TEXT | required | - | - |

### `tokens status`

Pobierz status tokena.

| Opcja | Typ | Domyślnie | Zmienna środowiskowa | Opis |
| --- | --- | --- | --- | --- |
| `--reference` | TEXT | required | - | - |
