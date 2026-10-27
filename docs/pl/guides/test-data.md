---
title: Dane testowe
description: Twórz jednorazowe podmioty, osoby, uprawnienia, flagi załączników i zablokowane konteksty logowania w środowisku testowym przez KSeF2 CLI, łącznie z komendą testdata sandbox i skróceniem ważności certyfikatu.
---

Grupa `testdata` przygotowuje środowisko, na którym testujesz. Tworzy podmioty i osoby w środowisku testowym, nadaje i cofa uprawnienia testowe, włącza i wyłącza załączniki, blokuje i odblokowuje konteksty logowania oraz skraca ważność certyfikatu testowego. Nic z tego nie rusza danych faktur. Przygotowuje podmioty, które faktury wysyłają i odbierają.

Dwie zasady obejmują całą grupę. Istnieje tylko w środowisku testowym, więc każdą komendę tutaj uruchamiaj z `--env test` albo z profilem, który wybiera środowisko testowe. Wobec każdego innego środowiska CLI zatrzymuje się komunikatem `testdata is only available for Environment.TEST`. Służy do przygotowania środowiska testowego. Nie projektuj przepływu, który potrzebuje jej w środowisku przedprodukcyjnym (demo) albo produkcyjnym.

Komendy rozmawiają z endpointami danych testowych KSeF przez klienta głównego, więc nie potrzebują tokena, certyfikatu ani `--nip`. Każdy NIP, którego dotyczą, podajesz opcją. Wyjątkiem jest `testdata sandbox`: uwierzytelnia się wewnętrznie certyfikatem, który sam generuje.

## Przygotuj podmiot jedną komendą

`testdata sandbox` tworzy tymczasowy podmiot w środowisku testowym, generuje dla niego certyfikat testowy i klucz, uwierzytelnia się nimi i wydaje token, a potem utrzymuje to wszystko, dopóki nie powiesz inaczej:

```bash
uv run ksef2 --env test testdata sandbox
```

```text
nip: 5261040828
subject_type: enforcement_authority
token: ONE_TIME_VALUE
reference_number: 20260302-TOKEN-...
token_permissions: invoice_read, invoice_write
sandbox_dir: /home/you/work/.ksef2-sandbox/5261040828
cert_file: /home/you/work/.ksef2-sandbox/5261040828/cert.pem
key_file: /home/you/work/.ksef2-sandbox/5261040828/private-key.pem
env_file: /home/you/work/.ksef2-sandbox/5261040828/env.sh
source: source /home/you/work/.ksef2-sandbox/5261040828/env.sh
send_with_token: ksef2 --env test --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" invoices send invoice.xml --wait
send_with_certificate: ksef2 --env test --nip "$KSEF2_NIP" --cert "$KSEF2_CERT" --key "$KSEF2_KEY" invoices send invoice.xml --wait
cleanup: remote_test_data_on_exit
```

Komenda czeka potem na Enter, a jego naciśnięcie usuwa zdalne dane testowe. To zatrzymanie jest sensem przejścia. W drugim terminalu korzystasz z przygotowanego podmiotu, a gdy wrócisz, naciskasz Enter i podmiot znika. W skrypcie, który tworzy ten podmiot, czyta wynik i sprząta samodzielnie, dodaj `--no-hold`.

W tym drugim terminalu plik env to cały zestaw danych uwierzytelniających:

```bash
source .ksef2-sandbox/5261040828/env.sh

uv run ksef2 --env test --json \
  invoices metadata \
  --role seller \
  --date-from 2026-03-01T00:00:00Z \
  --all
```

`env.sh` eksportuje `KSEF2_NIP`, `KSEF2_TOKEN`, `KSEF2_CERT` i `KSEF2_KEY`. CLI zapisuje ten plik i klucz prywatny z uprawnieniami tylko dla właściciela (`0600`). Wartość tokena pojawia się raz, w tym wyniku i w tym pliku, a wynik `--json` tej komendy też ją niesie. Trzymaj terminal i katalog poza logami i commitami. Sprzątanie obejmuje tylko zdalne dane testowe, więc katalog `.ksef2-sandbox` usuń sam, gdy skończysz.

| Opcja | Skutek |
| --- | --- |
| `--nip` | NIP tymczasowego podmiotu. Domyślnie wygenerowany NIP z poprawną sumą kontrolną. NIP, który podasz, musi być poprawny. |
| `--type` | Typ podmiotu: `enforcement_authority` (domyślnie), `vat_group` albo `jst`. |
| `--description` | Opis podmiotu. Domyślnie `ksef2-cli sandbox`. |
| `--out-dir` | Gdzie trafiają certyfikat, klucz i pliki env. Domyślnie `.ksef2-sandbox`. Każdy podmiot dostaje własny podkatalog nazwany jego NIP-em. |
| `--token-permission` | Powtarzaj dla uprawnień, które dostaje token. Domyślnie `invoice_read` i `invoice_write`. |
| `--token-description` | Opis wygenerowanego tokena. |
| `--hold` / `--no-hold` | Czeka na Enter przed sprzątaniem. Oczekiwanie jest domyślne. |

## Twórz podmioty i osoby

Podmiot to organizacja. Osoba to człowiek przypisany do jednego podmiotu.

```bash
uv run ksef2 --env test testdata create-subject \
  --nip 5261040828 \
  --type vat_group \
  --description "Sandbox company"

uv run ksef2 --env test testdata create-person \
  --nip 5261040828 \
  --pesel 90010112345 \
  --description "Sandbox person"
```

