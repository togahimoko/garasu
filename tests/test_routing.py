import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("garasu_refresh", ROOT / "scripts/refresh.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class GarasuTests(unittest.TestCase):
    def test_domains(self):
        value, count = mod.domains(b"# comment\n+.youtube.com\n+.youtube.com\n+.github.com\n", 2)
        self.assertEqual(count, 2)
        self.assertEqual(value.count(b"+.youtube.com"), 1)

    def test_ips(self):
        sr, mm, count = mod.ip_data(b"1.2.3.4/32\n2001:db8::/32\n", 2)
        self.assertEqual(count, 2)
        self.assertIn(b"IP-CIDR,1.2.3.4/32", sr)
        self.assertIn(b"IP-CIDR6,2001:db8::/32", sr)
        self.assertIn(b"1.2.3.4/32", mm)
        self.assertNotIn(b"IP-CIDR,", mm)

    def test_invalid_source_does_not_pass(self):
        with self.assertRaises(ValueError):
            mod.domains(b"invalid,rule,inject\n", 1)

    def test_profiles_and_brand(self):
        for name in ("incy", "happ"):
            doc = json.loads((ROOT / "clients" / (name + ".json")).read_text())
            self.assertEqual(doc["Name"], "Garasu MAX")
            self.assertIn("geoip:blocked-ru", doc["ProxyIp"])
            self.assertIn("geosite:youtube", doc["ProxySites"])
            self.assertIn("/togahimoko/garasu/main/geo/", doc["Geositeurl"])

    def test_shadowrocket_rule_order(self):
        conf = (ROOT / "clients/shadowrocket.conf").read_text()
        self.assertLess(conf.index("rkn-domains.list,PROXY"), conf.index("direct.list,DIRECT"))
        self.assertLess(conf.index("rkn-ips.list,PROXY"), conf.index("direct-ips.list,DIRECT"))
        self.assertIn("FINAL,PROXY", conf)
        self.assertNotIn("DST-PORT,443,REJECT", conf)
        self.assertNotIn("*.ru,DIRECT", conf)

    def test_mihomo_rule_order(self):
        conf = (ROOT / "clients/mihomo-remnawave.yaml").read_text()
        self.assertLess(conf.index("RULE-SET,rkn-domains,Garasu"),
                        conf.index("RULE-SET,direct,DIRECT"))
        self.assertIn("include-all: true", conf)
        self.assertIn("MATCH,Garasu", conf)
        self.assertNotIn("dialer-proxy", conf)
        self.assertNotIn("DST-PORT,443,REJECT", conf)

    def test_mihomo_remnawave_injection_and_yaml(self):
        conf = (ROOT / "clients/mihomo-remnawave.yaml").read_text()
        self.assertEqual(conf.count("proxies: # LEAVE THIS LINE!"), 2)
        data = yaml.safe_load(conf)
        self.assertIn("proxies", data)
        self.assertIsNone(data["proxies"])
        groups = {group["name"]: group for group in data["proxy-groups"]}
        self.assertIn("Garasu", groups)
        self.assertIn("Garasu Auto", groups)
        self.assertIn("Garasu Auto", groups["Garasu"]["proxies"])
        self.assertTrue(groups["Garasu Auto"]["include-all"])
        self.assertFalse(groups["Garasu Auto"]["remnawave"]["include-proxies"])
        self.assertEqual(data["rules"][-1], "MATCH,Garasu")
        for key, provider in data["rule-providers"].items():
            self.assertTrue(provider["url"].startswith(
                "https://raw.githubusercontent.com/togahimoko/garasu/main/rules/"
            ), key)
            self.assertEqual(provider["format"], "text")
            self.assertEqual(provider["type"], "http")
        self.assertEqual(data["rule-providers"]["rkn-ips"]["behavior"], "ipcidr")
        self.assertEqual(data["rule-providers"]["rkn-domains"]["behavior"], "domain")

    def test_published_manifest_checksums(self):
        path = ROOT / "install/manifest.json"
        if not path.exists():
            return  # first repo bootstrap before initial scheduled build
        manifest = json.loads(path.read_text())
        self.assertEqual(manifest["name"], "Garasu MAX")
        self.assertEqual(len(manifest["files"]), 17)
        for filename, record in manifest["files"].items():
            data = (ROOT / filename).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), record["sha256"], filename)
            self.assertEqual(len(data), record["bytes"], filename)

    def test_install_links(self):
        path = ROOT / "install/links.json"
        if not path.exists():
            return
        links = json.loads(path.read_text())
        self.assertTrue(links["incy"].startswith(
            "incy://autorouting/onadd/https://raw.githubusercontent.com/togahimoko/garasu/"
        ))
        self.assertTrue(links["happ"].startswith("happ://routing/onadd/"))
        encoded = links["happ"].removeprefix("happ://routing/onadd/")
        happ = json.loads(base64.b64decode(encoded, validate=True))
        self.assertEqual(happ, json.loads((ROOT / "clients/happ.json").read_text()))

    def test_srr_preserves_existing_rules(self):
        spec = importlib.util.spec_from_file_location("garasu_srr", ROOT / "scripts/build_srr.py")
        plugin = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(plugin)
        base = {
            "version": "1",
            "settings": {"disableSubscriptionAccessByPath": False},
            "rules": [
                {"name": "Browser", "responseType": "BROWSER", "conditions": [1]},
                {"name": "Mihomo Clients", "responseType": "MIHOMO", "conditions": [2]},
                {"name": "Singbox Clients", "responseType": "SINGBOX", "conditions": [3]},
                {"name": "Fallback", "responseType": "XRAY_BASE64", "conditions": []},
            ],
        }
        before = json.dumps(base, sort_keys=True)
        links = {
            "incy": "incy://autorouting/onadd/https://example.com/incy.json",
            "happ": "happ://routing/onadd/" + "a" * 2000,
        }
        result = plugin.patch(base, links)
        self.assertEqual(json.dumps(base, sort_keys=True), before)
        self.assertEqual(len(result["rules"]), 6)
        self.assertEqual(result["rules"][0], base["rules"][0])
        self.assertEqual(result["rules"][3], base["rules"][1])
        self.assertEqual(result["rules"][4], base["rules"][2])
        self.assertEqual(result["rules"][5], base["rules"][3])
        self.assertEqual(result["rules"][1]["responseModifications"]["headers"][0]["key"], "autorouting")
        self.assertEqual(result["rules"][2]["responseModifications"]["headers"][0]["key"], "routing")
        self.assertEqual(result["rules"][1]["responseType"], "XRAY_BASE64")
        self.assertEqual(result["rules"][2]["responseType"], "XRAY_BASE64")
        self.assertEqual(plugin.patch(result, links), result)
        with self.assertRaises(ValueError):
            plugin.patch({**base, "rules": base["rules"][:-1]}, links)
        with self.assertRaises(ValueError):
            plugin.patch(base, {**links, "happ": "happ://routing/onadd/" + "b" * 5000})

    def test_no_secrets(self):
        for path in (ROOT / "clients").iterdir():
            content = path.read_text()
            for secret in ("BEGIN PRIVATE KEY", "YOUR_UUID", "SUBSCRIPTION_TOKEN"):
                self.assertNotIn(secret, content)

    def test_subpage_patcher_is_idempotent(self):
        spec = importlib.util.spec_from_file_location("garasu_subpage", ROOT / "scripts/patch_subpage.py")
        plugin = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(plugin)
        source = {"platforms": {"ios": {"apps": [{"name": "Happ", "blocks": [
            {"title": {"en": "Add Subscription"}, "buttons": [
                {"type": "subscriptionLink", "link": "happ://add/{{SUBSCRIPTION_LINK}}"}]}
        ]}]}}}
        links = {"happ": "happ://routing/onadd/abc"}
        updated, changed = plugin.patch(source, links)
        self.assertEqual(changed, ["ios/Happ"])
        self.assertEqual(len(updated["platforms"]["ios"]["apps"][0]["blocks"]), 2)
        updated, _ = plugin.patch(updated, links)
        blocks = updated["platforms"]["ios"]["apps"][0]["blocks"]
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["buttons"][0]["type"], "subscriptionLink")

if __name__ == "__main__":
    unittest.main()
