"""Offline routing and delivery contract for native-client candidates."""
import base64
import json
from pathlib import Path
import unittest
from urllib.parse import parse_qs, urlsplit
from scripts import refresh


ROOT = Path(__file__).resolve().parents[1]


class NativeUnifiedRouting(unittest.TestCase):
    def test_shadowrocket_does_not_direct_foreign_categories(self):
        for path in (ROOT / "clients/shadowrocket.conf",
                     ROOT / "clients/canary/shadowrocket.conf"):
            with self.subTest(path=path):
                profile = path.read_text()
                self.assertIn("MANAGED-CONFIG interval=21600", profile)
                rules = profile.split("[Rule]", 1)[1]
                self.assertNotIn("games.list,DIRECT", rules)
                self.assertNotIn("direct.list,DIRECT", rules)
                self.assertNotIn("direct-ips.list,DIRECT", rules)
                self.assertLess(rules.index("rkn-ips.list,PROXY"),
                                rules.index("ru-ips.list,DIRECT"))
                self.assertIn("DOMAIN-SUFFIX,ru,DIRECT", rules)
                self.assertIn("FINAL,PROXY", rules)

    def test_happ_incy_only_direct_private_and_ru(self):
        for name in ("happ", "incy"):
            with self.subTest(name=name):
                doc = json.loads((ROOT / f"clients/{name}.json").read_text())
                self.assertEqual(doc["DirectSites"],
                                 ["geosite:private", "geosite:category-ru",
                                  "geosite:garasu-ru"])
                self.assertEqual(doc["DirectIp"], ["geoip:private", "geoip:ru"])
                self.assertIn("geosite:banned-ru", doc["ProxySites"])
                self.assertIn("geoip:blocked-ru", doc["ProxyIp"])

    def test_happ_incy_ads_overlap_and_unknown_ru_suffix(self):
        data = (ROOT / "geo/geosite.dat").read_bytes()
        categories = {}
        for number, entry in refresh._protobuf_fields(data):
            if number != 1:
                continue
            fields = list(refresh._protobuf_fields(entry))
            name = next(value.decode().lower() for n, value in fields if n == 1)
            categories[name] = [value for n, value in fields if n == 2]
        self.assertIn("garasu-ru", categories)
        self.assertIn("garasu-ads", categories)
        ru = {dict(refresh._protobuf_fields(item))[2].decode(): item
              for item in categories["garasu-ru"]}
        self.assertEqual(ru["ru"][:2], b"\x08\x02")
        self.assertEqual(ru["su"][:2], b"\x08\x02")
        ads = {dict(refresh._protobuf_fields(item))[2].decode()
               for item in categories["garasu-ads"]}
        self.assertNotIn("ads.youtube.com", ads)
        self.assertIn("1rx.io", ads)
        proxy_names = ("telegram", "github", "discord", "whatsapp",
                       "banned-ru", "hosting", "youtube", "ai", "crypto",
                       "category-geoblock-ru", "twitch-ads")
        proxy = {dict(refresh._protobuf_fields(item))[2].decode()
                 for name in proxy_names for item in categories[name]}
        proxy_parents = {".".join(parts[i:]) for domain in proxy
                         for parts in [domain.split(".")]
                         for i in range(len(parts) - 1)}
        self.assertFalse(ads & proxy_parents)
        for domain in ads:
            parts = domain.split(".")
            self.assertFalse(any(".".join(parts[i:]) in proxy
                                 for i in range(len(parts) - 1)), domain)
        for name in ("happ", "incy"):
            doc = json.loads((ROOT / f"clients/{name}.json").read_text())
            self.assertIn("geosite:garasu-ru", doc["DirectSites"])
            self.assertEqual(doc["BlockSites"], ["geosite:garasu-ads"])

    def test_derived_ads_exclude_proxy_child_and_parent_suffixes(self):
        def category(name, domains):
            entries = [b"\x08\x02" + refresh._protobuf_bytes(2, d.encode())
                       for d in domains]
            payload = refresh._protobuf_bytes(1, name.encode())
            payload += b"".join(refresh._protobuf_bytes(2, e) for e in entries)
            return refresh._protobuf_bytes(1, payload)
        blob = b"".join((
            category("CATEGORY-ADS", ["ads.youtube.com", "example.org", "other.net"]),
            category("WIN-SPY", []),
            category("YOUTUBE", ["youtube.com"]),
            category("GITHUB", ["login.example.org"]),
        ))
        result = refresh.add_native_geosite_categories(
            blob, ("youtube", "github"), ("category-ads", "win-spy"), ("ru", "su"))
        cats = {dict(refresh._protobuf_fields(e))[1].decode().lower(): e
                for n, e in refresh._protobuf_fields(result) if n == 1}
        ads = [dict(refresh._protobuf_fields(v))[2].decode()
               for n, v in refresh._protobuf_fields(cats["garasu-ads"]) if n == 2]
        self.assertEqual(ads, ["other.net"])

    def test_quantumultx_ru_suffixes_are_remote_after_blocked_filters(self):
        links = json.loads((ROOT / "install/links.json").read_text())
        qx = parse_qs(urlsplit(links["quantumultx"]).query)["remote-resource"][0]
        filters = json.loads(qx)["filter_remote"]
        text = "\n".join(filters)
        self.assertLess(text.index("rkn-domains.list"), text.index("ru-tlds.list"))
        self.assertLess(text.index("ads.list"), text.index("ru-tlds.list"))
        self.assertLess(text.index("ru-tlds.list"), text.index("ru-ips.list"))
        self.assertIn("ru-tlds.list, tag=Garasu-ru-tlds, force-policy=direct", text)
        resource = (ROOT / "rules/quantumultx/ru-tlds.list").read_text()
        self.assertIn("host-suffix, ru, direct", resource)
        example = (ROOT / "clients/quantumultx-integration.example").read_text()
        self.assertIn("ru-tlds.list", example.split("[filter_local]", 1)[0])
        self.assertNotIn("host-suffix, ru, direct", example.split("[filter_local]", 1)[1])

    def test_delivery_records_manifest_digest_for_offline_integrity_check(self):
        import hashlib
        links = json.loads((ROOT / "install/links.json").read_text())
        self.assertEqual(links["manifest_url"],
                         "https://raw.githubusercontent.com/togahimoko/garasu/main/install/manifest.json")
        self.assertEqual(links["manifest_sha256"],
                         hashlib.sha256((ROOT / "install/manifest.json").read_bytes()).hexdigest())
        manifest = json.loads((ROOT / "install/manifest.json").read_text())
        for name in ("clients/shadowrocket.conf", "clients/happ.json", "clients/incy.json"):
            with self.subTest(name=name):
                content = (ROOT / name).read_bytes()
                self.assertEqual(manifest["files"][name]["sha256"],
                                 hashlib.sha256(content).hexdigest())
                self.assertEqual(manifest["files"][name]["bytes"], len(content))

    def test_quantumultx_foreign_game_and_direct_resources_are_not_direct(self):
        for name in ("games", "direct", "direct-ips"):
            text = (ROOT / f"rules/quantumultx/{name}.list").read_text()
            self.assertNotIn(", direct", text.lower(), name)
        self.assertIn("host-suffix, steampowered.com, proxy",
                      (ROOT / "rules/quantumultx/games.list").read_text())

    def test_delivery_keeps_personal_nodes_and_no_broad_direct_filters(self):
        links = json.loads((ROOT / "install/links.json").read_text())
        self.assertTrue(links["shadowrocket"].startswith("shadowrocket://config/add/https://"))
        self.assertTrue(links["incy"].startswith("incy://autorouting/onadd/https://"))
        happ = json.loads(base64.b64decode(links["happ"].split("/onadd/", 1)[1], validate=True))
        self.assertEqual(happ, json.loads((ROOT / "clients/happ.json").read_text()))
        qx = parse_qs(urlsplit(links["quantumultx"]).query)["remote-resource"][0]
        filters = json.loads(qx)["filter_remote"]
        for name in ("games", "direct", "direct-ips"):
            self.assertNotIn("Garasu-" + name, " ".join(filters))
        self.assertIn("rkn-ips", links["surge_rulesets"])

    def test_surge_loon_qx_integration_snippets_have_final_proxy(self):
        for name in ("surge", "loon", "quantumultx"):
            with self.subTest(name=name):
                text = (ROOT / f"clients/{name}-integration.example").read_text()
                self.assertIn("{{PERSONAL_PROXY_POLICY}}", text)
                self.assertLess(text.index("rkn-domains.list"), text.index("ru-ips.list"))
                self.assertLess(text.index("ru-ips.list"), text.index("FINAL"))
                self.assertNotIn("games.list", text)
                self.assertNotIn("direct.list", text)


if __name__ == "__main__":
    unittest.main()
