"""Contract tests for the released native profiles and Remnawave responses.

These checks verify serialized policy, routing precedence and test-user-agent
selection. Native device import and real ISP connectivity are separate tests.
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
        cls.preview = json.loads((RELEASE / "remnawave/srr-test.json").read_text())

    def test_one_visible_selector_and_fail_closed_auto(self):
        config = self.mihomo
        self.assertEqual(config["mode"], "rule")
        self.assertEqual(config["rules"][-1], "MATCH,Garasu")
        select, auto = config["proxy-groups"]
        self.assertEqual([g["name"] for g in config["proxy-groups"]
                          if not g.get("hidden")], ["Garasu"])
        self.assertEqual(select["type"], "select")
        self.assertEqual(select["proxies"], ["Garasu Auto"])
        self.assertEqual(select["default-selected"], "Garasu Auto")
        self.assertNotIn("remnawave", select)
        self.assertTrue(config["profile"]["store-selected"])
        self.assertEqual(auto["name"], "Garasu Auto")
        self.assertEqual(auto["type"], "url-test")
        self.assertTrue(auto["include-all"])
        self.assertTrue(auto["hidden"])
        self.assertFalse(auto["remnawave"]["include-proxies"])
        self.assertFalse(auto["lazy"])
        self.assertEqual(auto["empty-fallback"], "REJECT")
        self.assertNotIn("DIRECT", select["proxies"])
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
                select, auto = data["proxy-groups"]
                select["proxies"] = ["Garasu Auto"] + [
                    n["name"] for n in data["proxies"]
                ]
                auto["proxies"] = []
                self.assertEqual(len(select["proxies"]), 1 + count)
                self.assertEqual(select["proxies"][0], "Garasu Auto")
                self.assertEqual(select["default-selected"], "Garasu Auto")
                self.assertTrue(auto["include-all"])
                self.assertEqual(auto["empty-fallback"], "REJECT")
                self.assertNotIn("DIRECT", select["proxies"])
                self.assertEqual(data["rules"][-1], "MATCH,Garasu")

    def test_single_universal_policy_has_no_remote_bootstrap(self):
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
        self.assertTrue(all(p["type"] == "inline" for p in providers.values()))
        self.assertGreater(len(providers["rkn-domains"]["payload"]), 10000)
        self.assertGreater(len(providers["rkn-ips"]["payload"]), 20000)
        self.assertGreater(len(providers["ru-ips"]["payload"]), 20000)
        self.assertEqual(self.mihomo["dns"]["proxy-server-nameserver"],
                         ["system"])

    def test_no_embedded_personal_nodes(self):
        for path in (RELEASE / "mihomo/config.yaml",
                     RELEASE / "stash/config.yaml"):
            text = path.read_text(encoding="utf-8")
            self.assertEqual(text.count("proxies: # LEAVE THIS LINE!"),
                             3 if path.parent.name == "mihomo" else 2)
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
            "clash/1.0": "MIHOMO",
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
                match = next(x for x in rules if self._match(x, ua))
                self.assertEqual(match["responseType"], expected)
        self.assertEqual(
            next(x for x in rules if self._match(x, "mihomo/1.0", "text/html"))["responseType"],
            "BROWSER"
        )

    def test_happ_subscriber_header_equals_generated_profile(self):
        target = json.loads((RELEASE / "happ/config.json").read_text(encoding="utf-8"))
        rule = next(r for r in self.ssr["rules"] if r["name"] == "Happ Garasu")
        value = next(h["value"] for h in
                     rule["responseModifications"]["headers"]
                     if h["key"].lower() == "routing")
        self.assertTrue(value.startswith("happ://routing/onadd/"))
        profile = json.loads(base64.b64decode(value.split("/onadd/", 1)[1]))
        self.assertEqual(profile, target)
        self.assertGreater(int(target["LastUpdated"]), 1793761499)

    def test_production_srr_has_no_missing_named_templates(self):
        # Production SSR refers only to the known installed Default records.
        # Optional Xray JSON is disabled until its template is deployed.
        for rule in self.ssr["rules"]:
            if not rule.get("enabled", False):
                continue
            template = rule.get("responseModifications", {}).get("subscriptionTemplate")
            if template:
                self.assertEqual(template, "Default", rule["name"])
        xray = [r for r in self.ssr["rules"] if r["responseType"] == "XRAY_JSON"]
        self.assertEqual(len(xray), 1)
        self.assertFalse(xray[0]["enabled"])

    def test_dedicated_test_agent_does_not_replace_normal_clients(self):
        test = self.preview["rules"]
        self.assertEqual(test[0]["responseType"], "BROWSER")
        self.assertEqual(test[1]["name"], "Garasu Test")
        self.assertTrue(self._match(test[1], "garasu-test-mihomo/1.0"))
        self.assertFalse(self._match(test[1], "mihomo/1.0"))
        self.assertEqual(test[1]["responseModifications"]["subscriptionTemplate"],
                         "Default")
        self.assertEqual(test[-1]["responseType"], "XRAY_BASE64")


if __name__ == "__main__":
    unittest.main()
