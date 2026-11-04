"""Static contract for Garasu one-control candidates; no live network tests."""
import json
from pathlib import Path
import unittest
import yaml

BASE = Path(__file__).resolve().parents[1] / "clients" / "one-control"

def yml(name):
    return yaml.safe_load((BASE / name).read_text(encoding="utf-8"))

def js(name):
    return json.loads((BASE / name).read_text(encoding="utf-8"))

class GarasuOneControlContract(unittest.TestCase):
    def test_mihomo_single_visible_group(self):
        text = (BASE / "mihomo-remnawave.yaml").read_text(encoding="utf-8")
        p = yml("mihomo-remnawave.yaml")
        self.assertEqual(text.count("proxies: # LEAVE THIS LINE!"), 2)
        self.assertIsNone(p["proxies"])
        self.assertEqual(p["mixed-port"], 7897)
        self.assertNotIn("tun", p)
        groups = p["proxy-groups"]
        self.assertEqual([g["name"] for g in groups if not g.get("hidden")], ["Garasu"])
        g, auto = groups
        self.assertEqual(g["proxies"], ["Garasu Auto"])
        self.assertEqual(auto["type"], "url-test")
        self.assertTrue(auto["include-all"])
        self.assertFalse(auto["lazy"])
        self.assertEqual(auto["empty-fallback"], "REJECT")
        self.assertEqual(auto["expected-status"], 204)
        self.assertFalse(auto["remnawave"]["include-proxies"])
        self.assertEqual(p["rules"][-1], "MATCH,Garasu")
        self.assertEqual(len(p["rule-providers"]), 13)
        self.assertTrue(all(x["proxy"] == "DIRECT" for x in p["rule-providers"].values()))
        self.assertLess(p["rules"].index("RULE-SET,rkn-domains,Garasu"),
                        p["rules"].index("DOMAIN-SUFFIX,ru,DIRECT"))

    def test_stash_one_group_no_foreign_direct_fallback(self):
        text = (BASE / "stash-remnawave.yaml").read_text(encoding="utf-8")
        p = yml("stash-remnawave.yaml")
        self.assertEqual(text.count("proxies: # LEAVE THIS LINE!"), 2)
        self.assertEqual(len(p["proxy-groups"]), 1)
        group = p["proxy-groups"][0]
        self.assertEqual(group["name"], "Garasu")
        self.assertEqual(group["type"], "url-test")
        self.assertEqual(group["proxies"], ["REJECT"])
        self.assertEqual(p["rules"][-1], "MATCH,Garasu")

    def test_incy_happ_policy_consistency(self):
        a, b = js("incy.json"), js("happ.json")
        self.assertEqual(a, b)
        self.assertEqual(a["Name"], "Garasu")
        self.assertEqual(a["GlobalProxy"], "true")
        self.assertEqual(a["RouteOrder"], "block-proxy-direct")
        self.assertIn("geosite:private", a["DirectSites"])
        self.assertIn("geosite:banned-ru", a["ProxySites"])
        self.assertTrue(a["Geoipurl"].endswith("/geo/geoip.dat"))
        self.assertTrue(a["Geositeurl"].endswith("/geo/geosite.dat"))

    def test_shadowrocket_native_policy(self):
        s = (BASE / "shadowrocket.conf").read_text(encoding="utf-8")
        self.assertIn("[General]", s)
        self.assertIn("[Rule]", s)
        self.assertIn("garasu-one-control-20261104/clients/one-control/shadowrocket.conf", s)
        self.assertIn("FINAL,PROXY,dns-failed", s)
        self.assertLess(s.index("rkn-domains.list,PROXY"), s.index("DOMAIN-SUFFIX,ru,DIRECT"))
        self.assertNotIn("vless://", s)

    def test_singbox_auto_outbound_private_safety(self):
        d = js("singbox-remnawave-1.14.json")
        gs = [o for o in d["outbounds"] if o["tag"] == "→ Remnawave"]
        self.assertEqual(len(gs), 1)
        self.assertEqual(gs[0]["type"], "urltest")
        self.assertIsNone(gs[0]["outbounds"])
        self.assertEqual(gs[0]["url"], "https://cp.cloudflare.com/generate_204")
        self.assertEqual(d["route"]["final"], "→ Remnawave")
        self.assertTrue(any(h["tag"] == "garasu-rules" and h["detour"] == "direct"
                            for h in d["http_clients"]))
        self.assertFalse(any(r.get("outbound") == "→ Remnawave"
                             and (r.get("ip_is_private") is True
                                  or "100.64.0.0/10" in r.get("ip_cidr", []))
                             for r in d["route"]["rules"]))
        self.assertFalse(any(o["type"] == "vless" for o in d["outbounds"]))

    def test_xray_requires_virtual_host_injection(self):
        d = js("xray-advanced-remnawave.json")
        self.assertTrue(d["remnawave"]["addVirtualHostAsOutbound"])
        self.assertEqual({o["tag"] for o in d["outbounds"]}, {"direct", "block"})
        self.assertEqual(d["routing"]["rules"][-1]["outboundTag"], "proxy")
        self.assertFalse(any(r.get("outboundTag") == "proxy"
                             and "geoip:private" in r.get("ip", [])
                             for r in d["routing"]["rules"]))

if __name__ == "__main__":
    unittest.main()
