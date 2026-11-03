"""Contract checks for core routing templates; native app and network gates remain separate."""
import json
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
YAML = [
    "clients/mihomo-remnawave.yaml", "clients/stash-remnawave.yaml",
    "clients/canary/mihomo-remnawave.yaml", "clients/canary/stash-remnawave.yaml",
]
SINGBOX = [
    "clients/singbox-remnawave.json", "clients/singbox-remnawave-1.14.json",
    "clients/canary/singbox-remnawave-1.14.json",
    "clients/experimental/singbox-remnawave-1.14-auto.json",
]
RU_SUFFIXES = {"ru", "su", "moscow", "xn--p1ai", "xn--p1acf",
               "xn--80asehdb", "xn--c1avg", "xn--80aswg",
               "xn--80adxhks", "xn--d1acj3b"}


class UnifiedCoreRoutes(unittest.TestCase):
    def test_mihomo_and_stash_blocked_first_ru_direct_foreign_proxy(self):
        for path in YAML:
            with self.subTest(path=path):
                doc = yaml.safe_load((ROOT / path).read_text())
                rules = doc["rules"]
                self.assertLess(rules.index("RULE-SET,rkn-domains,Garasu"),
                                rules.index("DOMAIN-SUFFIX,ru,DIRECT"))
                self.assertLess(rules.index("RULE-SET,rkn-ips,Garasu"),
                                rules.index("RULE-SET,ru-ips,DIRECT,no-resolve"))
                self.assertLess(rules.index("RULE-SET,proxy-ips,Garasu"),
                                rules.index("DOMAIN-SUFFIX,ru,DIRECT"))
                self.assertEqual(rules[-1], "MATCH,Garasu")
                self.assertFalse(any(x.startswith("RULE-SET," + name + ",DIRECT")
                                     for name in ("games", "direct", "direct-ips")
                                     for x in rules))
                self.assertEqual({x.split(',')[1] for x in rules
                                  if x.startswith("DOMAIN-SUFFIX,") and x.endswith(",DIRECT")}
                                 & RU_SUFFIXES, RU_SUFFIXES)
                groups = {g["name"]: g for g in doc["proxy-groups"]}
                self.assertNotIn("DIRECT", groups["Garasu"]["proxies"] or [])
                self.assertEqual(doc["rule-providers"]["rkn-domains"]["interval"], 21600)
                self.assertEqual(doc["rule-providers"]["rkn-ips"]["interval"], 21600)
                self.assertEqual((ROOT / path).read_text().count("# LEAVE THIS LINE!"), 2)

    def test_singbox_blocked_first_ru_direct_foreign_proxy(self):
        for path in SINGBOX:
            with self.subTest(path=path):
                doc = json.loads((ROOT / path).read_text())
                rules = doc["route"]["rules"]
                blocked = next(i for i, x in enumerate(rules)
                               if "garasu-rkn-domains" in x.get("rule_set", []))
                blocked_ip = next(i for i, x in enumerate(rules)
                                  if "garasu-rkn-ips" in x.get("rule_set", []))
                russian = next(i for i, x in enumerate(rules)
                               if "ru" in x.get("domain_suffix", []))
                ru_ip = next(i for i, x in enumerate(rules)
                             if "garasu-ru-ips" in x.get("rule_set", []))
                self.assertLess(blocked, russian)
                self.assertLess(blocked_ip, ru_ip)
                self.assertEqual(set(rules[russian]["domain_suffix"]), RU_SUFFIXES)
                self.assertFalse(any(set(x.get("rule_set", [])) &
                                     {"garasu-games", "garasu-direct", "garasu-direct-ips"}
                                     for x in rules))
                self.assertEqual(doc["route"]["final"], "→ Remnawave")
                groups = [x for x in doc["outbounds"] if x.get("type") in ("selector", "urltest")]
                self.assertEqual(len(groups), 1)
                self.assertIsNone(groups[0]["outbounds"])
                self.assertNotIn("direct", groups[0].get("outbounds") or [])
                providers = {x["tag"]: x for x in doc["route"]["rule_set"]}
                for name in ("garasu-rkn-domains", "garasu-rkn-ips"):
                    self.assertEqual(providers[name]["update_interval"], "6h")

    def test_local_dns_bootstrap_and_tun_are_explicit(self):
        for path in ("clients/mihomo-remnawave.yaml",
                     "clients/canary/mihomo-remnawave.yaml"):
            with self.subTest(path=path):
                doc = yaml.safe_load((ROOT / path).read_text())
                self.assertEqual(doc["dns"]["proxy-server-nameserver"], ["system"])
                self.assertEqual(doc["dns"]["direct-nameserver"], ["system"])
                self.assertIn("*.local", doc["dns"].get("fake-ip-filter", []))
        for path in SINGBOX:
            with self.subTest(path=path):
                doc = json.loads((ROOT / path).read_text())
                self.assertTrue(any(x.get("type") == "tun" and x.get("auto_route")
                                    and x.get("strict_route") for x in doc["inbounds"]))
                local = next(x for x in doc["dns"]["servers"] if x["tag"] == "local")
                self.assertEqual(local["type"], "local")
                self.assertEqual(doc["dns"]["rules"][0]["server"], "local")

    def test_xray_resolves_domain_before_ip_rules_and_preserves_proxy_fallback(self):
        doc = json.loads((ROOT / "clients/xray-advanced-remnawave.json").read_text())
        routes = doc["routing"]["rules"]
        self.assertEqual(doc["routing"]["domainStrategy"], "IpOnDemand")
        self.assertLess(next(i for i, x in enumerate(routes)
                             if "geosite:banned-ru" in x.get("domain", [])),
                        next(i for i, x in enumerate(routes)
                             if "geosite:category-ads" in x.get("domain", [])))
        blocked_ip = next(i for i, x in enumerate(routes)
                          if "geoip:blocked-ru" in x.get("ip", []))
        ads = next(i for i, x in enumerate(routes)
                   if "geosite:category-ads" in x.get("domain", []))
        self.assertLess(blocked_ip, ads)
        rebinding = next(i for i, x in enumerate(routes)
                         if "geoip:private" in x.get("ip", []) and x.get("domain"))
        private_ip = next(i for i, x in enumerate(routes)
                          if "geoip:private" in x.get("ip", []) and not x.get("domain"))
        self.assertLess(rebinding, private_ip)
        self.assertEqual(routes[rebinding]["outboundTag"], "proxy")
        lan = next(i for i, x in enumerate(routes)
                   if "domain:lan" in x.get("domain", []))
        self.assertLess(lan, rebinding)
        self.assertEqual(routes[lan]["outboundTag"], "direct")
        self.assertLess(blocked_ip, next(i for i, x in enumerate(routes)
                                         if "geoip:ru" in x.get("ip", [])))
        self.assertEqual(routes[-1]["outboundTag"], "proxy")
        self.assertFalse(any(set(x.get("domain", [])) &
                             {"geosite:category-ru", "geosite:apple", "geosite:microsoft",
                              "geosite:steam", "geosite:epicgames", "geosite:riot",
                              "geosite:roblox"}
                             for x in routes if x["outboundTag"] == "direct"))
        self.assertTrue(doc["remnawave"]["addVirtualHostAsOutbound"])
        self.assertNotIn("proxy", [x["tag"] for x in doc["outbounds"]])


if __name__ == "__main__":
    unittest.main()
