"""Xray/Happ/INCY must implement the same Russian routing policy."""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
DIRECT=("apple","microsoft","twitch","pinterest","steam",
        "epicgames","origin","riot","escapefromtarkov","faceit")
PROXY=("google-play","github","telegram","youtube","discord","twitch-ads",
       "category-geoblock-ru","banned-ru")
BLOCK=("garasu-ads","category-ads","win-spy")
EXACT=("apple.com","microsoft.com","icloud.com","outlook.com")

class MobileRoutingMatrix(unittest.TestCase):
    def test_happ_incy_direct_proxy_block(self):
        for client in ("happ","incy"):
            with self.subTest(client=client):
                d=json.loads((ROOT/f"release/{client}/config.json").read_text())
                self.assertEqual(d["RouteOrder"],"block-proxy-direct")
                for cat in DIRECT:
                    self.assertIn("geosite:"+cat,d["DirectSites"])
                for cat in PROXY:
                    self.assertIn("geosite:"+cat,d["ProxySites"])
                for cat in BLOCK:
                    self.assertIn("geosite:"+cat,d["BlockSites"])
                for domain in EXACT:
                    self.assertIn("domain:"+domain,d["DirectSites"])
                self.assertIn("domain:mtalk.google.com",d["DirectSites"])

    def test_xray_has_specific_proxy_before_direct(self):
        d=json.loads((ROOT/"release/xray/config.json").read_text())
        rules=d["routing"]["rules"]
        def order(tag):
            for i,x in enumerate(rules):
                if tag in x.get("domain",[]): return i,x["outboundTag"]
            raise AssertionError("Missing "+tag)
        for cat in BLOCK:
            self.assertEqual(order("geosite:"+cat)[1],"block")
        for cat in PROXY:
            self.assertEqual(order("geosite:"+cat)[1],"proxy")
        for cat in DIRECT:
            self.assertEqual(order("geosite:"+cat)[1],"direct")
        for domain in EXACT:
            self.assertEqual(order("domain:"+domain)[1],"direct")
        self.assertEqual(order("domain:mtalk.google.com")[1],"direct")
        self.assertLess(order("geosite:twitch-ads")[0],order("geosite:twitch")[0])
        self.assertLess(order("geosite:category-geoblock-ru")[0],order("geosite:category-ru")[0])
        self.assertLess(order("geosite:google-play")[0],order("geosite:apple")[0])

    def test_shadowrocket_contains_foreign_apex_rules(self):
        s=(ROOT/"release/shadowrocket/config.conf").read_text()
        for domain in EXACT:
            self.assertIn("DOMAIN-SUFFIX,"+domain+",DIRECT",s)

if __name__=="__main__":
    unittest.main()
