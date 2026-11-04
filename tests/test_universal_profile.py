"""One Garasu route policy rendered independently for seven native clients."""
import json
from pathlib import Path
import unittest

import yaml

from scripts.sync_universal_routing import TARGETS, expected, load_policy, native_rules

ROOT = Path(__file__).resolve().parents[1]


class UniversalRoutingContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = load_policy(ROOT)
        cls.desired = expected(ROOT)
        cls.mihomo = yaml.safe_load((ROOT / "release/mihomo/config.yaml").read_text())
        cls.stash = yaml.safe_load((ROOT / "release/stash/config.yaml").read_text())

    def test_exactly_one_canonical_policy_for_seven_formats(self):
        self.assertEqual(self.policy["profiles"], 1)
        self.assertEqual(len(TARGETS), 7)
        for rel, content in self.desired.items():
            with self.subTest(client=rel):
                self.assertEqual((ROOT / rel).read_text(encoding="utf-8"), content)

    def test_no_first_boot_rule_provider_network_dependency(self):
        keys = {"ads", "rkn-domains", "rkn-ips", "ru-ips", "proxy-ips",
                "youtube", "discord", "ai", "crypto", "proxy"}
        for client in (self.mihomo, self.stash):
            providers = client["rule-providers"]
            self.assertEqual(set(providers), keys)
            self.assertTrue(all(item.get("type") == "inline" for item in providers.values()))
            self.assertGreater(len(providers["rkn-domains"]["payload"]), 10000)
            self.assertGreater(len(providers["rkn-ips"]["payload"]), 20000)
            self.assertGreater(len(providers["ru-ips"]["payload"]), 20000)
            self.assertIn("+.003.su", providers["rkn-domains"]["payload"])
            self.assertNotIn("+.xapi.ozon.ru", providers["ads"]["payload"])
            rules = client["rules"]
            self.assertLess(rules.index("RULE-SET,rkn-domains,Garasu"),
                            rules.index("DOMAIN-SUFFIX,ru,DIRECT"))
            self.assertLess(rules.index("RULE-SET,rkn-ips,Garasu,no-resolve"),
                            rules.index("RULE-SET,ru-ips,DIRECT,no-resolve"))
            self.assertEqual(rules[-1], "MATCH,Garasu")

    def test_ad_exemptions_precise(self):
        p = self.policy
        for host in p["ad_exempt_domains"]:
            self.assertNotIn(host, p["_ads_domains"])
        self.assertIn("ads.yandex.ru", p["_ads_domains"])
        self.assertIn("xapi.ozon.ru", p["ad_exempt_domains"])

    def test_shadowrocket_embeds_blocked_snapshots(self):
        text = (ROOT / "release/shadowrocket/config.conf").read_text()
        self.assertNotIn("raw.githubusercontent.com", text.split("[Rule]", 1)[1])
        self.assertIn("DOMAIN-SUFFIX,003.su,PROXY", text)
        self.assertIn("DOMAIN-SUFFIX,ru,DIRECT", text)
        self.assertLess(text.index("DOMAIN-SUFFIX,003.su,PROXY"),
                        text.index("DOMAIN-SUFFIX,su,DIRECT"))
        self.assertNotIn("DOMAIN-SUFFIX,xapi.ozon.ru,REJECT", text)
        self.assertIn("FINAL,PROXY,dns-failed", text)

    def test_singbox_inline_ru_and_blocked(self):
        cfg = json.loads((ROOT / "release/singbox/config.json").read_text())
        sets = {s["tag"]: s for s in cfg["route"]["rule_set"]}
        self.assertEqual(len(sets), 10)
        self.assertTrue(all(x["type"] == "inline" for x in sets.values()))
        self.assertEqual(cfg["route"]["final"], "→ Remnawave")
        rules = cfg["route"]["rules"]
        self.assertLess(next(i for i,r in enumerate(rules) if r.get("rule_set") == ["garasu-rkn-domains"]),
                        next(i for i,r in enumerate(rules) if "ru" in r.get("domain_suffix", [])))
        self.assertGreater(len(sets["garasu-ru-ips"]["rules"][0]["ip_cidr"]), 20000)

    def test_incy_and_happ_share_actual_auto_routing_geodata(self):
        files = [json.loads((ROOT / f"release/{c}/config.json").read_text())
                 for c in ("incy", "happ")]
        self.assertEqual(files[0], files[1])
        for cfg in files:
            self.assertEqual(cfg["Name"], "Garasu")
            self.assertEqual(cfg["GlobalProxy"], "true")
            self.assertEqual(cfg["RouteOrder"], "block-proxy-direct")
            self.assertIn("geosite:banned-ru", cfg["ProxySites"])
            self.assertIn("geoip:blocked-ru", cfg["ProxyIp"])
            self.assertIn("geosite:category-ru", cfg["DirectSites"])
            self.assertIn("geoip:ru", cfg["DirectIp"])
            self.assertTrue(cfg["Geoipurl"].endswith("/geo/geoip.dat"))
            self.assertTrue(cfg["Geositeurl"].endswith("/geo/geosite.dat"))
            self.assertEqual(cfg["BlockSites"], ["geosite:garasu-ads"])

    def test_xray_uses_paired_geo_for_both_actions(self):
        cfg = json.loads((ROOT / "release/xray/config.json").read_text())
        routes = cfg["routing"]["rules"]
        self.assertEqual(routes[-1]["outboundTag"], "proxy")
        self.assertIn("geosite:banned-ru", routes[3]["domain"])
        self.assertIn("geoip:blocked-ru", routes[4]["ip"])
        self.assertIn("geosite:category-ru", routes[5]["domain"])
        self.assertIn("geoip:ru", routes[6]["ip"])
        self.assertTrue(cfg["remnawave"]["addVirtualHostAsOutbound"])


if __name__ == "__main__":
    unittest.main()
