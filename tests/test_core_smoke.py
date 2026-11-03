"""Offline regression tests for Garasu Remnawave-to-core fixtures.

These prove syntactic node injection / rule-provider wiring only. They make
no real VPN connection and never access a personal subscription URL.
"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("garasu_smoke", ROOT / "scripts/smoke_cores.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class CoreSmokeTests(unittest.TestCase):
    def test_mihomo_and_stash_import_with_synthetic_node(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            for src in ("clients/mihomo-remnawave.yaml", "clients/stash-remnawave.yaml"):
                with self.subTest(src=src):
                    path = mod.prepare_mihomo(src, out)
                    conf = yaml.safe_load(path.read_text())
                    self.assertEqual(conf["proxies"][0]["server"], "127.0.0.1")
                    self.assertEqual(conf["proxies"][0]["name"], "garasu-ci-node")
                    self.assertTrue(all(p["type"] == "file"
                                        for p in conf["rule-providers"].values()))
                    self.assertTrue(all(Path(p["path"]).is_file()
                                        for p in conf["rule-providers"].values()))
                    self.assertTrue(all("url" not in p
                                        for p in conf["rule-providers"].values()))
                    self.assertIn("Garasu", {g["name"] for g in conf["proxy-groups"]})

    def test_singbox_both_versions_have_valid_local_rule_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            for src in ("clients/singbox-remnawave.json",
                        "clients/singbox-remnawave-1.14.json"):
                with self.subTest(src=src):
                    path = mod.prepare_singbox(src, out)
                    conf = json.loads(path.read_text())
                    self.assertIn("garasu-ci-node", conf["outbounds"][0]["outbounds"])
                    self.assertTrue(all(p["type"] == "local" and Path(p["path"]).is_file()
                                        for p in conf["route"]["rule_set"]))
                    self.assertEqual(conf["route"]["final"], "→ Remnawave")

    def test_xray_fixture_loads_asset_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = mod.prepare_xray("clients/xray-advanced-remnawave.json", Path(tmp))
            conf = json.loads(file.read_text())
            self.assertNotIn("remnawave", conf)
            self.assertIn("proxy", {o.get("tag") for o in conf["outbounds"]})
            self.assertTrue((ROOT / "geo/geoip.dat").is_file())
            self.assertTrue((ROOT / "geo/geosite.dat").is_file())

    def test_fixture_never_writes_to_live_client_files(self):
        source = ROOT / "clients/mihomo-remnawave.yaml"
        original = source.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            mod.prepare_mihomo("clients/mihomo-remnawave.yaml", Path(tmp))
        self.assertEqual(source.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
