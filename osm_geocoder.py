#!/usr/bin/env python3
"""Lokalny geokoder adresów dla wybranego obszaru administracyjnego, oparty na danych OSM.

Pobiera wszystkie obiekty z addr:housenumber w granicy obszaru (np. gminy)
przez Overpass API, zapisuje je w SQLite, a potem wyszukuje współrzędne
po ulicy (lub addr:place), numerze i miejscowości albo eksportuje do CSV.
Tylko biblioteka standardowa Pythona.

Użycie:
    python osm_geocoder.py build --area "<nazwa obszaru w OSM>" [--admin-level 7] [--db addresses.db]
    python osm_geocoder.py lookup "<ulica>" "<numer>" "<miasto>" [--db addresses.db]
    python osm_geocoder.py export addresses.csv [--db addresses.db]
"""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import math
import re
import sqlite3
import sys
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_DB = "addresses.db"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
DEFAULT_ADMIN_LEVEL = "7"  # w Szwecji gmina (kommun) ma admin_level=7
USER_AGENT = "osm-geocoder/1.0 (https://github.com/fabiansprycha/geo)"
# OSM Type: node = punkt (np. wejście), way = obrys budynku/działki (współrzędne to jego środek),
# relation = złożony obiekt. OSM ID: numer obiektu danego typu,
# podgląd: https://www.openstreetmap.org/<OSM Type>/<OSM ID>
CSV_COLUMNS = ["OSM Type", "OSM ID", "OSM Link", "Street Name", "Street Number", "Postcode", "City", "Lng", "Lat"]
# Rekordy tego samego adresu bliżej niż ten próg traktujemy jako jeden adres
# (np. węzeł wejścia i obrys budynku z tymi samymi tagami).
SAME_PLACE_METERS = 300.0



def build_query(area: str, admin_level: str = DEFAULT_ADMIN_LEVEL) -> str:
    area = area.replace("\\", "\\\\").replace('"', '\\"')
    level = f'["admin_level"="{admin_level}"]' if admin_level else ""
    return (
        "[out:json][timeout:600];\n"
        f'area["name"="{area}"]{level}->.a;\n'
        'nwr["addr:housenumber"](area.a);\n'
        "out center tags;\n"
    )

SCHEMA = """
CREATE TABLE IF NOT EXISTS addresses (
    id INTEGER PRIMARY KEY,
    osm_type TEXT NOT NULL,
    osm_id INTEGER NOT NULL,
    street TEXT,
    place TEXT,
    housenumber TEXT NOT NULL,
    postcode TEXT,
    city TEXT,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    name_key TEXT NOT NULL,
    number_key TEXT NOT NULL,
    city_key TEXT NOT NULL,
    place_key TEXT NOT NULL,
    UNIQUE (osm_type, osm_id, name_key, number_key)
);
CREATE INDEX IF NOT EXISTS idx_lookup ON addresses (name_key, number_key);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


# --- normalizacja ---------------------------------------------------------

def fold(text: str | None) -> str:
    """Klucz porównania: bez wielkości liter, nadmiarowych spacji i diakrytyków.

    "  Enköping " -> "enkoping", "Västra  Ringvägen" -> "vastra ringvagen".
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("ß", "ss").replace("ø", "o").replace("æ", "ae").replace("ł", "l")
    return re.sub(r"\s+", " ", text).strip().casefold()


def number_key(number: str | None) -> str:
    """Numer jako tekst: "16 a" -> "16a", "250 - 10" -> "250-10"."""
    return re.sub(r"\s+", "", fold(number))


def split_numbers(raw: str) -> list[str]:
    """OSM czasem ma kilka numerów w jednym tagu: "3;5" lub "3,5"."""
    parts = [p.strip() for p in re.split(r"[;,]", raw) if p.strip()]
    return parts or [raw.strip()]


# --- pobieranie i budowa bazy --------------------------------------------

