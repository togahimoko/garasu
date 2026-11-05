"""Contract tests for the released native profiles and Remnawave responses.

These checks verify one production policy, routing precedence and real
client User-Agent selection. Native device import and real ISP connectivity are separate tests.
"""
import base64
import copy
import json
from pathlib import Path
import re
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release"


class NativeReleaseContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mihomo = yaml.safe_load((RELEASE / "mihomo/config.yaml").read_text())
        cls.ssr = json.loads((RELEASE / "remnawave/srr.json").read_text())

    def test_one_visible_automatic_group_and_fail_closed(self):
        config = self.mihomo
        self.assertEqual(config["mode"], "rule")
        self.assertEqual(config["rules"][-1], "MATCH,Garasu")
        self.assertEqual(len(config["proxy-groups"]), 1)
        auto = config["proxy-groups"][0]
        self.assertEqual((auto["name"], auto["type"]), ("Garasu", "url-test"))
        self.assertNotIn("include-all", auto)
        self.assertFalse(auto["lazy"])
        self.assertEqual(auto["empty-fallback"], "REJECT")
        self.assertNotIn("DIRECT", auto.get("proxies") or [])
        self.assertNotIn("tun", config)

    def test_dynamic_subscriber_node_counts(self):
        for count in (0, 1, 2, 5, 32):
            with self.subTest(node_count=count):
                data = copy.deepcopy(self.mihomo)
                data["proxies"] = [
                    {"name": "TEST_NODE_" + str(i), "type": "socks5",
                     "server": "127.0.0.1", "port": 29000 + i}
                    for i in range(count)
                ]
                group = data["proxy-groups"][0]
                group["proxies"] = [n["name"] for n in data["proxies"]]
                self.assertEqual(len(group["proxies"]), count)
                self.assertEqual(group["type"], "url-test")
                self.assertEqual(group["empty-fallback"], "REJECT")
                self.assertNotIn("DIRECT", group["proxies"])
                self.assertEqual(data["rules"][-1], "MATCH,Garasu")

    def test_single_universal_policy_uses_remote_provider_links(self):
        rules = self.mihomo["rules"]
        self.assertLess(rules.index("RULE-SET,ads,REJECT"),
                        rules.index("DOMAIN-SUFFIX,sberbank.ru,DIRECT"))
        self.assertIn("DOMAIN-SUFFIX,ru,DIRECT", rules)
        self.assertIn("RULE-SET,ru-ips,DIRECT,no-resolve", rules)
        self.assertLess(rules.index("RULE-SET,rkn-domains,Garasu"),
                        rules.index("DOMAIN-SUFFIX,ru,DIRECT"))
        self.assertLess(rules.index("RULE-SET,rkn-ips,Garasu,no-resolve"),
                        rules.index("RULE-SET,ru-ips,DIRECT,no-resolve"))
        self.assertEqual(rules[-1], "MATCH,Garasu")
        providers = self.mihomo["rule-providers"]
        self.assertEqual(len(providers), 37)
        self.assertTrue(all(p["type"]=="http" and "payload" not in p
                            for p in providers.values()))
        for name,p in providers.items():
            if p["behavior"]=="classical":
                self.assertEqual(p["format"],"yaml")
                self.assertTrue(p["url"].endswith("/release/clash/providers/"+name+".yaml"))
            else:
                self.assertEqual(p["format"],"mrs")
                self.assertTrue(p["url"].endswith("/release/mihomo/.mrs/"+name+".mrs"))
        self.assertEqual(self.mihomo["dns"]["proxy-server-nameserver"],
                         ["system"])

    def test_no_embedded_personal_nodes(self):
        for path in (RELEASE / "mihomo/config.yaml",
                     RELEASE / "stash/config.yaml"):
            text = path.read_text(encoding="utf-8")
            self.assertEqual(text.count("proxies: # LEAVE THIS LINE!"),
                             2)
            self.assertNotIn("vless://", text)
            self.assertNotIn("uuid:", text.lower())

    @staticmethod
    def _match(rule, user_agent, accept="*/*"):
        conditions = rule.get("conditions") or []
        if not conditions:
            return True
        for item in conditions:
            value = accept if item["headerName"] == "accept" else user_agent
            pattern = item["value"]
            flags = 0 if item.get("caseSensitive") else re.I
            op = item["operator"]
            if op == "REGEX":
                ok = re.search(pattern, value, flags) is not None
            elif op == "STARTS_WITH":
                ok = value.lower().startswith(pattern.lower())
            elif op == "CONTAINS":
                ok = pattern.lower() in value.lower()
            else:
                ok = False
            if not ok:
                return False
        return True

    def test_srr_app_routing_and_safe_fallback(self):
        mapping = {
            "mihomo/1.0": "MIHOMO",
            "clash-verge-rev/2.0": "MIHOMO",
            "FlClash/1.0": "MIHOMO",
            "clash/1.0": "CLASH",
            "ClashX/1.0": "CLASH",
            "clash-premium/1.0": "CLASH",
            "clashx meta/1.0": "MIHOMO",
            "garasu-xray-json/1.0": "XRAY_JSON",
            "xray-core/1.0": "XRAY_JSON",
            "stash/1.0": "STASH",
            "karing/1.0": "SINGBOX",
            "incy/1.0": "XRAY_BASE64",
            "happ/1.0": "XRAY_BASE64",
            "Shadowrocket/1.0": "XRAY_BASE64",
            "v2rayN/1.0": "XRAY_BASE64",
        }
        rules = self.ssr["rules"]
        self.assertEqual(rules[0]["responseType"], "BROWSER")
        self.assertEqual(rules[-1]["name"], "Fallback Base64")
        self.assertEqual(rules[-1]["responseType"], "XRAY_BASE64")
        self.assertEqual(rules[-1]["conditions"], [])
        for ua, expected in mapping.items():
            with self.subTest(ua=ua):
                match = next(x for x in rules if x["enabled"] and self._match(x, ua))
                self.assertEqual(match["responseType"], expected)
        self.assertEqual(
            next(x for x in rules if self._match(x, "mihomo/1.0", "text/html"))["responseType"],
            "BROWSER"
        )

    def test_response_rules_no_ambiguous_client_overlaps(self):
        cases = ("mihomo/1.0", "clash-verge-rev/2.0", "FlClash/1.0",
                 "clash/1.0", "ClashX/1.0", "clash-premium/1.0",
                 "stash/2.0", "sfa/1.0", "karing/1.0",
                 "garasu-xray-json/1.0", "xray/1.0", "xray-core/1.0",
                 "incy/1.0", "happ/1.0", "Shadowrocket/1.0", "v2rayN/7.0")
        rules = self.ssr["rules"]
        self.assertEqual(sum(r["enabled"] and not r["conditions"] for r in rules), 1)
        for ua in cases:
            with self.subTest(ua=ua):
                matches = [r for r in rules if r["enabled"] and r["conditions"]
                           and self._match(r, ua)]
                self.assertLessEqual(len(matches), 1, "Ambiguous User-Agent match")
        self.assertEqual(rules[-1]["name"], "Fallback Base64")

    def test_happ_subscriber_header_equals_generated_profile(self):
        target = json.loads((RELEASE / "happ/config.json").read_text(encoding="utf-8"))
        rule = next(r for r in self.ssr["rules"] if r["name"] == "Happ Garasu")
        value = next(h["value"] for h in
                     rule["responseModifications"]["headers"]
                     if h["key"].lower() == "routing")
        self.assertTrue(value.startswith("happ://routing/onadd/"))
        self.assertLess(len(value.encode("ascii")), 3500)
        profile = json.loads(base64.b64decode(value.split("/onadd/", 1)[1]))
        self.assertEqual(profile, target)
        self.assertEqual(profile["BlockSites"],
                         ["geosite:garasu-ads","geosite:category-ads","geosite:win-spy"])
        self.assertGreater(int(target["LastUpdated"]), 1793761499)

    def test_production_srr_has_no_missing_named_templates(self):
        # SSR may reference only installed Default templates; five formats must
        # be enabled while Xray-compatible apps can opt in explicitly.
        for rule in self.ssr["rules"]:
            if not rule.get("enabled", False):
                continue
            template = rule.get("responseModifications", {}).get("subscriptionTemplate")
            if template:
                self.assertEqual(template, "Default", rule["name"])
        xray = [r for r in self.ssr["rules"] if r["responseType"] == "XRAY_JSON"]
        self.assertEqual(len(xray), 1)
        self.assertEqual({r["responseType"] for r in self.ssr["rules"] if r["enabled"]} &
                         {"MIHOMO", "STASH", "SINGBOX", "CLASH", "XRAY_JSON"},
                         {"MIHOMO", "STASH", "SINGBOX", "CLASH", "XRAY_JSON"})
        self.assertEqual(next(r for r in self.ssr["rules"] if r["name"] == "Clash Core Clients")["responseType"], "CLASH")
        self.assertTrue(xray[0]["enabled"])
        self.assertEqual(xray[0]["responseModifications"]["subscriptionTemplate"], "Default")
        self.assertTrue(xray[0]["responseModifications"]["ignoreHostXrayJsonTemplate"])

    def test_only_one_production_srr(self):
        self.assertEqual([p.name for p in
                          (RELEASE / "remnawave").glob("*.json")],
                         ["srr.json"])
        self.assertFalse(any("garasu-test-" in json.dumps(r).lower()
                             for r in self.ssr["rules"]))


if __name__ == "__main__":
    unittest.main()
