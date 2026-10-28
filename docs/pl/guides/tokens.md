---
title: Tokeny
description: Wygeneruj, wypisz, sprawdź i unieważnij tokeny KSeF w KSeF2 CLI, a potem zachowaj wynik do uwierzytelniania tokenem.
---

Token KSeF to dane uwierzytelniające do wielokrotnego użycia, ze stałym zestawem uprawnień. Automatyzacja woli tokeny, bo maszyna, która uruchamia zadanie, nie potrzebuje ani certyfikatu, ani klucza prywatnego. Grupa `tokens` obejmuje cykl życia: generowanie, listę, sprawdzenie jednego tokena i unieważnienie. Użycie tokena do uwierzytelnienia to inne zadanie i należy do [Uwierzytelniania](authentication.md).

KSeF wydaje token kontekstowi logowania, który uwierzytelnił się certyfikatem, więc `tokens generate` uruchamiasz danymi XAdES albo certyfikatem testowym. Zwrócona wartość służy potem skryptom do uwierzytelniania. Zestaw uprawnień jest ustalany przy generowaniu. Aby zmienić to, co token może robić, wygeneruj nowy i unieważnij stary.

## Wygeneruj token

```bash
uv run ksef2 --env test --nip 5261040828 --test-cert --json \
  tokens generate \
  --description "nightly invoice export" \
  --permission invoice_read
```

```json
{
  "reference_number": "20260625-TOKEN-...",
  "token": "ONE_TIME_VALUE",
  "status": null
}
```

`--description` i co najmniej jedno `--permission` są wymagane. `--permission` powtarzasz dla szerszego zestawu. Osiem przyjmowanych wartości to własne nazwy API:

```text
invoice_read       invoice_write          introspection        credentials_read
credentials_manage subunit_manage         enforcement_operations
collective_identifier_manage
```

Co każda z nich otwiera, rozstrzyga KSeF. Nazwa to wszystko, co CLI może o niej powiedzieć, więc zacznij od jednej operacji, którą zadanie musi wykonać, i nadaj najwęższą nazwę, która ją obejmuje. Niektóre nazwy układają się przy grupach komend tego CLI, co pomaga przy wyborze: `invoice_read` i `invoice_write` przy `invoices`, `collective_identifier_manage` przy `collective`, `credentials_read` i `credentials_manage` przy `tokens` i `certificates`.

Token, który uwierzytelnia się poprawnie, i tak kończy się błędem przy wywołaniu spoza swojego zestawu.

Wartość `token` to jedyne wydanie sekretu przez KSeF. Późniejsze komendy rozpoznają token po `reference_number` i nie odzyskają wartości, więc zapisz ją, gdy pojawi się w wyniku. Traktuj standardowe wyjście tej komendy jak materiał sekretny. Trzymaj je poza logami, zapisami sesji i wątkami zgłoszeń.

W trybie tekstowym te same pola wypisują się po jednym w wierszu. Wiersza `status` brakuje, dopóki nie poczekasz na aktywację, bo wynik tekstowy pomija puste pola:

```text
reference_number: 20260625-TOKEN-...
token: ONE_TIME_VALUE
```

## Poczekaj na aktywację

Nowy token nie jest aktywny w chwili, w której wraca. `--wait` sprawdza status, aż KSeF zgłosi, że jest aktywny:

```bash
uv run ksef2 --profile prod-xades --auth-timeout 120 --auth-poll-interval 2 \
  tokens generate \
  --description "billing worker" \
  --permission invoice_read \
  --permission invoice_write \
  --wait
```

