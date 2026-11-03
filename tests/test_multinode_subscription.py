"""Dynamic 1..32-node subscription acceptance without subscriber credentials.

These tests simulate Remnawave injection. Native app panel delivery still
requires separate real-subscription validation before production rollout.
"""
import json
from pathlib import Path
import tempfile
import unittest

import yaml

from scripts.smoke_cores import prepare_mihomo, prepare_singbox

ROOT = Path(__file__).resolve().parents[1]
MIHOMO = "clients/canary/mihomo-remnawave.yaml"
STASH = "clients/canary/stash-remnawave.yaml"
SINGBOX = "clients/canary/singbox-remnawave-1.14.json"
SINGBOX_AUTO = "clients/experimental/singbox-remnawave-1.14-auto.json"


class MultiNodeInjectionContract(unittest.TestCase):
    def test_mihomo_picks_all_nodes_automatically_with_no_direct_override(self):
        for count in (1, 2, 5, 16, 32):
            with self.subTest(nodes=count), tempfile.TemporaryDirectory() as tmp:
                output = prepare_mihomo(MIHOMO, Path(tmp), node_count=count)
                doc = yaml.safe_load(output.read_text())
                members = doc["proxies"]
                self.assertEqual(len(members), count)
                names = {p["name"] for p in members}
                self.assertEqual(len(names), count)
                groups = {p["name"]: p for p in doc["proxy-groups"]}
                self.assertEqual(groups["Garasu"]["proxies"], ["Garasu Auto"])
                self.assertNotIn("DIRECT", groups["Garasu"]["proxies"])
                auto = groups["Garasu Auto"]
                self.assertEqual(auto["type"], "url-test")
                self.assertTrue(auto["include-all"])
                self.assertEqual(auto["proxies"], [])
                self.assertFalse(auto.get("lazy", True))
                self.assertEqual(auto["empty-fallback"], "REJECT")
                self.assertEqual(auto["expected-status"], 204)
                self.assertFalse(auto.get("filter"))
                self.assertFalse(auto.get("exclude-filter"))
                self.assertEqual(doc["rules"][-1], "MATCH,Garasu")

    def test_stash_checks_injected_node_pool_and_rejects_empty_pool(self):
        for count in (1, 2, 5, 16, 32):
            with self.subTest(nodes=count), tempfile.TemporaryDirectory() as tmp:
                output = prepare_mihomo(STASH, Path(tmp), node_count=count)
                doc = yaml.safe_load(output.read_text())
                groups = {g["name"]: g for g in doc["proxy-groups"]}
                self.assertEqual(len(doc["proxies"]), count)
                names = {p["name"] for p in doc["proxies"]}
                self.assertEqual(groups["Garasu"]["type"], "url-test")
                self.assertEqual(set(groups["Garasu"]["proxies"]), names | {"REJECT"})
                self.assertNotIn("DIRECT", groups["Garasu"]["proxies"])
                self.assertFalse(groups["Garasu"].get("lazy", True))
                self.assertEqual(doc["rules"][-1], "MATCH,Garasu")

    def test_singbox_stable_and_experimental_support_variable_node_count(self):
        for template, expected_type in ((SINGBOX, "selector"),
                                        (SINGBOX_AUTO, "urltest")):
            for count in (1, 2, 5, 16, 32):
                with (self.subTest(template=template, nodes=count),
                      tempfile.TemporaryDirectory() as tmp):
                    output = prepare_singbox(template, Path(tmp), node_count=count)
                    doc = json.loads(output.read_text())
                    groups = [p for p in doc["outbounds"] if p["tag"] == "→ Remnawave"]
                    self.assertEqual(len(groups), 1)
                    group = groups[0]
                    self.assertEqual(group["type"], expected_type)
                    self.assertEqual(len(group["outbounds"]), count)
                    self.assertEqual(len(set(group["outbounds"])), count)
                    nodes = {p["tag"] for p in doc["outbounds"] if p["type"] == "http"}
                    self.assertEqual(nodes, set(group["outbounds"]))
                    self.assertNotIn("direct", group["outbounds"])
                    self.assertEqual(doc["route"]["final"], "→ Remnawave")
                    if expected_type == "urltest":
                        self.assertGreater(group["tolerance"], 0)
                        self.assertEqual(group["url"], "https://cp.cloudflare.com/generate_204")

    def test_uninjected_empty_pool_is_never_configured_as_direct(self):
        mihomo = yaml.safe_load((ROOT / MIHOMO).read_text())
        stash = yaml.safe_load((ROOT / STASH).read_text())
        groups = {p["name"]: p for p in mihomo["proxy-groups"]}
        self.assertEqual(groups["Garasu Auto"]["empty-fallback"], "REJECT")
        self.assertTrue(groups["Garasu Auto"]["include-all"])
        self.assertEqual(stash["proxy-groups"][0]["proxies"], ["REJECT"])
        self.assertEqual(stash["proxy-groups"][0]["type"], "url-test")
        self.assertNotIn("DIRECT", stash["proxy-groups"][0]["proxies"])


if __name__ == "__main__":
    unittest.main()
