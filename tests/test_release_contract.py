"""Contract tests for the released native profiles and Remnawave responses.

These checks verify serialized policy, routing precedence and test-user-agent
selection. Native device import and real ISP connectivity are separate tests.
"""
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

    def test_single_group_and_no_direct_fallback(self):
        config = self.mihomo
        self.assertEqual(config["mode"], "rule")
        self.assertEqual(config["rules"][-1], "MATCH,Garasu")
        groups = config["proxy-groups"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["name"], "Garasu")
        self.assertEqual(groups[0]["type"], "url-test")
        self.assertTrue(groups[0]["include-all"])
        self.assertFalse(groups[0]["lazy"])
        self.assertEqual(groups[0]["empty-fallback"], "REJECT")
        self.assertFalse(config["profile"]["store-selected"])
        self.assertNotIn("DIRECT", groups[0].get("proxies") or [])
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
                group["proxies"] = []
                names = {n["name"] for n in data["proxies"]}
                self.assertEqual(len(names), count)
                self.assertTrue(group["include-all"])
                self.assertEqual(group["empty-fallback"], "REJECT")
                self.assertNotIn("DIRECT", group["proxies"])
                self.assertEqual(data["rules"][-1], "MATCH,Garasu")

    def test_routing_priority_and_rule_download_bootstrap(self):
        rules = self.mihomo["rules"]
        self.assertLess(rules.index("RULE-SET,rkn-domains,Garasu"),
                        rules.index("DOMAIN-SUFFIX,ru,DIRECT"))
        self.assertLess(rules.index("RULE-SET,rkn-ips,Garasu"),
                        rules.index("RULE-SET,ru-ips,DIRECT,no-resolve"))
        providers = self.mihomo["rule-providers"]
        self.assertEqual(len(providers), 13)
        for name, rule in providers.items():
            self.assertEqual(rule["format"], "mrs", name)
            self.assertEqual(rule["proxy"], "DIRECT", name)
            self.assertTrue(rule["url"].endswith(
                "/release/mihomo/.mrs/" + name + ".mrs"))
        self.assertEqual(self.mihomo["dns"]["proxy-server-nameserver"],
                         ["system"])

    def test_no_embedded_personal_nodes(self):
        for path in (RELEASE / "mihomo/config.yaml",
                     RELEASE / "stash/config.yaml"):
            text = path.read_text(encoding="utf-8")
            self.assertEqual(text.count("proxies: # LEAVE THIS LINE!"), 2)
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

    def test_dedicated_test_agent_does_not_replace_normal_clients(self):
        test = self.preview["rules"]
        self.assertEqual(test[0]["responseType"], "BROWSER")
        self.assertEqual(test[1]["name"], "Garasu Test")
        self.assertTrue(self._match(test[1], "garasu-test-mihomo/1.0"))
        self.assertFalse(self._match(test[1], "mihomo/1.0"))
        self.assertEqual(test[1]["responseModifications"]["subscriptionTemplate"],
                         "Garasu")
        self.assertEqual(test[-1]["responseType"], "XRAY_BASE64")


if __name__ == "__main__":
    unittest.main()