def fetch_overpass(query: str, url: str = OVERPASS_URL, timeout: int = 660) -> dict:
    data = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def parse_elements(payload: dict):
    """Zwraca krotki gotowe do INSERT dla każdego adresu z odpowiedzi Overpass."""
    for el in payload.get("elements", []):
        tags = el.get("tags") or {}
        raw_number = tags.get("addr:housenumber")
        if not raw_number:
            continue
        if "lat" in el and "lon" in el:
            lat, lon = el["lat"], el["lon"]
        elif "center" in el:
            lat, lon = el["center"]["lat"], el["center"]["lon"]
        else:
            continue
        street = tags.get("addr:street")
        place = tags.get("addr:place")
        name = street or place
        if not name:
            continue
        city = tags.get("addr:city")
        for number in split_numbers(raw_number):
            yield (
                el.get("type", "node"), el["id"], street, place, number,
                tags.get("addr:postcode"), city, lat, lon,
                fold(name), number_key(number), fold(city), fold(place),
            )


def build(db_path: str, payload: dict) -> int:
    path = Path(db_path)
    tmp = path.with_name(path.name + ".tmp")
    if tmp.exists():
        tmp.unlink()
    con = sqlite3.connect(tmp)
    try:
        con.executescript(SCHEMA)
        con.executemany(
            "INSERT OR IGNORE INTO addresses (osm_type, osm_id, street, place, housenumber,"
            " postcode, city, lat, lon, name_key, number_key, city_key, place_key)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            parse_elements(payload),
        )
        count = con.execute("SELECT COUNT(*) FROM addresses").fetchone()[0]
        con.execute("INSERT OR REPLACE INTO meta VALUES ('osm_base', ?)",
                    ((payload.get("osm3s") or {}).get("timestamp_osm_base", ""),))
        con.commit()
    finally:
        con.close()
    tmp.replace(path)  # podmiana atomowa: stara baza działa do końca budowy
    return count


def export_csv(db_path: str, csv_path: str) -> int:
    """Zapisuje wszystkie adresy z bazy do CSV (UTF-8, przecinek)."""
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            "SELECT osm_type, osm_id, COALESCE(street, place), housenumber, postcode, city, lon, lat"
            " FROM addresses ORDER BY COALESCE(street, place), number_key, osm_type, osm_id")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(CSV_COLUMNS)
            n = 0
            for osm_type, osm_id, name, number, postcode, city, lon, lat in rows:
                w.writerow([osm_type, osm_id, f"https://www.openstreetmap.org/{osm_type}/{osm_id}",
                            name, number, postcode or "", city or "", lon, lat])
                n += 1
    finally:
        con.close()
    return n


# --- wyszukiwanie ----------------------------------------------------------

def _distance_m(a: dict, b: dict) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371000 * math.asin(math.sqrt(h))


def _clusters(rows: list[dict]) -> list[list[dict]]:
    """Grupuje rekordy leżące blisko siebie (ten sam adres zmapowany kilka razy)."""
    groups: list[list[dict]] = []
    for row in rows:
        for g in groups:
            if _distance_m(g[0], row) <= SAME_PLACE_METERS:
                g.append(row)
                break
        else:
            groups.append([row])
    return groups


def _public(row: dict) -> dict:
    keys = ("street", "place", "housenumber", "postcode", "city", "lat", "lon", "osm_type", "osm_id")
    return {k: row[k] for k in keys}


