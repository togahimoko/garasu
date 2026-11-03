"""Cross-client static contract for one Czech Remnawave node.

These checks validate template wiring and priorities, not physical node uptime,
real mobile app import, TLS, DNS reachability or Russian ISP behaviour.
"""
import json
from pathlib import Path
import unittest
from urllib.parse import urlparse
import yaml

ROOT = Path(__file__).resolve().parents[1]
CANARY = ROOT / "clients" / "canary"
BASE = "https://raw.githubusercontent.com/togahimoko/garasu/main/"
CATEGORIES = (
    "rkn-domains", "rkn-ips", "youtube", "discord", "ai", "crypto",
    "proxy", "proxy-ips", "ads", "games", "direct", "direct-ips", "ru-ips",
)
DOMAIN_CATEGORIES = {"rkn-domains", "youtube", "discord", "ai", "crypto",
                     "proxy", "ads", "games", "direct"}
PROXY_CATEGORIES = {"rkn-domains", "rkn-ips", "youtube", "discord",
                    "ai", "crypto", "proxy", "proxy-ips"}


def yaml_client(name):
    return yaml.safe_load((CANARY / name).read_text(encoding="utf-8"))


def json_client(name):
    return json.loads((ROOT / "clients" / name).read_text(encoding="utf-8"))


def singbox_canary():
    return json.loads((CANARY / "singbox-remnawave-1.14.json").read_text(encoding="utf-8"))


def assert_public_asset(case, url):
    case.assertTrue(url.startswith(BASE), "Unexpected rule host: " + url)
    relative = url[len(BASE):]
    case.assertNotIn("..", Path(relative).parts)
    case.assertTrue((ROOT / relative).is_file(), "Referenced but not published: " + relative)


