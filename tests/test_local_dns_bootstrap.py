"""Prevent DNS fake-IP and local-LAN regressions across Garasu canaries.

Static checks only; a real macOS/iOS DNS resolver and Russian ISP still need
on-device tests. Files in production are deliberately unchanged here.
"""
import json
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
C = ROOT / "clients" / "canary"
LOCAL_SUFFIXES = {"localhost", "local", "lan", "home.arpa"}


class LocalDNSBootstrapTests(unittest.TestCase):
    def test_mihomo_local_domains_never_receive_fake_ip(self):
        p = yaml.safe_load((C / "mihomo-remnawave.yaml").read_text())
        filters = set(p["dns"]["fake-ip-filter"])
        for name in LOCAL_SUFFIXES:
            with self.subTest(domain=name):
                self.assertIn(name, filters)
                self.assertIn("*." + name, filters)
                self.assertIn("DOMAIN-SUFFIX," + name + ",DIRECT", p["rules"])
        self.assertEqual(p["dns"]["proxy-server-nameserver"], ["system"])
        self.assertEqual(p["dns"]["direct-nameserver"], ["system"])
        self.assertEqual(p["mixed-port"], 7897)
        self.assertNotIn("DIRECT", next(x for x in p["proxy-groups"]
                                        if x["name"] == "Garasu")["proxies"])

    def test_singbox_local_names_resolve_normally_before_fake_ip(self):
        p = json.loads((C / "singbox-remnawave-1.14.json").read_text())
        dns = p["dns"]
        self.assertEqual(dns["rules"][0]["server"], "local")
        self.assertTrue(LOCAL_SUFFIXES.issubset(
            set(dns["rules"][0]["domain_suffix"])))
        self.assertEqual(dns["rules"][0]["action"], "route")
        self.assertEqual(dns["rules"][1]["server"], "remote")
        self.assertEqual(set(dns["rules"][1]["query_type"]), {"A", "AAAA"})
        local = next(x for x in dns["servers"] if x["tag"] == "local")
        remote = next(x for x in dns["servers"] if x["tag"] == "remote")
        self.assertEqual(local["type"], "local")
        self.assertNotIn("server", local)
        self.assertEqual(remote["type"], "fakeip")
        self.assertEqual(p["route"]["default_domain_resolver"], "local")

    def test_local_network_coverage_mihomo_stash_shadowrocket(self):
        expected = {
            "DOMAIN-SUFFIX,localhost,DIRECT",
            "DOMAIN-SUFFIX,local,DIRECT",
            "DOMAIN-SUFFIX,lan,DIRECT",
            "DOMAIN-SUFFIX,home.arpa,DIRECT",
            "IP-CIDR,169.254.0.0/16,DIRECT,no-resolve",
            "IP-CIDR,100.64.0.0/10,DIRECT,no-resolve",
        }
        for name in ("mihomo-remnawave.yaml", "stash-remnawave.yaml"):
            p = yaml.safe_load((C / name).read_text())
            rules = p["rules"]
            first_remote = rules.index("RULE-SET,rkn-domains,Garasu")
            for rule in expected:
                with self.subTest(client=name, rule=rule):
                    self.assertIn(rule, rules)
                    self.assertLess(rules.index(rule), first_remote)

        raw = (C / "shadowrocket.conf").read_text()
        front = raw.split("[Rule]", 1)[1]
        for rule in expected:
            with self.subTest(client="Shadowrocket", rule=rule):
                self.assertIn(rule, front)
                self.assertLess(front.index(rule), front.index("rkn-domains.list,PROXY"))
        bypass = next(x for x in raw.splitlines() if x.startswith("skip-proxy ="))
        for entry in ("169.254.0.0/16", "100.64.0.0/10",
                      "localhost", "*.local", "*.lan", "*.home.arpa"):
            self.assertIn(entry, bypass)

    def test_no_region_chain_and_default_proxy_for_foreign(self):
        for name in ("mihomo-remnawave.yaml", "stash-remnawave.yaml"):
            p = yaml.safe_load((C / name).read_text())
            self.assertEqual(p["rules"][-1], "MATCH,Garasu")
            self.assertNotIn("dialer-proxy", (C / name).read_text())
        sb = json.loads((C / "singbox-remnawave-1.14.json").read_text())
        self.assertEqual(sb["route"]["final"], "→ Remnawave")
        self.assertEqual(len([x for x in sb["outbounds"]
                              if x.get("type") == "selector"]), 1)
        shadow = (C / "shadowrocket.conf").read_text()
        self.assertIn("FINAL,PROXY", shadow)


if __name__ == "__main__":
    unittest.main()
