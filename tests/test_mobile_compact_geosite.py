"""Compact Happ/INCY geodata stays consistent with Garasu policy."""
import json
from pathlib import Path
import unittest

from scripts import refresh
from scripts.audit_geodata import categories, geosite_values

ROOT = Path(__file__).resolve().parents[1]


def field(number, payload):
    return refresh._protobuf_bytes(number, payload)


def category(name, payload):
    return field(1, field(1, name.encode()) + field(2, b"\x08\x02" + field(2, payload)))


class MobileGeoRouting(unittest.TestCase):
    def test_published_ads_use_exact_curated_binary_category(self):
        binary = geosite_values(categories((ROOT / "geo/geosite.dat").read_bytes())["GARASU-ADS"])
        originals = {row[2:] for row in (ROOT / "rules/ads.list").read_text().splitlines()
                     if row.startswith("+.")}
        exclusions = set(json.loads((ROOT / "policy/universal.json").read_text())["ad_exempt_domains"])
        self.assertEqual(binary, originals - exclusions)
        self.assertTrue(exclusions.isdisjoint(binary))

    def test_future_refresh_can_build_curated_category(self):
        original = category("proxy", b"proxied.test") + category("ads", b"other.test")
        result = refresh.add_native_geosite_categories(
            original, proxy_categories=("proxy",), block_categories=("ads",),
            ru_suffixes=("ru",), canonical_ads=b"+.tracker.test\n+.api.example\n",
            exempt_domains=("api.example",))
        self.assertEqual(geosite_values(categories(result)["GARASU-ADS"]),
                         {"tracker.test"})


if __name__ == "__main__":
    unittest.main()
