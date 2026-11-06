# enkoping-geocoder

Lokalny geokoder adresów w gminie Enköping (Szwecja). Skrypt jednym zapytaniem
pobiera wszystkie adresy gminy z OpenStreetMap przez Overpass API i zapisuje je
w bazie SQLite. Twoje narzędzie odpytuje potem tylko tę bazę, bez sieci.

Wymaga wyłącznie Pythona 3.9+ (biblioteka standardowa).

## Użycie

```bash
python enkoping_geocoder.py build                     # pobiera z Overpass, tworzy enkoping.db
python enkoping_geocoder.py lookup "Kungsgatan" "12A" "Enköping"
```

Przydatne opcje `build`:

- `--save-raw overpass.json` zapisuje surową odpowiedź, `--from-file overpass.json` buduje z niej bazę bez sieci.
- `--url` pozwala użyć innego serwera Overpass (np. `https://overpass.kumi.systems/api/interpreter`).
- `--print-query` wypisuje zapytanie, które można też wkleić do Overpass Turbo.

Jeśli `build` zapisze 0 adresów, sprawdź w OSM nazwę i `admin_level` granicy gminy
(stałe `MUNICIPALITY` i `ADMIN_LEVEL` w skrypcie).

Z Pythona:

```python
from enkoping_geocoder import Geocoder
geo = Geocoder("enkoping.db")
geo.lookup("Kungsgatan", "12A", "Enköping")
```

## Wyniki

`lookup` zwraca JSON z polem `status`:

| Status | Znaczenie |
|---|---|
| `exact` | Znaleziono adres (`lat`, `lon`). Rekordy bez `addr:city` też tu trafiają, bo OSM często go nie podaje. |
| `no_city_match` | Ulica i numer istnieją, ale w innej miejscowości; `results` je wymienia. |
| `ambiguous` | Ten sam adres w kilku miejscach oddalonych o ponad 300 m; trzeba wybrać z `results`. |
| `not_found` | Brak adresu; `suggestions` podpowiada podobne nazwy ulic (literówki). |

Kod wyjścia CLI: 0 dla `exact`/`ambiguous`, 1 dla pozostałych, 2 gdy brak bazy.

## Dopasowanie

- Wielkość liter, nadmiarowe spacje i znaki diakrytyczne są ignorowane: `enkoping` = `Enköping`, `vastra ringvagen` = `Västra Ringvägen`.
- Numery są tekstem bez spacji: `16 A` = `16a`. Tag z kilkoma numerami (`2;4`) daje osobne rekordy.
- Adresy wiejskie bez ulicy (`addr:place`) wyszukuje się, podając nazwę miejscowości lub gospodarstwa jako ulicę. Nazwa z `addr:place` jest też akceptowana jako miasto.
- Węzeł wejścia i budynek z tym samym adresem (bliżej niż 300 m) są traktowane jako jeden adres.

## Ograniczenia danych

OSM w Szwecji ma duże braki w adresach. Pełne dane adresowe (Belägenhetsadress)
udostępnia Lantmäteriet na wniosek; mogą być w SWEREF 99 TM (EPSG:3006) i wymagać
przeliczenia na WGS84. Nie uzupełniaj braków masowym odpytywaniem Nominatim ani
serwisów komercyjnych, bo zabraniają tego ich regulaminy.

## Licencja

Dane: © współtwórcy OpenStreetMap, licencja ODbL 1.0. Baza zbudowana z OSM jest
bazą pochodną i podlega ODbL. Licencja kodu: do ustalenia.

## Testy

```bash
python -m unittest discover -s tests -v
```
