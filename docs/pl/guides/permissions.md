---
title: Uprawnienia
description: Nadawaj, wypisuj i cofaj uprawnienia KSeF dla osób, podmiotów, upoważnień, jednostek podrzędnych i podmiotów unijnych w KSeF2 CLI.
---

KSeF oddziela uwierzytelnianie od upoważnienia. Dane uwierzytelniające, które logują się czysto, i tak kończą się błędem przy wywołaniu poza swoim zakresem. Grupa `permissions` zmienia ten zakres. Ma jedną komendę na cel nadania, osobne komendy listujące i dwa cofnięcia.

Każde nadanie i cofnięcie jest asynchroniczne. Komenda zwraca numer referencyjny operacji KSeF, gdy tylko żądanie zostanie przyjęte, a zmiana stosuje się później. Nic tutaj nie mówi, że uprawnienie jest aktywne. Mówi o tym tylko status operacji.

| Komenda | Cel | Rodzaje identyfikatora celu |
| --- | --- | --- |
| `grant-person` | Nazwana osoba, bezpośrednio. | `nip`, `pesel`, `fingerprint` |
| `grant-entity` | Inna firma. | `--subject-value` to jej NIP |
| `grant-authorization` | Upoważnienie do fakturowania, na przykład samofakturowanie. | `nip`, `peppol_id` |
| `grant-indirect` | Osoba działająca dla konkretnego kontrahenta. | `nip`, `pesel`, `fingerprint` |
| `grant-subunit` | Osoba w kontekście jednej jednostki podrzędnej. | `nip`, `pesel`, `fingerprint` |
| `grant-eu-entity` | Podmiot unijny identyfikowany odciskiem palca certyfikatu. | `fingerprint` |
| `grant-eu-admin` | Administracja podmiotu unijnego. | `fingerprint` |

Wybierz komendę zgodną z tym, jak dostęp ma być utrzymywany. Nadanie przez złą komendę pojawia się na innej liście i cofa się inną ścieżką.

## Nadaj osobie

```bash
uv run ksef2 --profile prod-xades --json \
  permissions grant-person \
  --subject-type pesel \
  --subject-value 90010112345 \
  --first-name Jan \
  --last-name Kowalski \
  --description "Accounting read access" \
  --permission invoice_read
```

`--permission` powtarzasz dla kolejnych zakresów. Przyjmowane wartości to `invoice_read`, `invoice_write`, `introspection`, `credentials_read`, `credentials_manage`, `enforcement_operations` i `subunit_manage`. Co najmniej jedna jest wymagana. Komenda kończy się błędem przed żądaniem, gdy pominiesz je wszystkie.

## Nadaj innemu podmiotowi

```bash
uv run ksef2 --profile prod-xades --json \
  permissions grant-entity \
  --subject-value 1234567890 \
  --entity-name "Accounting Sp. z o.o." \
  --description "Bookkeeping for 2026" \
  --permission invoice_read \
  --permission invoice_write
```

`--subject-value` to NIP drugiej firmy. `--permission` przyjmuje `invoice_read`, `invoice_write` albo `collective_identifier_manage`. `--can-delegate` stosuje delegację do każdego zakresu w tym samym wywołaniu. Ma to znaczenie tylko na tych ścieżkach uprawnień, na których KSeF pozwala delegować.

## Nadaj upoważnienie do fakturowania

Upoważnienia obejmują szczególne tryby fakturowania:

```bash
uv run ksef2 --profile prod-xades --json \
  permissions grant-authorization \
  --subject-type nip \
  --subject-value 1234567890 \
  --permission self_invoicing \
  --entity-name "Partner Sp. z o.o." \
  --description "Self-invoicing agreement"
```

`--permission` przyjmuje tu jedną wartość: `self_invoicing`, `rr_invoicing`, `tax_representative` albo `pef_invoicing`. Użyj `--subject-type peppol_id`, gdy partnera identyfikuje numer PEPPOL.

## Nadaj uprawnienia pośrednie

Uprawnienia pośrednie wiążą osobę z kontrahentem:

```bash
uv run ksef2 --profile prod-xades --json \
  permissions grant-indirect \
  --subject-type nip \
  --subject-value 9876543210 \
  --first-name Anna \
  --last-name Nowak \
  --description "Broker for selected buyers" \
  --permission invoice_read \
  --target-type nip \
  --target-value 1234567890
```

