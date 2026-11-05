"""Regression contract: one automatic route, compressed providers, six-hour refresh."""
import json
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
RAW = "https://raw.githubusercontent.com/togahimoko/garasu/main/"


class CompactAutoMRSTests(unittest.TestCase):
    def test_mihomo_has_one_automatic_group_and_mrs_every_six_hours(self):
        cfg = yaml.safe_load((ROOT / "release/mihomo/config.yaml").read_text())
        self.assertEqual(len(cfg["proxy-groups"]), 1)
        group = cfg["proxy-groups"][0]
        self.assertEqual((group["name"], group["type"]), ("Garasu", "url-test"))
        self.assertNotIn("include-all", group)
        self.assertEqual(cfg["rules"][-1], "MATCH,Garasu")
        self.assertNotIn("select", [g["type"] for g in cfg["proxy-groups"]])
        for name, provider in cfg["rule-providers"].items():
            with self.subTest(name=name):
                self.assertEqual(provider["type"], "http")
                classical = provider["behavior"]=="classical"
                self.assertEqual(provider["format"], "yaml" if classical else "mrs")
                self.assertEqual(provider["interval"], 21600)
                self.assertEqual(provider["proxy"], "DIRECT")
                url = (RAW+"release/clash/providers/"+name+".yaml" if classical else
                       RAW+"release/mihomo/.mrs/"+name+".mrs")
                self.assertEqual(provider["url"],url)
                if not classical:
                    self.assertTrue((ROOT/"release/mihomo/.mrs"/(name+".mrs")).stat().st_size>20)
        self.assertLess((ROOT / "release/mihomo/config.yaml").stat().st_size, 24000)

    def test_mobile_routing_revision_advances_with_source_revision(self):
        from scripts.sync_universal_routing import route_incy
        from scripts.sync_universal_routing import load_policy
        policy = load_policy(ROOT)
        policy["_last_updated"] = "1794000001"
        config = {"LastUpdated": "1793815000"}
        output = route_incy(config, policy)
        self.assertEqual(output["LastUpdated"], "1794000001")

    def test_stash_autoselect_and_binary_mrs_refresh(self):
        cfg = yaml.safe_load((ROOT / "release/stash/config.yaml").read_text())
        self.assertEqual([g["type"] for g in cfg["proxy-groups"]], ["url-test"])
        for name, provider in cfg["rule-providers"].items():
            with self.subTest(name=name):
                classical=provider["behavior"]=="classical"
                self.assertEqual(provider["format"],"yaml" if classical else "mrs")
                self.assertEqual(provider["interval"],21600)
                self.assertEqual(provider["url"],(RAW+"release/clash/providers/"+name+".yaml" if classical else
                                                   RAW+"release/mihomo/.mrs/"+name+".mrs"))

    def test_singbox_uses_binary_remote_srs_refresh(self):
        cfg = json.loads((ROOT / "release/singbox/config.json").read_text())
        for rule in cfg["route"]["rule_set"]:
            with self.subTest(name=rule["tag"]):
                self.assertEqual(rule["type"], "remote")
                self.assertEqual(rule["format"], "binary")
                self.assertEqual(rule["update_interval"], "6h")
                self.assertTrue(rule["url"].endswith(".srs"))
                self.assertTrue((ROOT / "release/singbox/rules" / (rule["tag"].removeprefix("garasu-") + ".srs")).stat().st_size > 20)


if __name__ == "__main__":
    unittest.main()
