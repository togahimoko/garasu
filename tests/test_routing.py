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
        self.assertLess(conf.index("rkn-domains.list,PROXY"), conf.index("DOMAIN-SUFFIX,ru,DIRECT"))
        self.assertLess(conf.index("rkn-ips.list,PROXY"), conf.index("ru-ips.list,DIRECT"))
        self.assertIn("FINAL,PROXY", conf)
        self.assertNotIn("DST-PORT,443,REJECT", conf)
        self.assertNotIn("*.ru,DIRECT", conf)

    def test_mihomo_rule_order(self):
        conf = (ROOT / "clients/mihomo-remnawave.yaml").read_text()
        self.assertLess(conf.index("RULE-SET,rkn-domains,Garasu"),
                        conf.index("DOMAIN-SUFFIX,ru,DIRECT"))
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
        self.assertEqual(len(manifest["files"]), 58)
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
        if "quantumultx" in links:
            self.assertTrue(links["quantumultx"].startswith(
                "quantumult-x:///add-resource?remote-resource="))
            self.assertEqual(len(links["surge_rulesets"]), 10)


    def test_srr_preserves_live_clients_until_promotion(self):
        spec = importlib.util.spec_from_file_location("garasu_srr", ROOT / "scripts/build_srr.py")
        plugin = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(plugin)
        agent = lambda value: [{"headerName": "user-agent", "operator": "STARTS_WITH",
                                "value": value, "caseSensitive": False}]
        base = {
            "version": "1",
            "settings": {"disableSubscriptionAccessByPath": False},
            "rules": [
                {"name": "Browser", "responseType": "BROWSER", "conditions": [1]},
                {"name": "Existing INCY", "responseType": "XRAY_BASE64", "conditions": agent("incy/"),
                 "responseModifications": {"headers": [{"key": "autorouting", "value": "old"}]}},
                {"name": "Existing Happ", "responseType": "XRAY_BASE64", "conditions": agent("happ"),
                 "responseModifications": {"headers": [{"key": "routing", "value": "old"}]}},
                {"name": "Mihomo Clients", "responseType": "MIHOMO", "conditions": agent("mihomo")},
                {"name": "Stash Clients", "responseType": "STASH", "conditions": agent("stash")},
                {"name": "Sing-box Clients", "responseType": "SINGBOX", "conditions": agent("singbox")},
                {"name": "Clash Core Clients", "responseType": "CLASH", "conditions": agent("clash")},
                {"name": "Fallback", "responseType": "XRAY_BASE64", "conditions": []},
            ],
        }
        old = json.dumps(base, sort_keys=True)
        payload = base64.b64encode(json.dumps({"Name": "Garasu MAX"}).encode()).decode()
        links = {"incy": "incy://autorouting/onadd/https://example.com/incy.json",
                 "happ": "happ://routing/onadd/" + payload}
        staged = plugin.patch(base, links, mode="test")
        self.assertEqual(len(staged["rules"]), 13)
        self.assertEqual(staged["rules"][6:], base["rules"][1:])
        self.assertEqual(staged["rules"][0], base["rules"][0])
        self.assertEqual(json.dumps(base, sort_keys=True), old)
        self.assertEqual(plugin.patch(staged, links, mode="test"), staged)
        full = plugin.patch(base, links, mode="full")
        self.assertEqual(len(full["rules"]), 8)
        self.assertEqual([r["name"] for r in full["rules"][:3]],
                         ["Browser", "INCY + Garasu MAX", "Happ + Garasu MAX"])
        self.assertEqual(full["rules"][3]["responseModifications"]["subscriptionTemplate"],
                         "Garasu Mihomo")
        self.assertEqual(full["rules"][4]["responseModifications"]["subscriptionTemplate"],
                         "Garasu Stash")
        self.assertEqual(full["rules"][5]["responseModifications"]["subscriptionTemplate"],
                         "Garasu Singbox")
        self.assertEqual(full["rules"][6:], base["rules"][6:])
        self.assertEqual(plugin.patch(full, links, mode="full"), full)
        self.assertEqual(plugin.patch(staged, links, mode="full"), full)
        with self.assertRaises(ValueError):
            plugin.patch({**base, "rules": base["rules"][:-1]}, links)
        with self.assertRaises(ValueError):
            plugin.patch(base, {**links, "happ": "happ://routing/onadd/" + "a" * 5000})


    def test_singbox_source_conversion(self):
        source = mod.singbox_domains(
            b"# source\n+.youtube.com\n+.github.com\nexample.org\n")
        rule_set = json.loads(source)
        self.assertEqual(rule_set["version"], 3)
        self.assertEqual(rule_set["rules"][0]["domain_suffix"],
                         ["youtube.com", "github.com"])
        self.assertEqual(rule_set["rules"][0]["domain"], ["example.org"])
        ip_set = json.loads(mod.singbox_ips(
            b"# source\n1.2.3.4/32\n2001:db8::/32\n"))
        self.assertEqual(ip_set["rules"][0]["ip_cidr"],
                         ["1.2.3.4/32", "2001:db8::/32"])

    def test_stash_template(self):
        conf = (ROOT / "clients/stash-remnawave.yaml").read_text()
        self.assertEqual(conf.count("proxies: # LEAVE THIS LINE!"), 2)
        data = yaml.safe_load(conf)
        self.assertIsNone(data["proxies"])
        self.assertEqual(data["proxy-groups"][0]["name"], "Garasu")
        self.assertEqual(data["proxy-groups"][0]["proxies"], ["REJECT"])
        self.assertEqual(data["rules"][-1], "MATCH,Garasu")
        for name in ("rkn-domains", "rkn-ips", "ads", "direct"):
            self.assertIn(name, data["rule-providers"])
        rules = data["rules"]
        self.assertLess(rules.index("RULE-SET,rkn-domains,Garasu"),
                        rules.index("DOMAIN-SUFFIX,ru,DIRECT"))
        self.assertLess(rules.index("RULE-SET,rkn-ips,Garasu"),
                        rules.index("RULE-SET,ru-ips,DIRECT,no-resolve"))
        self.assertNotIn("RULE-SET,direct,DIRECT", rules)

    def test_singbox_remnawave_template(self):
        config = json.loads((ROOT / "clients/singbox-remnawave.json").read_text())
        self.assertEqual(config["outbounds"][0]["tag"], "→ Remnawave")
        self.assertIsNone(config["outbounds"][0]["outbounds"])
        self.assertEqual(config["route"]["final"], "→ Remnawave")
        self.assertTrue(config["experimental"]["cache_file"]["enabled"])
        all_tags = {r["tag"] for r in config["route"]["rule_set"]}
        self.assertEqual(len(all_tags), 13)
        self.assertIn("garasu-ru-ips", all_tags)
        for provider in config["route"]["rule_set"]:
            self.assertEqual(provider["format"], "source")
            self.assertIn("/garasu/main/rules/singbox/", provider["url"])
        rules = config["route"]["rules"]
        proxi = next(i for i, r in enumerate(rules) if
                     "garasu-rkn-domains" in r.get("rule_set", []))
        direct = next(i for i, r in enumerate(rules) if
                      "garasu-ru-ips" in r.get("rule_set", []))
        self.assertLess(proxi, direct)
        self.assertEqual(rules[proxi]["outbound"], "→ Remnawave")
        self.assertEqual(rules[direct]["outbound"], "direct")

    def test_xray_advanced_template_requires_virtual_host(self):
        xray = json.loads((ROOT / "clients/xray-advanced-remnawave.json").read_text())
        self.assertTrue(xray["remnawave"]["addVirtualHostAsOutbound"])
        self.assertEqual(xray["routing"]["rules"][-1]["outboundTag"], "proxy")
        self.assertEqual(xray["routing"]["rules"][-1]["network"], "tcp,udp")
        routes = xray["routing"]["rules"]
        proxy_domain = next(i for i, r in enumerate(routes)
                            if "geosite:banned-ru" in r.get("domain", []))
        blocked_ip = next(i for i, r in enumerate(routes)
                          if "geoip:blocked-ru" in r.get("ip", []))
        ru_ip = next(i for i, r in enumerate(routes)
                     if "geoip:ru" in r.get("ip", []))
        self.assertLess(proxy_domain, blocked_ip)
        self.assertLess(blocked_ip, ru_ip)
        self.assertEqual(xray["routing"]["domainStrategy"], "IpOnDemand")
        self.assertEqual([o["tag"] for o in xray["outbounds"]], ["direct", "block"])

    def test_all_singbox_rule_sets_are_published(self):
        base = ROOT / "rules/singbox"
        if not base.exists():
            return
        cfg = json.loads((ROOT / "clients/singbox-remnawave.json").read_text())
        for provider in cfg["route"]["rule_set"]:
            filename = base / (provider["tag"].removeprefix("garasu-") + ".json")
            self.assertTrue(filename.exists(), filename)
            doc = json.loads(filename.read_text())
            self.assertEqual(doc["version"], 3)
            self.assertTrue(doc["rules"])
            self.assertTrue(doc["rules"][0].get("domain_suffix") or
                            doc["rules"][0].get("domain") or
                            doc["rules"][0].get("ip_cidr"))

    def test_surge_and_quantumultx_adapters(self):
        sample = b"# source\n+.example.ru\n+.youtube.com\n"
        surge = mod.surge_domains(sample).decode()
        qx = mod.quantumultx_domains(sample, "proxy").decode()
        self.assertIn("DOMAIN-SUFFIX,example.ru", surge)
        self.assertIn("DOMAIN-SUFFIX,youtube.com", surge)
        self.assertIn("host-suffix, example.ru, proxy", qx)
        self.assertIn("host-suffix, youtube.com, proxy", qx)
        source_ip = b"192.0.2.1/32\n2001:db8::/32\n"
        surge_ip = mod.surge_ips(source_ip).decode()
        qx_ip = mod.quantumultx_ips(source_ip, "direct").decode()
        self.assertIn("IP-CIDR,192.0.2.1/32", surge_ip)
        self.assertIn("IP-CIDR6,2001:db8::/32", surge_ip)
        self.assertIn("ip-cidr, 192.0.2.1/32, direct", qx_ip)
        self.assertIn("ip6-cidr, 2001:db8::/32, direct", qx_ip)
        self.assertEqual(mod.policy_for("ads"), "reject")
        self.assertEqual(mod.policy_for("direct"), "proxy")
        self.assertEqual(mod.policy_for("rkn-domains"), "proxy")

    def test_extended_rule_catalog(self):
        base = ROOT / "rules"
        if not (base / "surge").exists():
            return
        for name in list(mod.DOMAIN) + list(mod.IP):
            self.assertTrue((base / "surge" / (name + ".list")).is_file())
            self.assertTrue((base / "quantumultx" / (name + ".list")).is_file())
            self.assertTrue((base / "singbox" / (name + ".json")).is_file())

    def test_full_policy_domain_examples(self):
        base = ROOT / "rules"
        if not (base / "rkn-domains.list").exists():
            return
        routing = [
            ("rkn-domains", "PROXY"),
            ("youtube", "PROXY"),
            ("discord", "PROXY"),
            ("ai", "PROXY"),
            ("crypto", "PROXY"),
            ("proxy", "PROXY"),
            ("ads", "REJECT"),
            ("games", "DIRECT"),
            ("direct", "DIRECT"),
        ]
        sets = {}
        for name, _ in routing:
            sets[name] = set(
                line.strip().lower().removeprefix("+.")
                for line in (base / (name + ".list")).read_text().splitlines()
                if line.strip() and not line.startswith("#")
            )
        def route(domain):
            domain = domain.lower()
            for name, policy in routing:
                if any(domain == suffix or domain.endswith("." + suffix)
                       for suffix in sets[name]):
                    return policy
            return "PROXY"
        cases = {
            "www.youtube.com": "PROXY",
            "r1.googlevideo.com": "PROXY",
            "chatgpt.com": "PROXY",
            "api.github.com": "PROXY",
            "www.4pda.ru": "PROXY",
            "www.yandex.ru": "DIRECT",
            "ad.mail.ru": "REJECT",
            "unlisted.foreign.test": "PROXY",
        }
        for domain, expected in cases.items():
            self.assertEqual(route(domain), expected, domain)

    def test_no_secrets(self):
        for path in (ROOT / "clients").rglob("*"):
            if not path.is_file():
                continue
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
