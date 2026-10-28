---
title: Sesje interaktywne
description: Otwórz sesję interaktywną KSeF, wyślij do niej faktury, obserwuj ją i zamknij. Grupa online i jej stan sesji do wznowienia.
---

Sesja interaktywna to ścieżka wysyłki na bieżąco. KSeF ją otwiera, ty przekazujesz do niej XML faktur po jednej, a potem ją zamykasz, żeby KSeF mógł przetworzyć faktury i wystawić ich UPO (Urzędowe Poświadczenie Odbioru). Grupy `online` używaj, gdy sesja ma trwać dłużej niż jedna komenda: dokładasz kolejne faktury, podczas gdy ktoś sprawdza szkic, albo drugi proces ma dokończyć to, co zaczął pierwszy. Gdy jedna komenda może zrobić całą pracę, `invoices send` otwiera sesję, wysyła, zamyka ją i oddaje plik `--receipt`. Zobacz [Przepływy faktur](invoices.md#wyślij-faktury).

CLI nie trzyma sesji otwartej między komendami. Każda komenda uwierzytelnia się, wznawia sesję z pliku stanu, robi jedną rzecz i kończy pracę. Plik stanu jest więc całym odniesieniem do sesji. Każda komenda w tej grupie uwierzytelnia się i potrzebuje danych uwierzytelniających. Zobacz [Uwierzytelnianie](authentication.md).

## Otwórz sesję i zachowaj jej stan

```bash
uv run ksef2 --profile test-company \
  online open --state-file online-state.json
```

Wynik tekstowy podaje nazwę pliku i stan z zamaskowanym materiałem klucza:

```text
state_file: online-state.json
state: {"format_version":1,"reference_number":"20260302-...","aes_key":"**********","iv":"**********","form_code":["FA (3)","1-0E","FA"],"valid_until":"2026-03-02T10:00:00Z"}
```

`--state-file` jest tu opcjonalne, ale sesji otwartej bez niego nie da się wznowić. Stan trafia na standardowe wyjście i proces się kończy. `online send` to jedyna inna komenda, która może otworzyć własną sesję. Reszta wymaga pliku.

Plik stanu trzyma klucz AES sesji i IV **otwartym tekstem**. CLI tworzy go z uprawnieniami tylko dla właściciela (`0600`) i nigdy nie wypisuje tych wartości. Ten tryb jest uprawnieniem. Zawartość pozostaje zapisana otwartym tekstem. Każdy, kto może odczytać plik jako jego właściciel, oraz każde narzędzie, które go kopiuje, uzyskuje dostęp do działającej sesji. Trzymaj plik poza repozytorium i poza logami. Usuń go, gdy sesja się skończy.

`valid_until` to termin sesji po stronie KSeF. Po jego upływie sesja nie przyjmuje już niczego. Otwórz nową, zamiast ponawiać stary stan.

## Wyślij faktury do sesji

```bash
uv run ksef2 --profile test-company \
  online send invoice-1.xml invoice-2.xml \
  --keep-open \
  --save-state online-state.json
```

| Opcja | Skutek |
| --- | --- |
| `--state-file FILE` | Wznawia tę sesję, bez otwierania nowej. Plik musi istnieć, a `--form` jest ignorowane, bo struktura jest już zapisana w stanie. |
| `--save-state FILE` | Zapisuje stan użytej sesji, otwartej albo wznowionej. Tak sesja rozpoczęta bez `--state-file` staje się możliwa do wznowienia. |
| `--form` | Struktura dla nowo otwartej sesji: `FA2`, `FA3` (domyślnie), `FA_RR1`, `PEF3`, `PEF_KOR3`. |
| `--wait` | Czeka, aż każda faktura skończy przetwarzanie, zanim wyśle następną. |
| `--keep-open` | Zostawia otwartą sesję, którą ta komenda otworzyła, dla następnej komendy. Bez tej flagi nowo otwarta sesja się zamyka. Sesja wznowiona przez `--state-file` i tak zostaje otwarta, więc flaga tam nic nie zmienia. |
| `--close` | Zamyka sesję na końcu komendy, także tę wznowioną przez `--state-file`. Tak kończysz wznowioną sesję bez osobnego `online close`. |
| `--timeout`, `--poll-interval` | Maksymalny czas oczekiwania: 60 sekund, status sprawdzany co 2 sekundy, o ile nie podasz inaczej. |

Sesja otwarta przez tę komendę zamyka się domyślnie, bo ta komenda prowadziła całą wysyłkę. Sesja wznowiona przez `--state-file` zostaje domyślnie otwarta, bo plik jest odniesieniem do sesji i następna komenda ma z niego skorzystać. `--close` ją kończy. Pole `closed` w wyniku mówi, co się stało. `--close` razem z `--keep-open` kończy się błędem, bez wybierania jednej z opcji.

Ścieżki faktur wskazują pliki. Każda ścieżka musi istnieć. Katalogów ta komenda nie przyjmuje. W odróżnieniu od `invoices send` ta komenda nie przechodzi katalogu i nie ma `--recursive`.

Wynik tekstowy wypisuje jeden wiersz na plik:

```text
file=invoice-1.xml result={"reference_number":"20260302-ABCD-EF1234567890"}
```

Na tym etapie KSeF potwierdza tylko, że przyjął zaszyfrowaną treść do sesji. Z `--wait` ten sam wiersz zawiera też wynik przetworzenia, łącznie z nadanym `ksef_number`:

```text
file=invoice-1.xml result={"ordinal_number":1,"invoice_number":"FV/42/2026","ksef_number":"5261040828-20260302-...","reference_number":"20260302-ABCD-EF1234567890",...,"status":{"code":200,"description":"Processed",...}}
```

Z `--json` dostajesz pełną treść: `state_file`, `closed` i tablicę `results` z jednym obiektem `{file, result}` na fakturę. Flaga `closed` mówi, czy KSeF może już zacząć przetwarzanie.

Zatrzymanie tej komendy po tym, jak KSeF przyjął fakturę, nie wycofuje faktury. Ctrl-C kończy się kodem `130`, a `--wait`, które wyczerpie czas, kodem `1`. To, co już wysłano, zostaje w sesji.

Co przetrwało zatrzymanie, zależy od tego, jak sesja się zaczęła. Sesja wznowiona przez `--state-file` nadal ma ten plik, więc `online list --state-file FILE` go czyta. Sesja otwarta przez tę komendę zapisuje `--save-state` dopiero po zakończeniu całej wysyłki, więc przerwana wysyłka nie zostawia żadnego pliku stanu. Sesję znajdziesz ponownie przez `sessions invoice-list --type online`, a numery referencyjne faktur weźmiesz z tego, co komenda zdążyła wypisać. Odczytaj sesję, zanim wyślesz którykolwiek z tych plików drugi raz. Zobacz [Przerwana wysyłka nie oznacza, że faktury nie przyjęto](invoices.md#przerwana-wysyłka-nie-oznacza-że-faktury-nie-przyjęto).

## Sprawdź stan sesji

```bash
uv run ksef2 --profile test-company \
  online status --state-file online-state.json
```

Jedno żądanie, bez czekania. Odpowiedź to podsumowanie sesji po stronie KSeF: `status`, `date_created`, `date_updated`, `valid_until`, `invoice_count`, `successful_invoice_count`, `failed_invoice_count` oraz `upo`, gdy zamknięta sesja ma strony UPO.

Te liczniki czytaj jako podsumowanie. Sesja podaje własny status, więc może być zakończona, a któraś faktura w środku i tak odrzucona. Aby sprawdzić, które to faktury, wypisz listę.

Dla jednej faktury podaj jej numer referencyjny i pozwól komendzie sprawdzać status:

```bash
uv run ksef2 --profile test-company \
  online invoice-status \
  --state-file online-state.json \
  --invoice-reference "$INVOICE_REFERENCE" \
  --wait \
  --timeout 120 \
  --poll-interval 2
```

Bez `--wait` to pojedynczy odczyt. Z tą flagą komenda wraca, gdy KSeF nada fakturze wynik albo gdy lokalny `--timeout` się skończy. Wyczerpany limit czasu nic nie mówi o KSeF. Faktura może nadal być przetwarzana, więc sprawdź później, zanim wyślesz plik drugi raz.

## Wypisz, co sesja przyjęła

```bash
uv run ksef2 --profile test-company \
  online list --state-file online-state.json --page-size 100

uv run ksef2 --profile test-company \
  online list --state-file online-state.json --failed
```

`--page-size` przyjmuje wartości od 10 do 1000 i domyślnie wynosi 10. Jedno wywołanie zwraca jedną stronę. `continuation_token` z poprzedniej strony przekaż do `--continuation-token`, żeby iść dalej. `--failed` przełącza z faktur przyjętych na odrzucone. Tam pojawia się powód odrzucenia.

## Zamknij sesję

```bash
uv run ksef2 --profile test-company \
  online close --state-file online-state.json
```

```text
reference_number: 20260302-...
closed: yes
```

Zamknięcie mówi KSeF, że kolejnych faktur nie będzie. Dzięki temu system może wystawić zbiorcze UPO sesji. Zamknięcie sesji, która już jest zamknięta, nic nie robi. Wznowiony klient najpierw pyta KSeF i pomija drugie zamknięcie.

## Pobierz UPO faktury

```bash
uv run ksef2 --profile test-company \
  online upo \
  --state-file online-state.json \
  --ksef-number "$KSEF_NUMBER" \
  --out invoice-upo.xml
```

`--out` jest wymagane. Wymagane jest też dokładnie jedno z `--ksef-number` albo `--invoice-reference`. Komenda pyta raz i nigdy nie czeka, więc najpierw uruchom `online invoice-status --wait`. Gdy KSeF jeszcze nie wystawił UPO, komenda kończy się kodem `1` pod nagłówkiem `KSeF has not finished processing yet` i każe spróbować później. Faktura odrzucona przez KSeF w ogóle nie dostaje UPO, więc przeczytaj jej status, zanim będziesz ponawiał w nieskończoność.

Do pobrania UPO nie potrzebujesz stanu sesji, tylko jej numeru referencyjnego. Z numerem referencyjnym sesji oraz numerem referencyjnym faktury albo numerem KSeF `sessions upo` czyta ten sam dokument ze świeżego logowania. Po tę komendę sięgaj, gdy pliku stanu już nie ma albo należy do innej maszyny. Zobacz [Sesje i UPO](sessions-and-upo.md#która-komenda-upo-pasuje).

## Powiązane strony

- [Przepływy faktur](invoices.md)
- [Sesje wsadowe](batch-sessions.md)
- [Sesje i UPO](sessions-and-upo.md)
- [Uwierzytelnianie](authentication.md)
- [Opis komend](../reference/commands.md)