Przy `create-person` wymagane są `--nip`, `--pesel` i `--description`. `--bailiff` albo `--deceased` służą do przejścia statusów, które te nazwy opisują. Przy `create-subject` `--type` przyjmuje `enforcement_authority`, `vat_group` albo `jst`, a `--subunit` powtarza się, żeby dodać jednostki podrzędne w postaci `NIP:description`:

```bash
uv run ksef2 --env test --json testdata create-subject \
  --nip 5261040828 \
  --type jst \
  --description "Sandbox unit" \
  --subunit 5261040829:"Branch one" \
  --subunit 5261040830:"Branch two"
```

Oba rodzaje mają pasujące usunięcie i oba przyjmują tylko NIP:

```bash
uv run ksef2 --env test testdata delete-subject --nip 5261040828
uv run ksef2 --env test testdata delete-person --nip 5261040828
```

Usuwaj to, co tworzysz, gdy zestaw danych jest współdzielony między uruchomieniami. Komendy tworzą dane w testowej bazie KSeF i same po sobie nie sprzątają. Robi to tylko `testdata sandbox`.

## Nadaj i cofnij uprawnienia testowe

Nadania powstają w kontekście logowania. Ktoś dostaje uprawnienie, które stosuje się do danych kogoś innego.

```bash
uv run ksef2 --env test testdata grant-permissions \
  --grant-to-type nip \
  --grant-to-value 1111111111 \
  --context-type nip \
  --context-value 5261040828 \
  --permission invoice_read \
  --permission invoice_write
```

`--grant-to-type` i `--context-type` przyjmują `nip`, `pesel`, `fingerprint` albo `system`, a co najmniej jedno `--permission` jest wymagane. Nazwy są własne dla KSeF:

```text
invoice_read            invoice_write           pef_invoice_write
introspection           credentials_read        credentials_manage
enforcement_operations  subunit_manage          vat_ue_manage
collective_identifier_manage
```

`--description` opisuje nadanie i domyślnie wynosi `Granted by ksef2-cli`. Pasujące cofnięcie nazywa tę samą parę, bez uprawnień:

```bash
uv run ksef2 --env test testdata revoke-permissions \
  --revoke-from-type nip \
  --revoke-from-value 1111111111 \
  --context-type nip \
  --context-value 5261040828
```

To dane środowiska testowego do sprawdzenia postaci nadania, zanim poprosisz o nie na serio. Nadania produkcyjne idą przez grupę `permissions`, opisaną w [Uprawnieniach](permissions.md).

## Włącz i wyłącz załączniki

```bash
uv run ksef2 --env test testdata enable-attachments --nip 5261040828
uv run ksef2 --env test testdata revoke-attachments --nip 5261040828
```

Załączniki są flagą na podmiocie. Dlatego [Uprawnienia](permissions.md#sprawdź-uprawnienia-do-załączników) czytają je własną komendą, a zmienia się je tutaj. Podmiot z `is_attachment_allowed` równym false nie może wysyłać faktur z załącznikami, dopóki coś ich nie włączy. `revoke-attachments` przyjmuje opcjonalne `--expected-end-date` w postaci `YYYY-MM-DD` dla unieważnienia, które zapisuje KSeF.

## Zablokuj i odblokuj kontekst logowania

```bash
uv run ksef2 --env test testdata block-context \
  --context-type nip \
  --context-value 5261040828

uv run ksef2 --env test testdata unblock-context \
  --context-type nip \
  --context-value 5261040828
```

`--context-type` przyjmuje `nip`, `internal_id`, `nip_vat_ue` albo `peppol_id`, a obie opcje są wymagane. To przełącznik do sprawdzenia, jak twój kod reaguje na odmowę kontekstu logowania: zablokuj go, uruchom komendę, która ma się nie powieść, a potem odblokuj w tym samym teście. Nie zostawiaj zablokowanego kontekstu, którym się uwierzytelniasz, bo KSeF odmawia go, dopóki coś go nie odblokuje.

## Skróć ważność certyfikatu

```bash
uv run ksef2 --env test testdata update-certificate-valid-to \
  --serial-number ABCDEF1234567890 \
  --valid-to 2026-03-01T12:00:00Z
```

```text
serial_number: ABCDEF1234567890
valid_to: 2026-03-01T12:00:00+00:00
updated: yes
```

`--serial-number` to 16 znaków szesnastkowych, czyli to, co `certificates list` i `certificates retrieve` podają dla certyfikatu, który posiadasz. CLI odrzuca numer seryjny, którego KSeF i tak by nie przyjął. `--valid-to` przyjmuje datę z czasem w ISO 8601 z przesunięciem UTC, bo endpoint działa na jednej chwili, a znacznik bez strefy żadnej nie nazywa. Data bez godziny, na przykład `2026-03-01`, to północ tego dnia w UTC. Data z czasem bez przesunięcia jest odrzucana, zanim cokolwiek zostanie wysłane. Komenda istnieje po to, żeby certyfikat szybko się skończył i dało się zobaczyć, co robi ścieżka odnowienia. Nie planuj wydłużania ważności tą komendą.

## Powiązane strony

- [Uwierzytelnianie](authentication.md)
- [Uprawnienia](permissions.md)
- [Certyfikaty](certificates.md)
- [Limity](limits.md)
- [Opis komend](../reference/commands.md)