`--target-type` to `nip`, `all_partners` albo `internal_id`, a `--target-value` wskazuje kontrahenta. Pomiń oba, gdy nadanie nie ma być ograniczone do jednego celu. `--permission` przyjmuje `invoice_read`, `invoice_write` albo `collective_identifier_manage`.

## Nadaj uprawnienia jednostki podrzędnej

Przy nadaniu dla jednostki podrzędnej wskazujesz kontekst logowania, w którym obowiązuje. Tym różni się od zwykłego nadania osobie:

```bash
uv run ksef2 --profile prod-xades --json \
  permissions grant-subunit \
  --subject-type pesel \
  --subject-value 90010112345 \
  --first-name Jan \
  --last-name Kowalski \
  --context-type nip \
  --context-value 1234567890 \
  --subunit-name "Warehouse Wawer" \
  --description "Subunit access"
```

`--context-type` to `nip` albo `internal_id`. `--subunit-name` jest opcjonalne i opisuje jednostkę podrzędną.

## Nadaj podmiotowi unijnemu

```bash
uv run ksef2 --profile prod-xades --json \
  permissions grant-eu-entity \
  --subject-value "$FINGERPRINT" \
  --description "EU entity read access" \
  --permission invoice_read
```

`--subject-value` to odcisk palca certyfikatu, a `--permission` przyjmuje `invoice_read` albo `invoice_write`. Prawa administracyjne to osobne wywołanie, bo są utrzymywane w kontekście VAT UE:

```bash
uv run ksef2 --profile prod-xades --json \
  permissions grant-eu-admin \
  --subject-value "$FINGERPRINT" \
  --context-value "PL1234567890" \
  --eu-entity-name "Example EU Entity" \
  --description "EU entity administrator"
```

`--context-type` domyślnie wynosi `nip_vat_ue` i tylko tę wartość przyjmuje, więc możesz je pominąć.

## Poczekaj na operację

Dodaj `--wait` do dowolnego nadania albo cofnięcia. Wynikiem jest wtedy status końcowy:

```bash
uv run ksef2 --profile prod-xades --json \
  permissions grant-entity \
  --subject-value 1234567890 \
  --entity-name "Accounting Sp. z o.o." \
  --description "Bookkeeping for 2026" \
  --permission invoice_read \
  --wait
```

```json
{
  "status": {
    "code": 200,
    "description": "Completed"
  }
}
```

Kod `100` oznacza, że KSeF nadal stosuje zmianę, a `200`, że skończył. Cokolwiek innego, na przykład `400` albo `500`, kończy komendę jako błąd, a komunikat zawiera opis zwrócony przez KSeF. `--wait` sprawdza status przez 60 sekund, co sekundę, i żadna opcja CLI tego czasu oczekiwania nie zmienia.

Bez `--wait`, albo po oczekiwaniu, które przekroczyło czas, sprawdź numer referencyjny samodzielnie:

```bash
uv run ksef2 --profile prod-xades --json \
  permissions operation-status --reference "$OPERATION_REFERENCE"
```

Dopóki ten status nie pokazuje `200`, nie pokazuj uprawnienia jako aktywnego we własnym systemie i nie uruchamiaj od niego zależnego zadania.

## Wypisz, co jest nadane

Role posiadane przez uwierzytelniony podmiot:

```bash
uv run ksef2 --profile prod-xades permissions entity-roles --all
```

Wszystko inne idzie przez `permissions query` z treścią JSON. Rodzaj wybiera postać zapytania, `--payload` wskazuje plik, a `--page-size`, `--page-offset` i `--all` stronicują wynik tak samo jak inne komendy listujące.

`--page-size` ustawia liczbę pozycji na żądanie API, także z `--all`. `--all` wymaga, żeby `--page-offset` było równe 0, czyli swojej wartości domyślnej, i odrzuca przesunięcie inne niż zero.

