"""Five distinct Remnawave template types from the user's panel screenshot."""
import json
from pathlib import Path
import unittest
import yaml

from scripts.sync_universal_routing import expected, load_policy, provider_sets

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://raw.githubusercontent.com/togahimoko/garasu/main/release/clash/providers/"


class PanelTemplateContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = load_policy(ROOT)
        cls.sets = provider_sets(cls.policy)
        cls.generated = expected(ROOT)

    def test_five_templates_are_distinct_publishable_paths(self):
        paths = {
            "XRAY_JSON": "release/xray/config.json",
            "MIHOMO": "release/mihomo/config.yaml",
            "STASH": "release/stash/config.yaml",
            "SINGBOX": "release/singbox/config.json",
            "CLASH": "release/clash/config.yaml",
        }
        self.assertEqual(len(set(paths.values())), 5)
        for template_type, path in paths.items():
            with self.subTest(template=template_type):
                self.assertIn(path, self.generated)
                self.assertLess((ROOT / path).stat().st_size, 24000)

    def test_classic_clash_has_automatic_route_and_only_remote_yaml_lists(self):
        config = yaml.safe_load((ROOT / "release/clash/config.yaml").read_text())
        text = (ROOT / "release/clash/config.yaml").read_text()
        self.assertEqual(config["mode"], "rule")
        self.assertEqual(text.count("proxies: # LEAVE THIS LINE!"), 2)
        self.assertEqual(len(config["proxy-groups"]), 1)
        self.assertEqual(config["proxy-groups"][0]["type"], "url-test")
        self.assertEqual(config["proxy-groups"][0]["name"], "Garasu")
        self.assertNotIn("include-all", config["proxy-groups"][0])
        self.assertNotIn("remnawave", config["proxy-groups"][0])
        self.assertEqual(config["rules"][-1], "MATCH,Garasu")
        self.assertEqual(set(config["rule-providers"]), set(self.sets))
        for name, provider in config["rule-providers"].items():
            with self.subTest(name=name):
                self.assertEqual(provider["type"], "http")
                self.assertEqual(provider["behavior"], self.sets[name][0])
                self.assertEqual(provider["interval"], 21600)
                self.assertEqual(provider["url"], BASE + name + ".yaml")
                self.assertTrue(provider["path"].endswith(name + ".yaml"))
                self.assertNotIn("payload", provider)
                self.assertNotIn("format", provider)
                rules = yaml.safe_load((ROOT / ("release/clash/providers/" + name + ".yaml")).read_text())
                self.assertEqual(len(rules["payload"]), len(self.sets[name][1]))
                if provider["behavior"] == "domain":
                    self.assertTrue(all(entry.startswith(".") and not entry.startswith("+.")
                                        for entry in rules["payload"]))
        order = config["rules"]
        self.assertLess(order.index("RULE-SET,rkn-domains,Garasu"),
                        order.index("DOMAIN-SUFFIX,ru,DIRECT"))
        self.assertLess(order.index("RULE-SET,rkn-ips,Garasu,no-resolve"),
                        order.index("RULE-SET,ru-ips,DIRECT,no-resolve"))

    def test_clash_not_mihomo_only_extensions(self):
        text = (ROOT / "release/clash/config.yaml").read_text()
        for unsupported in ("format: mrs", "include-all:", "empty-fallback:", "hidden:",
                            "remnawave:", "proxy-server-nameserver:", "tcp-concurrent:",
                            "unified-delay:", "profile:"):
            with self.subTest(option=unsupported):
                self.assertNotIn(unsupported, text)

    def test_xray_uses_compact_binary_geosite_and_geoip(self):
        doc = json.loads((ROOT / "release/xray/config.json").read_text())
        self.assertTrue(doc["remnawave"]["addVirtualHostAsOutbound"])
        self.assertIn("geosite:banned-ru", doc["routing"]["rules"][3]["domain"])
        self.assertIn("geoip:blocked-ru", doc["routing"]["rules"][4]["ip"])


if __name__ == "__main__":
    unittest.main()
