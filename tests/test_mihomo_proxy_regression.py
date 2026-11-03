"""Stop proxy-only and latency regressions in Garasu Mihomo candidate."""
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CANARY = ROOT / "clients/canary/mihomo-remnawave.yaml"


class MihomoRuntimeRegressions(unittest.TestCase):
    def setUp(self):
        self.text = CANARY.read_text(encoding="utf-8")
        self.profile = yaml.safe_load(self.text)
        self.groups = {g["name"]: g for g in self.profile["proxy-groups"]}

    def test_system_proxy_has_an_explicit_loopback_listener(self):
        self.assertEqual(self.profile.get("mixed-port"), 7897,
                         "Without a local HTTP/SOCKS listener, only TUN may work")
        self.assertFalse(self.profile.get("allow-lan", False))

    def test_selected_group_cannot_silently_remain_direct(self):
        self.assertEqual(self.groups["Garasu"]["proxies"], ["Garasu Auto"])
        self.assertIs(self.profile["profile"]["store-selected"], False)
        self.assertEqual(self.profile["rules"][-1], "MATCH,Garasu")
        self.assertIn("RULE-SET,direct,DIRECT", self.profile["rules"])

    def test_url_test_group_probes_nodes_even_without_a_saved_selection(self):
        auto = self.groups["Garasu Auto"]
        self.assertEqual(auto["type"], "url-test")
        self.assertTrue(auto["include-all"])
        self.assertFalse(auto.get("lazy", True))
        self.assertGreaterEqual(auto.get("timeout", 0), 5000)
        self.assertEqual(auto["remnawave"]["include-proxies"], False)
        self.assertEqual(self.text.count("proxies: # LEAVE THIS LINE!"), 2)

    def test_do_not_force_tun_or_expose_controller_via_subscription(self):
        self.assertNotIn("tun", self.profile)
        self.assertNotIn("external-controller", self.profile)
        self.assertFalse(self.profile.get("allow-lan", False))

if __name__ == "__main__":
    unittest.main()
