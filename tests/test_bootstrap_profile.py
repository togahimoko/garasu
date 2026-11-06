"""Cold-start profile attached to Telegram can be imported without another VPN."""
from pathlib import Path
import tempfile
import unittest

import yaml

from scripts.export_bootstrap_profile import ROOT, TEMPLATE, build_profile, export


class BootstrapExportTest(unittest.TestCase):
    def setUp(self):
        self.source = {
            "proxies": [
                {"name": "TEST_CF", "type": "vless", "server": "203.0.113.10",
                 "port": 443, "uuid": "00000000-0000-4000-8000-000000000001"},
                {"name": "TEST_REALITY", "type": "vless", "server": "203.0.113.11",
                 "port": 443, "uuid": "00000000-0000-4000-8000-000000000002"},
            ]
        }

    def test_export_preserves_all_nodes_and_rules_without_vpn_bootstrap(self):
        with tempfile.TemporaryDirectory(prefix="garasu-telegram-bootstrap-") as home:
            output = Path(home) / "private.yaml"
            result = export(yaml.safe_dump(self.source), output)
            self.assertEqual(result, output.resolve())
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            cfg = yaml.safe_load(output.read_text())
            self.assertEqual(cfg["proxies"], self.source["proxies"])
            self.assertEqual(cfg["proxy-groups"][0]["proxies"],
                             ["TEST_CF", "TEST_REALITY"])
            self.assertEqual(cfg["rules"][-1], "MATCH,Garasu")
            self.assertEqual(len(cfg["rule-providers"]), 37)
            self.assertTrue(all(p["proxy"] == "DIRECT"
                                for p in cfg["rule-providers"].values()))
            self.assertEqual(cfg["dns"]["nameserver-policy"]["raw.githubusercontent.com"],
                             ["tcp://77.88.8.8:53", "tcp://77.88.8.1:53"])
            with self.assertRaises(FileExistsError):
                export(yaml.safe_dump(self.source), output)

    def test_reject_empty_and_duplicate_nodes(self):
        template = yaml.safe_load(TEMPLATE.read_text())
        with self.assertRaises(ValueError):
            build_profile({"proxies": []}, template)
        bad = {"proxies": [self.source["proxies"][0]] * 2}
        with self.assertRaises(ValueError):
            build_profile(bad, yaml.safe_load(TEMPLATE.read_text()))

    def test_never_write_credentials_into_public_repo(self):
        with self.assertRaises(ValueError):
            export(yaml.safe_dump(self.source), ROOT / "release/private.yaml")


if __name__ == "__main__":
    unittest.main()
