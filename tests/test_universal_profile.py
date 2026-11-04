"""Contract: exactly one canonical Garasu policy, rendered for seven clients."""
import json
from pathlib import Path
import unittest

import yaml

from scripts.sync_universal_routing import expected, load_policy, TARGETS

ROOT = Path(__file__).resolve().parents[1]


class UniversalRoutingContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = load_policy(ROOT)
        cls.desired = expected(ROOT)
        cls.domains = cls.policy["critical_ru_direct_domains"]
        cls.ads = [line.strip() for line in (ROOT / "rules/ads.list").read_text().splitlines()
                   if line.strip() and not line.startswith("#")]

    def test_exactly_one_canonical_policy_for_seven_formats(self):
        self.assertEqual(self.policy["profiles"], 1)
        self.assertEqual(len(TARGETS), 7)
        for rel, content in self.desired.items():
            with self.subTest(client=rel):
                self.assertEqual((ROOT / rel).read_text(encoding="utf-8"), content)

    def test_mihomo_and_stash_have_zero_remote_providers(self):
        for kind in ("mihomo", "stash"):
            with self.subTest(client=kind):
                data = yaml.safe_load((ROOT / f"release/{kind}/config.yaml").read_text())
                providers = data["rule-providers"]
                self.assertEqual(set(providers), {"ads"})
                self.assertEqual(providers["ads"]["type"], "inline")
                self.assertEqual(len(providers["ads"]["payload"]), len(self.ads))
                self.assertEqual(set(providers["ads"]["payload"]), set(self.ads))
                self.assertFalse(any("DOMAIN-SUFFIX,ru,DIRECT" == x for x in data["rules"]))
                self.assertEqual(data["rules"][-1], "MATCH,Garasu")

    def test_bank_direct_ads_reject_unknown_proxy(self):
        data = yaml.safe_load((ROOT / "release/mihomo/config.yaml").read_text())
        rules = data["rules"]
        self.assertIn("DOMAIN-SUFFIX,sberbank.ru,DIRECT", rules)
        self.assertIn("DOMAIN-SUFFIX,gosuslugi.ru,DIRECT", rules)
        self.assertLess(rules.index("RULE-SET,ads,REJECT"),
                        rules.index("DOMAIN-SUFFIX,sberbank.ru,DIRECT"))
        self.assertNotIn("RULE-SET,ru-ips,DIRECT,no-resolve", rules)
        self.assertFalse(any(x.startswith("RULE-SET,rkn") for x in rules))

    def test_shadowrocket_is_fully_embedded(self):
        text = (ROOT / "release/shadowrocket/config.conf").read_text()
        section = text.split("[Rule]\n", 1)[1]
        self.assertNotIn("raw.githubusercontent.com", section)
        self.assertEqual(
            len([x for x in section.splitlines() if x.endswith(",REJECT")]),
            len(self.ads))
        self.assertIn("DOMAIN-SUFFIX,gosuslugi.ru,DIRECT", section)
        self.assertIn("FINAL,PROXY,dns-failed", section)

    def test_singbox_inline_ads_and_proxy_fallback(self):
        cfg = json.loads((ROOT / "release/singbox/config.json").read_text())
        sets = cfg["route"]["rule_set"]
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0]["type"], "inline")
        self.assertEqual(len(sets[0]["rules"][0]["domain_suffix"]), len(self.ads))
        self.assertEqual(cfg["route"]["final"], "→ Remnawave")
        self.assertFalse(any(r.get("domain_suffix") == ["ru"]
                             and r.get("outbound") == "direct"
                             for r in cfg["route"]["rules"]))

    def test_incy_and_happ_have_identical_self_contained_rules(self):
        files = [json.loads((ROOT / f"release/{kind}/config.json").read_text())
                 for kind in ("incy", "happ")]
        self.assertEqual(files[0], files[1])
        for cfg in files:
            self.assertEqual(cfg["Name"], "Garasu")
            self.assertEqual(cfg["GlobalProxy"], "true")
            self.assertEqual(cfg["RouteOrder"], "block-proxy-direct")
            self.assertIn("domain:gosuslugi.ru", cfg["DirectSites"])
            self.assertNotIn("geosite:category-ru", cfg["DirectSites"])
            self.assertNotIn("geoip:ru", cfg["DirectIp"])
            self.assertEqual(len(cfg["BlockSites"]), len(self.ads))
            self.assertEqual(cfg["Geoipurl"], "")
            self.assertEqual(cfg["Geositeurl"], "")

    def test_xray_has_no_remotely_required_geo_categories(self):
        cfg = json.loads((ROOT / "release/xray/config.json").read_text())
        rules = cfg["routing"]["rules"]
        self.assertEqual(rules[-1]["outboundTag"], "proxy")
        self.assertIn("domain:gosuslugi.ru", rules[-2]["domain"])
        self.assertEqual(rules[-3]["outboundTag"], "block")
        self.assertEqual(len(rules[-3]["domain"]), len(self.ads))
        self.assertFalse(any("geosite:" in d for r in rules
                             for d in r.get("domain", [])))
        self.assertTrue(cfg["remnawave"]["addVirtualHostAsOutbound"])


if __name__ == "__main__":
    unittest.main()