| Rodzaj | Model treści | Pola wymagane |
| --- | --- | --- |
| `personal` | `PersonalPermissionsQuery` | brak |
| `entities` | `EntityPermissionsQuery` | brak |
| `persons` | `PersonPermissionsQuery` | `query_type` |
| `authorizations` | `AuthorizationPermissionsQuery` | `query_type` |
| `eu-entities` | `EuEntityPermissionsQuery` | brak |
| `subordinate-entities` | `SubordinateEntityRolesQuery` | brak |
| `subunits` | `SubunitPermissionsQuery` | brak |

Własne aktywne nadania odczytu, w pliku `personal.json`:

```json
{
  "permission_types": ["invoice_read"],
  "permission_state": "active"
}
```

```bash
uv run ksef2 --profile prod-xades --json \
  permissions query personal --payload personal.json --all
```

Nadania wydane w kontekście jednej firmy, w `entities.json`:

```json
{
  "context_type": "nip",
  "context_value": "5261040828"
}
```

```bash
uv run ksef2 --profile prod-xades --json \
  permissions query entities --payload entities.json
```

Upoważnienia są podzielone kierunkiem, więc `query_type` jest wymagane. W `authorizations.json` wartość `granted` oznacza wydane przez ten podmiot, a `received` wydane dla niego:

```json
{
  "query_type": "granted",
  "permission_types": ["self_invoicing"]
}
```

```bash
uv run ksef2 --profile prod-xades \
  permissions query authorizations --payload authorizations.json
```

Dla rodzajów bez pól wymaganych `{}` jest poprawną treścią i zwraca wszystko, co KSeF wylistuje dla bieżącego kontekstu logowania. Każdy rodzaj zgłasza pola, które definiuje jego własne API. Poniżej te, na których później działasz:

| Rodzaj | Pola, które naprawdę odczytasz |
| --- | --- |
| `personal` | `id`, `permission_type`, `permission_state`, `authorized_value`, `target_value` |
| `entities` | `id`, `context_type`, `context_value`, `permission_type`, `can_delegate` |
| `persons` | `id`, `permission_type`, `permission_state`, `person_first_name`, `person_last_name` |
| `authorizations` | `id`, `authorization_scope`, `authorized_entity_value`, `authorizing_entity_value` |
| `eu-entities` | `id`, `vat_ue_identifier`, `authorized_fingerprint_identifier`, `permission_type` |
| `subordinate-entities` | `subordinate_entity_type`, `subordinate_entity_value`, `role` |
| `subunits` | `id`, `subunit_type`, `subunit_value`, `permission_type`, `subunit_name` |

Każde `id` to napis o długości 36 znaków, więc odczytaj je z listy, zamiast pisać je sam. Wiersze `subordinate-entities` nie mają pola `id`. Mówią o rolach i nic nie mówią o ich cofaniu.

Tryb tekstowy wypisuje jeden blok `key: value` na rekord i pomija puste pola. Skrypt powinien prosić o `--json`.

## Cofnij

Cofaj po `id` odczytanym z listy. Opis wpisany przy nadawaniu do tego nie służy:

```bash
uv run ksef2 --profile prod-xades --json \
  permissions revoke-common --permission-id "$PERMISSION_ID" --wait
```

Nadania upoważnień mają własne cofnięcie. Użycie złego zostawia nadanie na miejscu:

```bash
uv run ksef2 --profile prod-xades --json \
  permissions revoke-authorization --permission-id "$AUTHORIZATION_ID" --wait
```

Oba zwracają numer referencyjny operacji bez `--wait`, więc obowiązuje ta sama zasada statusu. Cofnięcie liczy się, gdy operacja zgłosi `200`.

## Sprawdź uprawnienia do załączników

Uprawnienia do załączników są stanem bieżącego podmiotu. Mają własną komendę tylko do odczytu:

```bash
uv run ksef2 --profile prod-xades --json permissions attachment-status
```

```json
{
  "is_attachment_allowed": true,
  "revoked_date": null
}
```

Podmiot z `is_attachment_allowed` równym false nie może wysyłać faktur z załącznikami, a `revoked_date` mówi, kiedy to się zaczęło. Zmiana tego stanu to praca na danych testowych środowiska testowego i nie należy do tej grupy.

## Powiązane strony

- [Tokeny](tokens.md)
- [Certyfikaty](certificates.md)
- [Uwierzytelnianie](authentication.md)
- [Opis komend](../reference/commands.md)
