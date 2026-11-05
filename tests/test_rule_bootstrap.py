"""Remote rule-sets must bootstrap independently of the proxy tunnel."""
import json
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]

class GarasuColdBootstrap(unittest.TestCase):
    def test_mihomo_rule_downloads_do_not_depend_on_proxy(self):
        cfg = yaml.safe_load((ROOT / "release/mihomo/config.yaml").read_text())
        self.assertEqual(len(cfg["proxy-groups"]), 1)
        for name, provider in cfg["rule-providers"].items():
            with self.subTest(name=name):
                self.assertEqual(provider["proxy"], "DIRECT")
                self.assertEqual(provider["type"], "http")
                classical=provider["behavior"]=="classical"
                self.assertEqual(provider["format"], "yaml" if classical else "mrs")
                self.assertEqual(provider["interval"], 21600)
                self.assertTrue(provider["url"].startswith(
                    "https://raw.githubusercontent.com/togahimoko/garasu/main/release/clash/providers/"
                    if classical else
                    "https://raw.githubusercontent.com/togahimoko/garasu/main/release/mihomo/.mrs/"))

    def test_singbox_remote_rules_http_client_has_direct_detour(self):
        cfg = json.loads((ROOT / "release/singbox/config.json").read_text())
        tag = cfg["route"]["default_http_client"]
        clients = [c for c in cfg["http_clients"] if c["tag"] == tag]
        self.assertEqual(len(clients), 1)
        self.assertNotIn("detour", clients[0], "Explicit empty direct outbound breaks sing-box 1.14 runtime")
        for server in cfg.get("dns",{}).get("servers",[]):
            self.assertNotEqual(server.get("detour"), "direct",
                                "Direct DNS detour to empty outbound breaks sing-box runtime")
        self.assertTrue(cfg["experimental"]["cache_file"]["enabled"])
        for r in cfg["route"]["rule_set"]:
            self.assertEqual(r["http_client"], tag)
            self.assertEqual(r["format"], "binary")
            self.assertEqual(r["update_interval"], "6h")

    def test_network_cold_start_is_optional_and_safe_by_design(self):
        import subprocess
        import sys
        script = ROOT / "scripts/smoke_cold_bootstrap.py"
        source = script.read_text()
        self.assertIn("TemporaryDirectory(", source)
        self.assertIn("127.0.0.1", source)
        self.assertIn("OFFLINE_SYNTHETIC", source)
        self.assertIn("MRS_NAMES", source)
        help_output = subprocess.run([sys.executable, "scripts/qa.py", "--help"],
                                     cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertIn("--cold-network", help_output.stdout)

    def test_mobile_and_classic_maintain_remote_sources(self):
        stash = yaml.safe_load((ROOT / "release/stash/config.yaml").read_text())
        clash = yaml.safe_load((ROOT / "release/clash/config.yaml").read_text())
        for client in (stash,clash):
            for name, provider in client["rule-providers"].items():
                with self.subTest(client=client["proxy-groups"][0]["name"], name=name):
                    self.assertEqual(provider["interval"], 21600)
                    self.assertTrue(provider["url"].startswith("https://"))
        self.assertNotIn("proxy", stash["rule-providers"]["ads"])
        self.assertNotIn("proxy", clash["rule-providers"]["ads"])

if __name__=="__main__":
    unittest.main()
