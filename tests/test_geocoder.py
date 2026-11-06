import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import enkoping_geocoder as eg  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "sample_response.json"


class GeocoderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = str(Path(cls.tmp.name) / "test.db")
        cls.count = eg.build(cls.db, json.loads(FIXTURE.read_text(encoding="utf-8")))
        cls.geo = eg.Geocoder(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.geo.close()
        cls.tmp.cleanup()

    def test_build_skips_records_without_coords_or_street(self):
        # 9 rekordów: 8 elementów z adresem, Skolgatan "2;4" rozbity na dwa,
        # relacja bez center i węzeł bez ulicy pominięte.
        self.assertEqual(self.count, 9)

    def test_exact_with_duplicate_node_and_building(self):
        r = self.geo.lookup("Kungsgatan", "12A", "Enköping")
        self.assertEqual(r["status"], "exact")
        self.assertEqual(len(r["results"]), 2)
        self.assertAlmostEqual(r["lat"], 59.6356, places=3)

    def test_case_space_and_diacritics_ignored(self):
        r = self.geo.lookup("  kungsGATAN ", "12 a", "ENKOPING")
        self.assertEqual(r["status"], "exact")
        r = self.geo.lookup("Vastra ringvagen", "16a", "Enkoping")
        self.assertEqual(r["status"], "exact")

    def test_record_without_city_is_exact(self):
        r = self.geo.lookup("Kungsgatan", "5", "Enköping")
        self.assertEqual(r["status"], "exact")

    def test_no_city_match(self):
        r = self.geo.lookup("Storgatan", "3", "Enköping")
        self.assertEqual(r["status"], "no_city_match")
        self.assertEqual({x["city"] for x in r["results"]}, {"Grillby", "Örsundsbro"})

    def test_ambiguous_without_city(self):
        r = self.geo.lookup("Storgatan", "3")
        self.assertEqual(r["status"], "ambiguous")
        self.assertEqual(len(r["results"]), 2)

    def test_city_resolves_ambiguity(self):
        r = self.geo.lookup("Storgatan", "3", "orsundsbro")
        self.assertEqual(r["status"], "exact")
        self.assertEqual(r["results"][0]["city"], "Örsundsbro")

    def test_addr_place(self):
        r = self.geo.lookup("Hacksta", "1", "Enköping")
        self.assertEqual(r["status"], "exact")
        self.assertEqual(r["results"][0]["place"], "Hacksta")

    def test_place_name_given_as_city(self):
        r = self.geo.lookup("Hacksta", "1", "Hacksta")
        self.assertEqual(r["status"], "exact")

    def test_multi_number_tag(self):
        self.assertEqual(self.geo.lookup("Skolgatan", "4", "Enköping")["status"], "exact")

    def test_not_found_with_suggestions(self):
        r = self.geo.lookup("Kungsgtan", "12A", "Enköping")
        self.assertEqual(r["status"], "not_found")
        self.assertIn("Kungsgatan", r["suggestions"])

    def test_cli(self):
        self.assertEqual(eg.main(["lookup", "Kungsgatan", "12A", "Enköping", "--db", self.db]), 0)
        self.assertEqual(eg.main(["lookup", "Nowhere", "1", "--db", self.db]), 1)


if __name__ == "__main__":
    unittest.main()
