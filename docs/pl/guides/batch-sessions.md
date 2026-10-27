---
title: Sesje wsadowe
description: Wyślij XML faktur jako jedną sesję wsadową KSeF, przygotuj paczkę raz i prześlij ją ponownie oraz odczytaj status, odrzucone faktury i strony UPO w KSeF2 CLI.
---

Sesja wsadowa niesie wiele faktur jako jeden przepływ KSeF. KSeF przyjmuje paczkę ZIP złożoną z plików XML, podzieloną na części i zaszyfrowaną przed przesłaniem. Ścieżka wsadowa ma więc etapy, których nie ma sesja interaktywna: przygotowanie, przesłanie, zamknięcie, oczekiwanie, a potem odczyt wyników poszczególnych faktur. `invoices send --mode batch` uruchamia je wszystkie jedną komendą. Grupy `batch` używaj, gdy potrzebujesz stanu sesji, chcesz przygotować paczkę raz i przesłać ją więcej niż raz albo musisz odzyskać przesłanie, które KSeF odrzucił. Zobacz [Przepływy faktur](invoices.md#wyślij-faktury-jako-paczkę).

Sprawdź sufit, zanim wybierzesz wielkość paczki. `limits get context` podaje `batch_session.max_invoices` i limit rozmiaru jednej faktury dla bieżącego kontekstu logowania. KSeF egzekwuje oba. Zobacz [Limity](limits.md#odczytaj-obowiązujące-limity).

## Wyślij paczkę jedną komendą

```bash
uv run ksef2 --profile prod-token \
  batch submit invoice-1.xml invoice-2.xml \
  --wait \
  --state-file batch-state.json
```

To przygotowuje paczkę, otwiera sesję wsadową, przesyła każdą część, zamyka sesję, a potem czeka, jeśli o to poprosisz. Ścieżki faktur to pliki i muszą istnieć. Tutaj nie ma przejścia katalogu, więc katalog plików przekaż do `invoices send`. Pozostałe opcje:

| Opcja | Skutek |
| --- | --- |
| `--state-file FILE` | Gdzie zapisać stan sesji do wznowienia. Przy nieudanym przesłaniu tu ląduje stan przerwanej sesji. |
| `--form` | Struktura zadeklarowana dla sesji: `FA2`, `FA3` (domyślnie), `FA_RR1`, `PEF3`, `PEF_KOR3`. |
| `--offline` | Deklaruje tryb offline dla paczki. |
| `--max-part-size BYTES` | Dzieli ZIP na mniejsze części, z limitem tego rozmiaru przed szyfrowaniem. Pomiń, żeby użyć wartości domyślnej SDK. |
| `--wait` | Czeka, aż KSeF skończy przetwarzać zamkniętą sesję. |
| `--timeout`, `--poll-interval` | Budżet oczekiwania: 120 sekund, sprawdzany co 2 sekundy, o ile nie podasz inaczej. |

`--wait` zwraca status sesji, więc wynik niesie i podsumowanie stanu, i rozstrzygnięcie:

```text
state_file: batch-state.json
state: {"format_version":1,"reference_number":"20260302-BATCH-...","aes_key":"**********","iv":"**********","form_code":["FA (3)","1-0E","FA"],"prepared_batch_digest":null}
status: {"status":{"code":200,"description":"Processed","details":null},...,"upo":{"pages":[{"reference_number":"upo-page-1","download_url_expiration_date":"2026-03-03T00:00:00Z"}]},"invoice_count":2,"successful_invoice_count":2,"failed_invoice_count":0}
```

Bez `--wait` nic nie odpytuje sesji. Wynik JSON podaje `status` jako `null`, a wynik tekstowy pomija ten wiersz. Plik stanu trzyma klucz AES sesji i IV **otwartym tekstem**. CLI tworzy go z uprawnieniami tylko dla właściciela (`0600`) i wypisuje te wartości zamaskowane, jak każdy inny plik stanu w CLI. `0600` decyduje, kto może otworzyć plik. Zawartość pozostaje zapisana otwartym tekstem, więc plik jest danymi uwierzytelniającymi wszędzie tam, gdzie go skopiujesz.

## Przygotuj raz, prześlij wielokrotnie

Pakowanie i szyfrowanie części kosztuje więcej niż ich wysłanie, a nic z tego nie zależy od sesji. `batch prepare` zapisuje gotową paczkę do katalogu, więc odrzucone przesłanie ponawiasz na częściach, które już istnieją:

```bash
uv run ksef2 --profile prod-token \
  batch prepare invoice-1.xml invoice-2.xml \
  --out batch-parts
```

```text
path: batch-parts
invoices: 2
parts: 2
digest: e6c4f3f11decada4ab73c73d9f788a13d357a3471f4439b4a354ae70ff7caff3
```

`--out` (`-o`) jest wymagane. `--form`, `--offline` i `--max-part-size` znaczą tu to samo co przy `submit`. Skrót obejmuje części, więc dwie paczki odróżnisz bez otwierania ich.

Zapisaną paczkę przesyłasz do nowej sesji przez `--prepared`:

```bash
uv run ksef2 --profile prod-token \
  batch submit --prepared batch-parts \
  --wait \
  --state-file batch-state.json
```

Przygotowana paczka jest przesyłana dokładnie tak, jak została zbudowana. `--form`, `--offline` i `--max-part-size` nie stosują się obok `--prepared`, a podanie plików faktur razem z tą opcją kończy się błędem, zanim cokolwiek zostanie wysłane.

Artefakt trzyma klucz sesji i treści faktur, obie **otwartym tekstem** pod tą ścieżką. Traktuj `batch-parts` tak, jak plik z danymi uwierzytelniającymi, i usuń go, gdy sesja wsadowa się skończy.

## Wznów przesłanie, które KSeF odrzucił

Gdy magazyn KSeF odrzuci przesłanie, te same dwa pliki niosą naprawę. Nieudane `submit` zostawia stan przerwanej sesji w `--state-file`, a `batch upload` wysyła zapisane części do tej sesji, bez otwierania nowej:

```bash
uv run ksef2 --profile prod-token \
  batch upload --prepared batch-parts \
  --state-file batch-state.json \
  --wait
```

Obie opcje są wymagane. Plik stanu nazywa sesję i jej wstępnie podpisane adresy przesłania. Artefakt niesie dokładnie te części, których oczekuje KSeF, a skrót treści jest z nimi sprawdzany. Odzyskanie nie potrzebuje więc nowych faktur ani nowej paczki. Podłączenie innej paczki do tej sesji kończy się błędem przed przesłaniem. Ponowne `batch submit --prepared` otwiera nową sesję. To też jest dobra odpowiedź, gdy stara sesja już wygasła.

Bez `--state-file` nie ma do czego ponownie podłączyć części. Komunikat błędu nazywa drugą drogę: przygotuj faktury raz, a potem prześlij zapisaną paczkę.

## Przerwana sesja wsadowa nie oznacza, że paczki nie wysłano

`batch submit` zapisuje numer referencyjny sesji do `--state-file`, zanim zacznie sprawdzać status. `invoices send --mode batch` zapisuje swój plik `--receipt` w tej samej chwili. Ctrl-C, wyczerpany `--timeout` i zerwane połączenie kończą więc komendę, gdy paczka jest już wysłana. CLI mówi o tym wprost (`Batch session ... was submitted, but waiting stopped: ... do not submit the invoices again`) i kończy się kodem `130` przy Ctrl-C albo `1` w pozostałych przypadkach.

Zanim prześlesz cokolwiek ponownie, odczytaj, co trzyma KSeF:

```bash
uv run ksef2 --profile prod-token --json \
  batch status --state-file batch-state.json --wait

uv run ksef2 --profile prod-token --json \
  batch list --state-file batch-state.json --failed
```

`batch upload --prepared DIR --state-file FILE` wysyła zapisane części ponownie do tej samej sesji. Zatrzymaną sesję wsadową zwykle kończysz. Nowej sesji wtedy nie otwierasz i żadnej faktury nie trzeba szyfrować drugi raz. Uruchomienie tych samych faktur w nowej sesji wkłada do KSeF drugą kopię każdej faktury. `batch list --failed` mówi, które faktury sesja odrzuciła. To coś innego niż części, których odmówił jej magazyn.

## Odczytaj status i wyniki poszczególnych faktur

Status i lista przyjmują jeden z dwóch sposobów wskazania sesji: `--reference` z numerem sesji albo `--state-file` z plikiem zapisanym przez `batch submit --state-file`. Podaj dokładnie jeden. Oba naraz kończą się komunikatem `Use either --reference or --state-file, not both.` Brak obu kończy się komunikatem `Provide --reference or --state-file.` Sprawdzenie odbywa się przed wysłaniem żądania.

Sam numer tu wystarcza, bo KSeF odpowiada na status sesji i stronę faktur po numerze sesji:

```bash
uv run ksef2 --profile prod-token \
  batch status --reference "$BATCH_REFERENCE" --wait

uv run ksef2 --profile prod-token \
  batch list --reference "$BATCH_REFERENCE" --page-size 100

uv run ksef2 --profile prod-token \
  batch list --state-file batch-state.json --failed
```

Dlatego przerwane `submit` z przykładu powyżej każe uruchomić `batch status --reference REFERENCE`. Utracony plik stanu nie zasłania tego, co trzyma KSeF. `--state-file` robi więcej niż odczyt po numerze. Niesie klucz AES sesji i IV, więc komenda otwiera sesję ponownie i pyta przez nią, bez wywołania API usługi. Tej postaci używaj, gdy plik już masz pod ręką. Trzymaj go przy sesji wsadowej, dopóki KSeF z nią nie skończy. Ponowne otwarcie potrzebuje tych kluczy. Wiersz `state`, który wypisują komendy, to ta sama sesja z zamaskowanymi kluczami, więc nie jest drogą powrotną.

`batch status` czyta to samo podsumowanie co `submit --wait` i może czekać na tych samych zasadach (`--wait`, `--timeout` 120, `--poll-interval` 2). Jego liczniki należą do sesji, więc zakończona sesja nadal może zgłaszać odrzucone faktury. `batch list` mówi które: domyślnie faktury przyjęte, a z `--failed` odrzucone, gdzie kod statusu KSeF i szczegóły wyjaśniają każde odrzucenie. Faktury przyjęte i odrzucone to osobne strony. Przy uzgadnianiu paczki czytaj obie. `--page-size` przyjmuje wartości od 10 do 1000 i domyślnie wynosi 10. `continuation_token` poprzedniej strony przekaż do `--continuation-token`, żeby iść dalej.

Wyniki sesji wsadowej wiąż po `invoice_file_name` i `invoice_hash`. Pozycja na liście do tego nie służy. To pola, które KSeF zwraca przy każdej fakturze. Numer KSeF pojawia się dopiero po przyjęciu faktury.

## Pobierz stronę UPO sesji wsadowej

Sesja wsadowa dostaje UPO stronami, wymienionymi pod `upo.pages[].reference_number` w statusie sesji. Każdą stronę pobierasz jej własnym numerem referencyjnym:

```bash
uv run ksef2 --profile prod-token \
  batch upo \
  --state-file batch-state.json \
  --upo-reference "$UPO_REFERENCE" \
  --out batch-upo-1.xml
```

`--upo-reference` i `--out` są wymagane, plus jeden sposób wskazania sesji. Tutaj oba sposoby naprawdę są wymienne. Żądanie idzie do KSeF z numerem sesji, niezależnie od tego, czy podał go `--reference`, czy `--state-file`. Strona UPO sesji istnieje dopiero po zamknięciu i przetworzeniu sesji, a komenda nigdy nie czeka. Najpierw uruchom `batch status --wait`. Gdy KSeF jeszcze nie wytworzył strony, komenda kończy się kodem `1` pod nagłówkiem `KSeF has not finished processing yet` i każe spróbować później. `download_url_expiration_date` obok każdego numeru referencyjnego to własny termin KSeF dla adresu URL stojącego za tym numerem. Zachowaj pobrany XML.

`invoices upo --upo-dir` pobiera każdą stronę sesji wsadowej jednym wywołaniem, gdy masz plik `--receipt`. `sessions upo --upo-reference` czyta jedną stronę ze świeżego logowania, bez stanu sesji. Do obu wystarcza numer sesji. Ten sam numer czyta wiersz podsumowania przez `sessions invoice-list --type batch --reference`, gdy pliku stanu już nie ma. Zobacz [Sesje i UPO](sessions-and-upo.md).

## Tryb offline

`--offline` deklaruje paczkę jako wystawioną w trybie offline. Faktury powstały poza KSeF i dochodzą do niego z opóźnieniem. CLI przekazuje deklarację dalej, a SDK wstawia ją do żądania sesji wsadowej. Co KSeF z niej zrobi, rozstrzyga KSeF. Deklaracja jest wbudowana w przygotowaną paczkę, dlatego `submit --prepared` ignoruje tę flagę. Takie faktury znajdziesz później, filtrując metadane przez `--invoicing-mode offline`.

## Powiązane strony

- [Przepływy faktur](invoices.md)
- [Sesje interaktywne](online-sessions.md)
- [Sesje i UPO](sessions-and-upo.md)
- [Limity](limits.md)
- [Opis komend](../reference/commands.md)
