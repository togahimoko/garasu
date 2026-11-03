"""Smoke fixtures must use the real pinned full Refilter candidate files."""
import json
from pathlib import Path
import tempfile
import unittest
import yaml
from scripts import smoke_cores

ROOT = Path(__file__).resolve().parents[1]


class UnifiedEngineFixture(unittest.TestCase):
    def test_mihomo_full_registry_and_injected_nodes(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            prepared = smoke_cores.prepare_mihomo(
                "clients/unified/mihomo-remnawave.yaml", out, node_count=5)
            config = yaml.safe_load(prepared.read_text())
            self.assertEqual(len(config["proxies"]), 5)
            self.assertEqual(config["proxy-groups"][0]["proxies"], ["Garasu Auto"])
            self.assertEqual(config["proxy-groups"][1]["type"], "url-test")
            self.assertIn("rkn-domains-full", config["rule-providers"])
            self.assertIn("rkn-ips-full", config["rule-providers"])
            self.assertTrue(all(x["type"] == "file" for x in config["rule-providers"].values()))
            self.assertEqual(config["rules"][-1], "MATCH,Garasu")
            self.assertNotIn("GEOIP,RU,DIRECT", config["rules"])

    def test_singbox_full_registry_and_injected_nodes(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            prepared = smoke_cores.prepare_singbox(
                "clients/unified/singbox-remnawave-1.14.json", out, node_count=5)
            config = json.loads(prepared.read_text())
            self.assertEqual(len(config["outbounds"][0]["outbounds"]), 5)
            rulesets = {x["tag"]: x for x in config["route"]["rule_set"]}
            self.assertEqual(Path(rulesets["garasu-rkn-domains-full"]["path"]),
                             ROOT / "rules/unified/refilter-domain-full.singbox.json")
            self.assertEqual(Path(rulesets["garasu-rkn-ips-full"]["path"]),
                             ROOT / "rules/unified/refilter-ip-full.singbox.json")
            self.assertEqual(config["route"]["final"], "→ Remnawave")

    def test_xray_candidate_keeps_virtual_host_injection(self):
        with tempfile.TemporaryDirectory() as td:
            prepared = smoke_cores.prepare_xray(
                "clients/unified/xray-advanced-remnawave.json", Path(td))
            config = json.loads(prepared.read_text())
            self.assertIn("proxy", [x["tag"] for x in config["outbounds"]])
            self.assertNotIn("geosite:apple", json.dumps(config["routing"]))
            self.assertNotIn("geoip:ru", json.dumps(config["routing"]))


if __name__ == "__main__":
    unittest.main()
