# CLAUDE.md

Geokoder adresów gminy Enköping na danych OSM. Jeden plik: `enkoping_geocoder.py`.

## Komendy

- Testy: `python -m unittest discover -s tests -v`
- Budowa bazy: `python enkoping_geocoder.py build` (sieć: Overpass API)
- Budowa offline: `python enkoping_geocoder.py build --from-file overpass.json`
- Wyszukiwanie: `python enkoping_geocoder.py lookup "<ulica>" "<numer>" "<miasto>"`

## Zasady

- Tylko biblioteka standardowa Pythona, bez zależności.
- Nie commituj danych: `*.db` i `overpass*.json` są w `.gitignore`.
- Każda zmiana logiki dopasowania ma test w `tests/test_geocoder.py`; dane testowe w `tests/fixtures/sample_response.json` są ręcznie przygotowane, nie pochodzą z OSM.
- Klucze porównania tworzą `fold()` (wielkość liter, spacje, diakrytyki) i `number_key()`. Zmiana tych funkcji wymaga przebudowy bazy.
- Nie dodawaj masowego geokodowania przez Nominatim ani serwisy komercyjne (regulaminy).

## Stan

- Pobieranie z prawdziwego Overpass nie zostało jeszcze przetestowane (środowisko, w którym powstał kod, nie miało dostępu do overpass-api.de). Liczba adresów dla gminy nieznana.
- Możliwe rozszerzenia: import danych Lantmäteriet (SWEREF 99 TM -> WGS84), filtr po kodzie pocztowym.