class CrossClientOneNodeContract(unittest.TestCase):
    def test_mihomo_and_stash_use_only_remnawave_injected_nodes(self):
        mihomo = yaml_client("mihomo-remnawave.yaml")
        stash = yaml_client("stash-remnawave.yaml")
        for name, profile in (("Mihomo", mihomo), ("Stash", stash)):
            with self.subTest(client=name):
                self.assertIsNone(profile["proxies"])
                self.assertTrue(all(p.get("type") not in ("vless", "trojan", "ss")
                                    for p in (profile["proxies"] or [])))
                self.assertNotIn("dialer-proxy", (CANARY / (
                    "mihomo-remnawave.yaml" if name == "Mihomo"
                    else "stash-remnawave.yaml")).read_text())
        groups = {x["name"]: x for x in mihomo["proxy-groups"]}
        self.assertEqual(groups["Garasu"]["proxies"], ["Garasu Auto"])
        self.assertTrue(groups["Garasu Auto"]["include-all"])
        self.assertFalse(groups["Garasu Auto"]["remnawave"]["include-proxies"])
        self.assertIsNone(groups["Garasu Auto"]["proxies"])
        self.assertFalse(mihomo["profile"]["store-selected"])
        self.assertIsNone(stash["proxy-groups"][0]["proxies"])
        self.assertEqual(stash["proxy-groups"][0]["type"], "url-test")
        self.assertFalse(stash["proxy-groups"][0].get("lazy", True))

    def test_private_network_first_on_all_canaries(self):
        private = ("DOMAIN-SUFFIX,localhost,DIRECT", "DOMAIN-SUFFIX,local,DIRECT",
                   "DOMAIN-SUFFIX,lan,DIRECT", "DOMAIN-SUFFIX,home.arpa,DIRECT",
                   "IP-CIDR,100.64.0.0/10,DIRECT,no-resolve")
        for name in ("mihomo-remnawave.yaml", "stash-remnawave.yaml"):
            with self.subTest(client=name):
                rules = yaml_client(name)["rules"]
                first_remote = rules.index("RULE-SET,rkn-domains,Garasu")
                for item in private:
                    self.assertIn(item, rules)
                    self.assertLess(rules.index(item), first_remote)
                self.assertEqual(rules[-1], "MATCH,Garasu")
        shadow = (CANARY / "shadowrocket.conf").read_text(encoding="utf-8")
        self.assertLess(shadow.index("DOMAIN-SUFFIX,local,DIRECT"),
                        shadow.index("rkn-domains.list,PROXY"))
        self.assertLess(shadow.index("IP-CIDR,100.64.0.0/10,DIRECT"),
                        shadow.index("rkn-ips.list,PROXY"))
        sb = singbox_canary()["route"]["rules"]
        local_idx = next(i for i, r in enumerate(sb) if "local" in r.get("domain_suffix", []))
        private_idx = next(i for i, r in enumerate(sb) if r.get("ip_is_private"))
        remote_idx = next(i for i, r in enumerate(sb)
                          if "garasu-rkn-domains" in r.get("rule_set", []))
        self.assertLess(local_idx, remote_idx)
        self.assertLess(private_idx, remote_idx)

    def test_exception_priority_before_ru_direct(self):
        for name in ("mihomo-remnawave.yaml", "stash-remnawave.yaml"):
            rules = yaml_client(name)["rules"]
            self.assertLess(rules.index("RULE-SET,rkn-domains,Garasu"),
                            rules.index("DOMAIN-SUFFIX,ru,DIRECT"))
            self.assertLess(rules.index("RULE-SET,rkn-ips,Garasu,no-resolve"),
                            rules.index("RULE-SET,ru-ips,DIRECT,no-resolve"))
            self.assertLess(rules.index("RULE-SET,ads,REJECT"),
                            rules.index("MATCH,Garasu"))
        shadow = (CANARY / "shadowrocket.conf").read_text(encoding="utf-8")
        self.assertLess(shadow.index("rkn-domains.list,PROXY"),
                        shadow.index("DOMAIN-SUFFIX,ru,DIRECT"))
        self.assertLess(shadow.index("rkn-ips.list,PROXY"),
                        shadow.index("ru-ips.list,DIRECT"))
        sb = singbox_canary()["route"]["rules"]
        self.assertLess(
            next(i for i, r in enumerate(sb) if "garasu-rkn-ips" in r.get("rule_set", [])),
            next(i for i, r in enumerate(sb) if "garasu-ru-ips" in r.get("rule_set", [])),
        )
        self.assertEqual(singbox_canary()["route"]["final"], "→ Remnawave")

    def test_rule_delivery_urls_exist_for_every_canary(self):
        for name in ("mihomo-remnawave.yaml", "stash-remnawave.yaml"):
            providers = yaml_client(name)["rule-providers"]
            self.assertEqual(set(providers), set(CATEGORIES))
            for cat, info in providers.items():
                with self.subTest(client=name, cat=cat):
                    expected = "/rules/" + cat + (
                        ".list" if cat in DOMAIN_CATEGORIES else ".cidr")
                    self.assertTrue(info["url"].endswith(expected))
                    self.assertEqual(info["behavior"],
                                     "domain" if cat in DOMAIN_CATEGORIES else "ipcidr")
                    self.assertEqual(info["format"], "text")
                    assert_public_asset(self, info["url"])
        sb = singbox_canary()
        providers = sb["route"]["rule_set"]
        self.assertEqual({x["tag"] for x in providers},
                         {"garasu-" + x for x in CATEGORIES})
        for item in providers:
            self.assertEqual(item["http_client"], "garasu-rules")
            self.assertEqual(item["format"], "source")
            assert_public_asset(self, item["url"])
        shadow = (CANARY / "shadowrocket.conf").read_text(encoding="utf-8")
        for cat in CATEGORIES:
            with self.subTest(client="Shadowrocket", cat=cat):
                suffix = ".list"
                link = BASE + "rules/" + cat + suffix
                self.assertIn(link, shadow)
                assert_public_asset(self, link)

    def test_dns_bootstrap_paths_explicit_on_mihomo_and_singbox(self):
        dns = yaml_client("mihomo-remnawave.yaml")["dns"]
        self.assertEqual(dns["proxy-server-nameserver"], ["system"])
        self.assertEqual(dns["direct-nameserver"], ["system"])
        sb = singbox_canary()
        local = next(d for d in sb["dns"]["servers"] if d["tag"] == "local")
        self.assertEqual(local["type"], "local")
        self.assertNotIn("server", local)
        self.assertEqual(sb["route"]["default_domain_resolver"], "local")
        self.assertEqual(sb["route"]["default_http_client"], "garasu-rules")
        self.assertTrue(any(c.get("tag") == "garasu-rules" and
                            c.get("detour") == "→ Remnawave"
                            for c in sb["http_clients"]))
        self.assertEqual(sb["route"]["final"], "→ Remnawave")

    def test_remnawave_singbox_and_xray_injection_only(self):
        sb = singbox_canary()
        selectors = [x for x in sb["outbounds"] if x.get("type") == "selector"]
        self.assertEqual(len(selectors), 1)
        self.assertIsNone(selectors[0]["outbounds"])
        self.assertNotIn("dialer-proxy", json.dumps(sb))
        xray = json_client("xray-advanced-remnawave.json")
        self.assertTrue(xray["remnawave"]["addVirtualHostAsOutbound"])
        self.assertNotIn("proxy", [o["tag"] for o in xray["outbounds"]])
        routes = xray["routing"]["rules"]
        self.assertLess(
            next(i for i, r in enumerate(routes) if "geoip:blocked-ru" in r.get("ip", [])),
            next(i for i, r in enumerate(routes) if "geoip:ru" in r.get("ip", [])),
        )
        self.assertEqual(routes[-1]["outboundTag"], "proxy")

    def test_happ_incy_policy_parity_and_geo_assets(self):
        inc, hap = json_client("incy.json"), json_client("happ.json")
        for d in (inc, hap):
            d.pop("LastUpdated", None)
        self.assertEqual(inc, hap)
        self.assertEqual(inc["RouteOrder"], "block-proxy-direct")
        self.assertIn("geosite:private", inc["DirectSites"])
        self.assertIn("geoip:ru", inc["DirectIp"])
        self.assertIn("geosite:banned-ru", inc["ProxySites"])
        self.assertIn("geoip:blocked-ru", inc["ProxyIp"])
        for key in ("Geoipurl", "Geositeurl"):
            assert_public_asset(self, inc[key])
        self.assertNotIn("proxies", inc)
        self.assertNotIn("outbounds", inc)

    def test_all_client_formats_and_generated_adapters_present(self):
        for path in (
            "clients/mihomo-remnawave.yaml",
            "clients/stash-remnawave.yaml",
            "clients/shadowrocket.conf",
            "clients/singbox-remnawave-1.14.json",
            "clients/xray-advanced-remnawave.json",
            "clients/incy.json", "clients/happ.json",
            "install/links.json", "install/manifest.json",
        ):
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file())
        links = json.loads((ROOT / "install/links.json").read_text(encoding="utf-8"))
        self.assertTrue(links["incy"].startswith("incy://"))
        self.assertTrue(links["happ"].startswith("happ://"))
        for cat in CATEGORIES:
            for fmt in ("surge", "quantumultx", "singbox"):
                suffix = ".json" if fmt == "singbox" else ".list"
                self.assertTrue((ROOT / "rules" / fmt / (cat + suffix)).is_file())
        for name in ("mihomo_template", "stash_template", "singbox_template"):
            assert_public_asset(self, links[name])


if __name__ == "__main__":
    unittest.main()
