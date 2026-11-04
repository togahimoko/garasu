"""Clash/1.0 must use the verified Mihomo generator, not legacy CLASH.

All fixtures are public or synthetic: no subscription URL or nodes live here.
"""
import json
from pathlib import Path
import re
import unittest
from scripts import build_srr, probe_subscription_delivery

ROOT = Path(__file__).resolve().parents[1]


class ClashCompatibility(unittest.TestCase):
    def test_full_srr_selects_existing_working_template_for_generic_clash(self):
        rules = json.loads((ROOT / "docs/remnawave-six-rule-full.json").read_text())["rules"]
        match = [r for r in rules if build_srr._clash_rule(r)]
        self.assertEqual(len(match), 1)
        clash = match[0]
        self.assertEqual(clash["responseType"], "MIHOMO")
        self.assertEqual(clash["responseModifications"]["subscriptionTemplate"],
                         "Garasu Mihomo")
        self.assertTrue(re.search(clash["conditions"][0]["value"], "clash/1.0", re.I))
        self.assertFalse(re.search(clash["conditions"][0]["value"], "clash-verge/2", re.I))
        self.assertEqual(rules[0]["responseType"], "BROWSER")
        self.assertEqual(rules[-1]["responseType"], "XRAY_BASE64")
        self.assertEqual(rules[-1]["conditions"], [])
        self.assertEqual({r["name"]: r["responseType"] for r in rules
                          if r["name"] in ("INCY + Garasu MAX", "Happ + Garasu MAX")},
                         {"INCY + Garasu MAX": "XRAY_BASE64",
                          "Happ + Garasu MAX": "XRAY_BASE64"})
        for name, typ in (("Mihomo Clients", "MIHOMO"),
                          ("Stash (iOS, macOS)", "STASH"),
                          ("Sing-box clients", "SINGBOX"),
                          ("Garasu Xray JSON opt-in", "XRAY_JSON")):
            self.assertEqual(next(r for r in rules if r["name"] == name)["responseType"], typ)

    def test_compatible_template_has_two_anchors_and_thirteen_providers(self):
        content = (ROOT / "clients/mihomo-remnawave.yaml").read_text()
        counts = probe_subscription_delivery._yaml_counts(content.encode())
        self.assertEqual(counts["rule_providers"], 13)
        self.assertEqual(counts["proxy_groups"], 2)
        self.assertGreaterEqual(counts["rules"], 15)
        self.assertEqual(content.count("proxies: # LEAVE THIS LINE!"), 2)
        self.assertIn("- RULE-SET,rkn-domains,Garasu", content)
        self.assertIn("- RULE-SET,rkn-ips,Garasu", content)
        self.assertLess(content.index("- RULE-SET,rkn-domains,Garasu"),
                        content.index("- DOMAIN-SUFFIX,ru,DIRECT"))
        self.assertIn("interval: 21600", content)


if __name__ == "__main__":
    unittest.main()
