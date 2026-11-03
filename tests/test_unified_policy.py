"""Independent routing contract for Astra's unified Garasu candidate.

No real subscription tokens, nodes or user domains are required.
The oracle is not derived from the implementation's generated decisions.
"""
import ipaddress
import json
from pathlib import Path
import unittest
from scripts import unified_policy as unified

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "policy" / "unified-v1.json"


class UnifiedPolicyContract(unittest.TestCase):
    def setUp(self):
        self.policy = unified.load_policy(POLICY)

    def test_policy_is_single_versioned_source_with_no_overseas_direct(self):
        self.assertEqual(self.policy["schema_version"], 1)
        self.assertEqual(self.policy["default_action"], "PROXY")
        self.assertEqual(self.policy["empty_nodes"], "REJECT")
        self.assertEqual(self.policy["foreign_direct_exceptions"], [])
        self.assertTrue(self.policy["full_refilter_required_for_ru_bypass"])

    def test_independent_cases_and_blocked_ip_override_ru_domains(self):
        cases = [
            ("www.youtube.com", "142.250.0.1", "PROXY"),
            ("rr1.googlevideo.com", "142.250.0.1", "PROXY"),
            ("nodejs.org", "104.20.1.1", "PROXY"),
            ("www.apple.com", "17.1.1.1", "PROXY"),
            ("store.steampowered.com", "23.1.1.1", "PROXY"),
            ("bank.example.ru", "95.1.1.1", "DIRECT"),
            ("blocked.example.ru", "95.1.1.1", "PROXY"),
            ("bank.example.ru", "95.2.2.2", "PROXY"),
            ("printer.lan", "192.168.1.2", "DIRECT"),
            ("public.example.org", "192.168.1.2", "PROXY"),
        ]
        for host, ip, expected in cases:
            with self.subTest(host=host, ip=ip):
                result = unified.decide(
                    self.policy, host, ip,
                    blocked_domains={"blocked.example.ru"},
                    blocked_ips={ipaddress.ip_network("95.2.2.0/24")},
                    ru_ips={ipaddress.ip_network("95.0.0.0/8")},
                    verified_full_refilter=True,
                )
                self.assertEqual(result, expected)

    def test_no_ru_direct_on_cold_start_without_full_registry(self):
        for host, ip in (("example.ru", "95.1.1.1"),
                         ("example.su", "95.1.1.1"),
                         ("example.org", "95.1.1.1")):
            with self.subTest(host=host):
                self.assertEqual(unified.decide(self.policy, host, ip,
                    blocked_domains=set(), blocked_ips=set(), ru_ips=set(),
                    verified_full_refilter=False), "PROXY")

    def test_rendered_mihomo_fail_closed_autonodes_bootstrap(self):
        outputs = unified.build_candidates(ROOT, self.policy)
        config = outputs["clients/unified/mihomo-remnawave.yaml"]
        self.assertEqual(config.count("proxies: # LEAVE THIS LINE!"), 2)
        self.assertIn("include-all: true", config)
        self.assertIn("empty-fallback: REJECT", config)
        self.assertIn("proxy-server-nameserver:", config)
        self.assertIn("direct-nameserver:", config)
        self.assertNotIn("  - RULE-SET,games,DIRECT", config)
        self.assertNotIn("  - RULE-SET,direct,DIRECT", config)
        self.assertNotIn("  - GEOIP,RU,DIRECT", config)
        self.assertNotIn("      - DIRECT\n", config)
        self.assertIn("refilter-domain-full.list", config)
        self.assertIn("refilter-ip-full.list", config)
        self.assertLess(config.index("RULE-SET,rkn-domains-full,Garasu"),
                        config.index("RULE-SET,ads,REJECT"))

    def test_foreign_direct_removed_in_other_adapters(self):
        outputs = unified.build_candidates(ROOT, self.policy)
        stash = outputs["clients/unified/stash-remnawave.yaml"]
        shadow = outputs["clients/unified/shadowrocket.conf"]
        sb = json.loads(outputs["clients/unified/singbox-remnawave-1.14.json"])
        xray = json.loads(outputs["clients/unified/xray-advanced-remnawave.json"])
        incy = json.loads(outputs["clients/unified/incy.json"])
        happ = json.loads(outputs["clients/unified/happ.json"])
        self.assertNotIn("RULE-SET,games,DIRECT", stash)
        self.assertNotIn("games.list,DIRECT", shadow)
        self.assertNotIn("direct.list,DIRECT", shadow)
        self.assertEqual(incy, happ)
        for group in (incy["DirectSites"], xray["routing"]["rules"][-2].get("domain", [])):
            for foreign in ("geosite:apple", "geosite:microsoft", "geosite:steam"):
                self.assertNotIn(foreign, group)
        self.assertNotIn("garasu-games", json.dumps(sb["route"]["rules"]))
        self.assertEqual(sb["route"]["final"], "→ Remnawave")

    def test_candidate_outputs_do_not_overwrite_published_paths(self):
        outputs = unified.build_candidates(ROOT, self.policy)
        self.assertGreaterEqual(len(outputs), 7)
        self.assertTrue(all(k.startswith("clients/unified/") for k in outputs))
        self.assertEqual(len(outputs), len(set(outputs)))

    def test_cli_check_detects_drift_without_writing(self):
        self.assertTrue(unified.check_candidates(ROOT, self.policy))


if __name__ == "__main__":
    unittest.main()
