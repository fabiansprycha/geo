# geo

Lokalny geokoder adresów z OpenStreetMap dla dowolnego obszaru administracyjnego
(np. gminy). Skrypt jednym zapytaniem pobiera wszystkie adresy obszaru przez
Overpass API i zapisuje je w bazie SQLite. Twoje narzędzie odpytuje potem tylko
tę bazę, bez sieci. Adresy można też wyeksportować do CSV.

Wymaga wyłącznie Pythona 3.9+ (biblioteka standardowa).

## Użycie

```bash
python osm_geocoder.py build --area "<nazwa granicy w OSM>"      # tworzy addresses.db
python osm_geocoder.py lookup "<ulica>" "<numer>" "<miasto>"
python osm_geocoder.py export addresses.csv
```

`--area` to dokładna wartość tagu `name` granicy w OSM (sprawdzisz ją na
openstreetmap.org, klikając obszar). Domyślnie szukana jest granica z
`admin_level=7`; inny poziom podasz przez `--admin-level`, a `--admin-level ""`
wyłącza ten filtr. Jeśli `build` zapisze 0 adresów, nazwa albo poziom się nie zgadzają.

Inne opcje `build`:

- `--save-raw overpass.json` zapisuje surową odpowiedź, `--from-file overpass.json` buduje z niej bazę bez sieci.
- `--url` pozwala użyć innego serwera Overpass (np. `https://overpass.kumi.systems/api/interpreter`).
- `--print-query` wypisuje zapytanie, które można też wkleić do Overpass Turbo.
- `--db` zmienia ścieżkę bazy (domyślnie `addresses.db`; to samo dla `lookup` i `export`).

Z Pythona:

```python
from osm_geocoder import Geocoder
geo = Geocoder("addresses.db")
geo.lookup("<ulica>", "12A", "<miasto>")
```

## Eksport do CSV

`export` zapisuje plik UTF-8 z kolumnami:

| Kolumna | Zawartość |
|---|---|
| `OSM Type` | Typ obiektu OSM: `node` (punkt, np. wejście do budynku), `way` (obrys budynku lub działki; współrzędne to jego środek), `relation` (obiekt złożony) |
| `OSM ID` | Numer obiektu w OSM; razem z typem jednoznacznie go identyfikuje |
| `OSM Link` | Podgląd obiektu na openstreetmap.org |
| `Street Name` | `addr:street`, a gdy go brak, `addr:place` |
| `Street Number` | `addr:housenumber` |
| `Postcode` | `addr:postcode` (może być puste) |
| `City` | `addr:city` (może być puste) |
| `Lng`, `Lat` | WGS84; dla budynków środek obrysu |

Tag z kilkoma numerami (`2;4`) daje kilka wierszy z tym samym `OSM ID`.

## Wyniki wyszukiwania

`lookup` zwraca JSON z polem `status`:

| Status | Znaczenie |
|---|---|
| `exact` | Znaleziono adres (`lat`, `lon`). Rekordy bez `addr:city` też tu trafiają, bo OSM często go nie podaje. |
| `no_city_match` | Ulica i numer istnieją, ale w innej miejscowości; `results` je wymienia. |
| `ambiguous` | Ten sam adres w kilku miejscach oddalonych o ponad 300 m; trzeba wybrać z `results`. |
| `not_found` | Brak adresu; `suggestions` podpowiada podobne nazwy ulic (literówki). |

Kod wyjścia CLI: 0 dla `exact`/`ambiguous`, 1 dla pozostałych, 2 gdy brak bazy.

## Dopasowanie

- Wielkość liter, nadmiarowe spacje i znaki diakrytyczne są ignorowane (`o` = `ö`, `a` = `å`).
- Numery są tekstem bez spacji: `16 A` = `16a`.
- Adresy wiejskie bez ulicy (`addr:place`) wyszukuje się, podając nazwę miejscowości lub gospodarstwa jako ulicę. Nazwa z `addr:place` jest też akceptowana jako miasto.
- Węzeł wejścia i budynek z tym samym adresem (bliżej niż 300 m) są traktowane jako jeden adres.

## Ograniczenia danych

Kompletność adresów w OSM zależy od kraju i regionu i bywa niska. Do pełnego
pokrycia potrzebne są oficjalne rejestry adresów (w Szwecji Lantmäteriet,
w SWEREF 99 TM, EPSG:3006). Nie uzupełniaj braków masowym odpytywaniem Nominatim
ani serwisów komercyjnych, bo zabraniają tego ich regulaminy.

## Licencja

Dane: © współtwórcy OpenStreetMap, licencja ODbL 1.0. Baza i CSV zbudowane z OSM
są bazami pochodnymi i podlegają ODbL. Licencja kodu: do ustalenia.

## Testy

```bash
python -m unittest discover -s tests -v
```