Maksymalny czas oczekiwania to `--auth-timeout` sekund, domyślnie `60`, sprawdzany co `--auth-poll-interval` sekund, domyślnie `1`. Profil, który ustawia `max_poll_attempts`, wyznacza czas oczekiwania jako `max_poll_attempts` razy swój `poll_interval`, gdy pominiesz `--auth-timeout`. Zobacz [Opcje cyklicznego sprawdzania](authentication.md#opcje-cyklicznego-sprawdzania).

Sprawdzanie odbywa się po tym, jak KSeF zwrócił dane uwierzytelniające, i zanim CLI cokolwiek wypisze. Limit czasu albo status `failed` lub `revoked` kończy komendę błędem, a wartość tokena nigdy nie dochodzi do terminala. Gdy utrata tej wartości ma znaczenie, podziel pracę na dwa kroki: wygeneruj bez `--wait`, zapisz sekret, a potem sprawdzaj status przez `tokens status`.

## Sprawdź jeden token

```bash
uv run ksef2 --profile prod-token --json \
  tokens status --reference "$TOKEN_REFERENCE"
```

```json
{
  "reference_number": "20260625-TOKEN-...",
  "status": "active"
}
```

Statusy to `pending`, `active`, `revoking`, `revoked` i `failed`.

## Wypisz tokeny

```bash
uv run ksef2 --profile prod-token tokens list \
  --status active \
  --page-size 50
```

Filtry: `--status` (powtórz dla kilku statusów), `--description` oraz `--author-identifier` razem z `--author-identifier-type` o wartości `nip`, `pesel` albo `fingerprint`. `--page-size` przyjmuje wartości od 10 do 100, a `--all` przechodzi wszystkie strony. W odróżnieniu od innych komend listujących ta nie ma `--page-offset`, więc dostajesz pierwszą stronę albo, z `--all`, cały wynik.

Wynik tekstowy wypisuje jeden wiersz `key=value` na token:

```text
reference_number=20260625-TOKEN-... status=active description=nightly invoice export author_identifier=nip:5261040828 context_identifier=nip:5261040828 requested_permissions=invoice_read date_created=2026-06-25T10:00:00+00:00
```

Puste pola znikają z wiersza, zamiast drukować puste miejsca, a `last_use_date` często nie występuje przy tokenie, którego nigdy nie użyto. Dodaj `--json`, gdy skrypt czyta te pola.

## Unieważnij token

```bash
uv run ksef2 --profile prod-token --json \
  tokens revoke --reference "$TOKEN_REFERENCE"
```

```json
{
  "reference_number": "20260625-TOKEN-...",
  "revoked": true
}
```

Odpowiedź oznacza, że KSeF przyjął unieważnienie. Uruchom `tokens status` i poczekaj na `revoked`, zanim usuniesz ostatnią kopię sekretu.

## Zachowaj token na kolejne komendy

Trzymaj obie połowy osobno. Wartość idzie do magazynu sekretów albo do zmiennej środowiskowej, a numer referencyjny tam, gdzie trzymasz konfigurację zadania.

```bash
export KSEF2_TOKEN='ONE_TIME_VALUE'

uv run ksef2 profile create billing-worker \
  --env production \
  --nip "$KSEF2_NIP" \
  --token-env KSEF2_TOKEN
```

Profil zapisuje nazwę zmiennej `KSEF2_TOKEN`. Wartość nigdy do pliku konfiguracji nie trafia, więc w konfiguracji nie ląduje nic sekretnego. Aby użyć tokena w jednej komendzie, pomiń profil:

```bash
uv run ksef2 --env production --nip "$KSEF2_NIP" --token "$KSEF2_TOKEN" --json \
  invoices metadata \
  --role seller \
  --date-from 2026-01-01T00:00:00Z \
  --all
```

`context_type` inny niż `nip` potrzebuje głównej opcji `--context-type` albo zmiennej `KSEF2_CONTEXT_TYPE`, jak opisuje [Uwierzytelnianie tokenem](authentication.md#uwierzytelnianie-tokenem).

Zapisz numer referencyjny, gdy tylko go masz. `tokens status` i `tokens revoke` go potrzebują, a nic w CLI nie zamienia numeru referencyjnego z powrotem w token ani tokena z powrotem w numer referencyjny.

## Powiązane strony

- [Uwierzytelnianie](authentication.md)
- [Uprawnienia](permissions.md)
- [Konfiguracja](configuration.md)
- [Opis komend](../reference/commands.md)