class Geocoder:
    def __init__(self, db_path: str = DEFAULT_DB):
        if not Path(db_path).exists():
            raise FileNotFoundError(f"Brak bazy {db_path}. Uruchom najpierw: build")
        self.con = sqlite3.connect(db_path)
        self.con.row_factory = sqlite3.Row

    def close(self) -> None:
        self.con.close()

    def suggest(self, street: str, limit: int = 5) -> list[str]:
        names = {}
        for r in self.con.execute("SELECT DISTINCT name_key, COALESCE(street, place) AS n FROM addresses"):
            names.setdefault(r["name_key"], r["n"])
        keys = difflib.get_close_matches(fold(street), list(names), n=limit, cutoff=0.6)
        return [names[k] for k in keys]

    def lookup(self, street: str, number: str, city: str | None = None) -> dict:
        rows = [dict(r) for r in self.con.execute(
            "SELECT * FROM addresses WHERE name_key = ? AND number_key = ? ORDER BY osm_type, osm_id",
            (fold(street), number_key(number)))]
        query = {"street": street, "number": number, "city": city}

        if not rows:
            return {"status": "not_found", "query": query, "suggestions": self.suggest(street)}

        ck = fold(city)
        if ck:
            in_city = [r for r in rows if ck in (r["city_key"], r["place_key"])]
            no_city = [r for r in rows if not r["city_key"]]
            candidates = in_city or no_city
            if not candidates:
                return {"status": "no_city_match", "query": query,
                        "results": [_public(r) for r in rows]}
        else:
            candidates = rows

        groups = _clusters(candidates)
        if len(groups) == 1:
            best = groups[0][0]
            return {"status": "exact", "query": query, "lat": best["lat"], "lon": best["lon"],
                    "results": [_public(r) for r in groups[0]]}
        return {"status": "ambiguous", "query": query,
                "results": [_public(g[0]) for g in groups]}


# --- CLI -------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="pobierz adresy z Overpass i zbuduj bazę SQLite")
    b.add_argument("--area", help='nazwa granicy w OSM (tag name), np. gminy')
    b.add_argument("--admin-level", default=DEFAULT_ADMIN_LEVEL,
                   help='admin_level granicy (domyślnie 7); pusty "" = bez filtra')
    b.add_argument("--db", default=DEFAULT_DB)
    b.add_argument("--url", default=OVERPASS_URL, help="adres serwera Overpass")
    b.add_argument("--from-file", help="zbuduj z zapisanej odpowiedzi Overpass (JSON) zamiast pobierać")
    b.add_argument("--save-raw", help="zapisz surową odpowiedź Overpass do pliku")
    b.add_argument("--print-query", action="store_true", help="wypisz zapytanie Overpass i zakończ")

    l = sub.add_parser("lookup", help="znajdź współrzędne adresu")
    l.add_argument("street", help="ulica albo nazwa miejscowości/gospodarstwa (addr:place)")
    l.add_argument("number")
    l.add_argument("city", nargs="?")
    l.add_argument("--db", default=DEFAULT_DB)

    e = sub.add_parser("export", help="zapisz adresy z bazy do pliku CSV")
    e.add_argument("csv", help="ścieżka pliku CSV")
    e.add_argument("--db", default=DEFAULT_DB)

    args = p.parse_args(argv)

    if args.cmd == "export":
        if not Path(args.db).exists():
            print(f"Brak bazy {args.db}. Uruchom najpierw: build", file=sys.stderr)
            return 2
        n = export_csv(args.db, args.csv)
        print(f"Zapisano {n} adresów w {args.csv}")
        return 0

    if args.cmd == "build":
        if not args.from_file and not args.area:
            p.error("build wymaga --area (albo --from-file)")
        query = build_query(args.area, args.admin_level) if args.area else ""
        if args.print_query:
            print(query)
            return 0
        if args.from_file:
            payload = json.loads(Path(args.from_file).read_text(encoding="utf-8"))
        else:
            print(f"Pobieram adresy z {args.url} ...", file=sys.stderr)
            payload = fetch_overpass(query, args.url)
        if args.save_raw:
            Path(args.save_raw).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        count = build(args.db, payload)
        print(f"Zapisano {count} adresów w {args.db}")
        if count == 0:
            print("0 adresów: sprawdź w OSM nazwę (--area) i admin_level granicy.", file=sys.stderr)
            return 1
        return 0

    try:
        geo = Geocoder(args.db)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    result = geo.lookup(args.street, args.number, args.city)
    geo.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in ("exact", "ambiguous") else 1


if __name__ == "__main__":
    sys.exit(main())
