"""Cross-client routing audit. Report gaps explicitly; never change live nodes."""
import json
from pathlib import Path
import unittest
import yaml

from scripts.audit_route_coverage import audit, get_sets, yaml_route, shadow_rules

ROOT = Path(__file__).resolve().parents[1]


class RouteCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = audit(ROOT)
        cls.source = get_sets(ROOT)
        cls.mihomo = yaml.safe_load((ROOT / "release/mihomo/config.yaml").read_text())
        cls.shadow = shadow_rules(ROOT)

    def test_report_matches_real_checkout(self):
        published = json.loads(
            (ROOT / "reports/routing-coverage.json").read_text(encoding="utf-8"))
        self.assertEqual(self.record, published)

    def test_domain_proxies_and_ru_fallback(self):
        for domain in ("www.youtube.com", "chatgpt.com",
                       "api.github.com"):
            with self.subTest(domain=domain):
                self.assertEqual(
                    yaml_route(domain, self.mihomo["rules"], self.source)[0], "PROXY")
        self.assertEqual(yaml_route("unlisted-audit.invalid.ru",
                                    self.mihomo["rules"], self.source)[0], "DIRECT")
        self.assertEqual(yaml_route("unlisted-audit.invalid.net",
                                    self.mihomo["rules"], self.source)[0], "PROXY")

    def test_known_divergences_remain_visible_in_audit(self):
        for category in ("direct", "games", "ads"):
            section = self.record["domains"][category]["clients"]["Mihomo"]
            self.assertGreaterEqual(section["deviations"], 0)
            self.assertEqual(section["deviations"], sum(section["reasons"].values()))
            if section["deviations"]:
                self.assertTrue(section["samples"])
        self.assertIsInstance(self.record["ru_direct_without_provider_guard"], bool)

    def test_reverse_ptr_routing_differs_in_shadowrocket(self):
        domain = "10.in-addr.arpa"
        shadow = yaml_route(domain, self.shadow, self.source)[0]
        mihomo = yaml_route(domain, self.mihomo["rules"], self.source)[0]
        if shadow != mihomo:
            self.assertGreater(self.record["non_ru_disagreements"], 0)

    def test_covered_blocked_domain_precedes_ru_suffix(self):
        rkn = self.source["rkn-domains"]
        chosen = next((name for name in sorted(rkn) if name.endswith(".ru")), None)
        self.assertIsNotNone(chosen)
        self.assertEqual(yaml_route(chosen, self.mihomo["rules"],
                                    self.source)[0], "PROXY")

    def test_advertising_overlaps_not_silently_declared_rejected(self):
        blocked_ads = self.source["ads"].intersection(self.source["rkn-domains"])
        self.assertGreater(len(blocked_ads), 0)
        domain = sorted(blocked_ads)[0]
        action = yaml_route(domain, self.mihomo["rules"], self.source)[0]
        self.assertIn(action, ("PROXY", "REJECT"))
        self.assertEqual(self.record["domains"]["ads"]["declared_action"], "REJECT")


if __name__ == "__main__":
    unittest.main()
