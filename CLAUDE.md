# CLAUDE.md

Geokoder adresów z OSM dla dowolnego obszaru administracyjnego. Jeden plik: `osm_geocoder.py`.
Przykładowy obszar, na którym projekt jest testowany: `Enköpings kommun` (Szwecja, admin_level=7).
README ma pozostać ogólne: nie wpisuj tam nazwy przykładowej gminy.

## Komendy

- Testy: `python -m unittest discover -s tests -v`
- Budowa bazy: `python osm_geocoder.py build --area "Enköpings kommun"` (sieć: Overpass API)
- Budowa offline: `python osm_geocoder.py build --from-file overpass.json`
- Wyszukiwanie: `python osm_geocoder.py lookup "<ulica>" "<numer>" "<miasto>"`
- Eksport: `python osm_geocoder.py export addresses.csv` (kolumny: OSM Type, OSM ID, OSM Link, Street Name, Street Number, Postcode, City, Lng, Lat)

## Zasady

- Tylko biblioteka standardowa Pythona, bez zależności.
- Nie commituj danych: `*.db`, `*.csv` i `overpass*.json` są w `.gitignore`.
- Każda zmiana logiki ma test w `tests/test_geocoder.py`; dane testowe w `tests/fixtures/sample_response.json` są ręcznie przygotowane, nie pochodzą z OSM.
- Klucze porównania tworzą `fold()` (wielkość liter, spacje, diakrytyki) i `number_key()`. Zmiana tych funkcji wymaga przebudowy bazy.
- Nie dodawaj masowego geokodowania przez Nominatim ani serwisy komercyjne (regulaminy).

## Stan

- Pobieranie z prawdziwego Overpass nie zostało przetestowane w chmurowym środowisku Claude: overpass-api.de, serwery zapasowe i Geofabrik zrywają tam połączenie. Trzeba je uruchamiać na komputerze użytkownika.
- Możliwe rozszerzenia: import danych Lantmäteriet (SWEREF 99 TM -> WGS84), filtr po kodzie pocztowym.
