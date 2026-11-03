"""Offline routing and delivery contract for native-client candidates."""
import base64
import json
from pathlib import Path
import unittest
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[1]


class NativeUnifiedRouting(unittest.TestCase):
    def test_shadowrocket_does_not_direct_foreign_categories(self):
        for path in (ROOT / "clients/shadowrocket.conf",
                     ROOT / "clients/canary/shadowrocket.conf"):
            with self.subTest(path=path):
                profile = path.read_text()
                self.assertIn("MANAGED-CONFIG interval=21600", profile)
                rules = profile.split("[Rule]", 1)[1]
                self.assertNotIn("games.list,DIRECT", rules)
                self.assertNotIn("direct.list,DIRECT", rules)
                self.assertNotIn("direct-ips.list,DIRECT", rules)
                self.assertLess(rules.index("rkn-ips.list,PROXY"),
                                rules.index("ru-ips.list,DIRECT"))
                self.assertIn("DOMAIN-SUFFIX,ru,DIRECT", rules)
                self.assertIn("FINAL,PROXY", rules)

    def test_happ_incy_only_direct_private_and_ru(self):
        for name in ("happ", "incy"):
            with self.subTest(name=name):
                doc = json.loads((ROOT / f"clients/{name}.json").read_text())
                self.assertEqual(doc["DirectSites"],
                                 ["geosite:private", "geosite:category-ru"])
                self.assertEqual(doc["DirectIp"], ["geoip:private", "geoip:ru"])
                self.assertIn("geosite:banned-ru", doc["ProxySites"])
                self.assertIn("geoip:blocked-ru", doc["ProxyIp"])

    def test_quantumultx_foreign_game_and_direct_resources_are_not_direct(self):
        for name in ("games", "direct", "direct-ips"):
            text = (ROOT / f"rules/quantumultx/{name}.list").read_text()
            self.assertNotIn(", direct", text.lower(), name)
        self.assertIn("host-suffix, steampowered.com, proxy",
                      (ROOT / "rules/quantumultx/games.list").read_text())

    def test_delivery_keeps_personal_nodes_and_no_broad_direct_filters(self):
        links = json.loads((ROOT / "install/links.json").read_text())
        self.assertTrue(links["shadowrocket"].startswith("shadowrocket://config/add/https://"))
        self.assertTrue(links["incy"].startswith("incy://autorouting/onadd/https://"))
        happ = json.loads(base64.b64decode(links["happ"].split("/onadd/", 1)[1], validate=True))
        self.assertEqual(happ, json.loads((ROOT / "clients/happ.json").read_text()))
        qx = parse_qs(urlsplit(links["quantumultx"]).query)["remote-resource"][0]
        filters = json.loads(qx)["filter_remote"]
        for name in ("games", "direct", "direct-ips"):
            self.assertNotIn("Garasu-" + name, " ".join(filters))
        self.assertIn("rkn-ips", links["surge_rulesets"])

    def test_surge_loon_qx_integration_snippets_have_final_proxy(self):
        for name in ("surge", "loon", "quantumultx"):
            with self.subTest(name=name):
                text = (ROOT / f"clients/{name}-integration.example").read_text()
                self.assertIn("{{PERSONAL_PROXY_POLICY}}", text)
                self.assertLess(text.index("rkn-domains.list"), text.index("ru-ips.list"))
                self.assertLess(text.index("ru-ips.list"), text.index("FINAL"))
                self.assertNotIn("games.list", text)
                self.assertNotIn("direct.list", text)


if __name__ == "__main__":
    unittest.main()
