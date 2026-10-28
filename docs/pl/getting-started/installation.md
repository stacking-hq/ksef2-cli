---
title: Instalacja
description: Zainstaluj albo uruchom KSeF2 CLI przez uv i sprawdź dostępne grupy komend.
---

## Wymagania

KSeF2 CLI wymaga Pythona 3.12 albo nowszego.

CLI zależy od opublikowanego SDK `ksef2` w zakresie `>=1.1,<2`. Wersja 1.1 zawiera poprawki pobierania certyfikatów i odczytu kodów PDF w trybie offline. Instalacja z PyPI:

```bash
uv tool install ksef2-cli
# or
pipx install ksef2-cli
```

Do pracy z kopii repozytorium użyj `uv`:

```bash
uv sync
uv run ksef2 --help
```

Dla zainstalowanego pakietu możesz użyć dowolnego z dwóch programów:

```bash
ksef2 --help
ksef2-cli --help
```

Oba punkty wejścia uruchamiają tę samą aplikację Typer.

## Sprawdź, jakie komendy są dostępne

Komenda główna wypisuje najpierw opcje globalne, a potem grupy komend:

```bash
uv run ksef2 --help
```

`--version` podaje CLI i SDK, które CLI wczytało, po jednej pozycji w wierszu. CLI czyta tę opcję przed plikiem konfiguracji, więc odpowiada także wtedy, gdy pliku brakuje albo jest uszkodzony. W trybie `--json` wypisuje ten sam zwykły tekst:

```bash
uv run ksef2 --version
```

```text
ksef2-cli 1.0.0
ksef2 1.1.0
```

Pomoc grupy pokazuje konkretny przepływ:

```bash
uv run ksef2 invoices --help
uv run ksef2 online --help
uv run ksef2 batch --help
```

`--json` daje wynik, który da się przetworzyć w skrypcie:

```bash
uv run ksef2 --json config path
```

## Wybór środowiska

Domyślne środowisko to `test`. Gdy potrzebujesz `demo` albo `production`, podaj `--env` przed grupą komend:

```bash
uv run ksef2 --env production --help
```

Dozwolone wartości:

- `production`
- `demo`
- `test`

Gdy nie podasz `--env`, środowisko bierze się z profilu, który ma wtedy pierwszeństwo przed wartością domyślną. Profil z `environment = "production"` nadal uwierzytelnia się w środowisku produkcyjnym. `--env` w wierszu polecenia nadpisuje ten profil na czas jednego wywołania:

```bash
uv run ksef2 --profile prod-client --env test --json auth login
```

Ta sama kolejność dotyczy każdej komendy, która korzysta ze środowiska, także `peppol providers`. Ta komenda w ogóle nie potrzebuje danych uwierzytelniających, więc najłatwiej tu przeoczyć ciche przejście na wartość domyślną.

## Generowanie PDF

Dwie komendy zamieniają XML faktury na PDF: `invoices export-pdf` i `fa3 render --pdf`. Renderują przez WeasyPrint. To dodatkowa zależność opcjonalna i nie instaluje się razem z CLI:

```bash
uv tool install "ksef2-cli[pdf]"   # installed CLI
uv sync --extra pdf                # project checkout
```

W Linuksie WeasyPrint potrzebuje też bibliotek systemowych:

```bash
sudo apt-get install libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0 libharfbuzz-subset0
```

W macOS te same biblioteki pochodzą z Homebrew. Gdy są zainstalowane, a ładowanie i tak się nie udaje, wskaż dynamicznemu loaderowi katalog Homebrew przy każdej komendzie PDF:

```bash
brew install pango
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run ksef2 fa3 render --in invoice.xml --pdf invoice.pdf
```

`/usr/local/lib` to odpowiednik tej ścieżki na Macach z procesorem Intela. Gdy zależności brakuje, obie komendy PDF podają polecenie instalacji, a w macOS także ścieżkę zapasową z przykładu powyżej. Pozostałe komendy działają bez tych bibliotek.

Bez dodatku CLI nadal się instaluje i każda inna komenda działa. Dwie komendy PDF wypisują wtedy polecenie instalacji z przykładu powyżej i nie renderują pliku.

## Następne kroki

- [Przejdź szybki start](quickstart.md)
- [Skonfiguruj uwierzytelnianie](../guides/authentication.md)
- [Ustaw lokalne wartości domyślne](../guides/configuration.md)
