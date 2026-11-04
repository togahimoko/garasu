"""One Garasu route policy rendered independently for seven native clients."""
import json
from pathlib import Path
import unittest

import yaml

from scripts.sync_universal_routing import TARGETS, PROVIDERS_BASE, SINGBOX_BASE, expected, load_policy, native_rules, provider_sets

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

    def test_every_large_ruleset_is_remote_and_matches_source(self):
        keys = set(provider_sets(self.policy))
        for client, fmt in ((self.mihomo, "mihomo"), (self.stash, "stash")):
            providers = client["rule-providers"]
            self.assertEqual(set(providers), keys)
            self.assertLess(len((ROOT / ("release/" + fmt + "/config.yaml")).read_bytes()), 12000)
            for name, provider in providers.items():
                with self.subTest(client=fmt, provider=name):
                    self.assertEqual(provider["url"], PROVIDERS_BASE + name + ".txt")
                    self.assertEqual(provider["format"], "text")
                    self.assertEqual(provider["behavior"], provider_sets(self.policy)[name][0])
                    self.assertNotIn("payload", provider)
                    self.assertEqual((provider.get("type") or "http"), "http")
        self.assertIn("+.003.su", (ROOT / "release/providers/rkn-domains.txt").read_text())
        self.assertNotIn("+.xapi.ozon.ru", (ROOT / "release/providers/ads.txt").read_text())
        self.assertGreater(len((ROOT / "release/providers/rkn-ips.txt").read_text().splitlines()),20000)
        for rules in (self.mihomo["rules"], self.stash["rules"]):
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

    def test_shadowrocket_uses_ordered_remote_sets(self):
        text = (ROOT / "release/shadowrocket/config.conf").read_text()
        self.assertLess(len(text.encode()), 8000)
        self.assertIn("DOMAIN-SET," + PROVIDERS_BASE + "ads.txt,REJECT", text)
        self.assertIn("DOMAIN-SET," + PROVIDERS_BASE + "rkn-domains.txt,PROXY", text)
        self.assertIn("RULE-SET,https://raw.githubusercontent.com/togahimoko/garasu/main/rules/rkn-ips.list,PROXY", text)
        self.assertLess(text.index("rkn-domains.txt,PROXY"), text.index("DOMAIN-SUFFIX,ru,DIRECT"))
        self.assertIn("FINAL,PROXY,dns-failed", text)

    def test_singbox_remote_source_sets_and_proxy_downloader(self):
        cfg = json.loads((ROOT / "release/singbox/config.json").read_text())
        self.assertLess(len((ROOT / "release/singbox/config.json").read_bytes()), 12000)
        sets = {s["tag"]: s for s in cfg["route"]["rule_set"]}
        self.assertEqual(len(sets), 10)
        for key, (behavior, values) in provider_sets(self.policy).items():
            item = sets["garasu-" + key]
            self.assertEqual(item["type"], "remote")
            self.assertEqual(item["format"], "source")
            self.assertEqual(item["url"], SINGBOX_BASE + key + ".json")
            self.assertEqual(item["http_client"], "garasu-rules")
            src = json.loads((ROOT / "release/singbox/rules" / (key+".json")).read_text())
            self.assertEqual(src["rules"][0]["domain_suffix" if behavior=="domain" else "ip_cidr"],values)
        self.assertEqual(cfg["route"]["default_http_client"], "garasu-rules")
        self.assertEqual(next(x for x in cfg["http_clients"] if x["tag"]=="garasu-rules")["detour"],
                         "→ Remnawave")
        self.assertTrue(cfg["experimental"]["cache_file"]["enabled"])
        self.assertEqual(cfg["route"]["final"], "→ Remnawave")
        rules = cfg["route"]["rules"]
        self.assertLess(next(i for i,r in enumerate(rules) if r.get("rule_set")==["garasu-rkn-domains"]),
                        next(i for i,r in enumerate(rules) if "ru" in r.get("domain_suffix",[])))

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
        self.assertEqual(routes[2]["domain"], ["geosite:garasu-ads"])
        self.assertIn("geosite:banned-ru", routes[3]["domain"])
        self.assertIn("geoip:blocked-ru", routes[4]["ip"])
        self.assertIn("geosite:category-ru", routes[5]["domain"])
        self.assertIn("geoip:ru", routes[6]["ip"])
        self.assertTrue(cfg["remnawave"]["addVirtualHostAsOutbound"])


if __name__ == "__main__":
    unittest.main()
