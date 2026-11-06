"""Guard DNS bootstrap against RU ISP DoH/DoT blocking regressions."""
import json
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]

ALIASES = {
    "clients/mihomo-remnawave.yaml": "release/mihomo/config.yaml",
    "clients/shadowrocket.conf": "release/shadowrocket/config.conf",
    "clients/stash-remnawave.yaml": "release/stash/config.yaml",
    "clients/incy.json": "release/incy/config.json",
    "clients/happ.json": "release/happ/config.json",
}


class DNSBootstrapContract(unittest.TestCase):
    def test_public_delivery_and_source_are_identical(self):
        for source, published in ALIASES.items():
            with self.subTest(source=source):
                self.assertEqual((ROOT / source).read_bytes(), (ROOT / published).read_bytes())

    def test_mihomo_proxy_doh_and_nonrecursive_node_bootstrap(self):
        config = yaml.safe_load((ROOT / "release/mihomo/config.yaml").read_text())
        dns = config["dns"]
        self.assertIs(dns["prefer-h3"], False)
        self.assertEqual(dns["proxy-server-nameserver"], ["tcp://77.88.8.8:53", "tcp://77.88.8.1:53"])
        self.assertEqual(dns["direct-nameserver"], ["system"])
        self.assertEqual(dns["default-nameserver"], ["77.88.8.8", "77.88.8.1"])
        self.assertNotIn("dns.google", str(dns))
        self.assertNotIn("dns.cloudflare.com", str(dns))
        self.assertNotIn("8.8.8.8", str(dns))
        self.assertNotIn("1.1.1.1", str(dns))
        self.assertEqual(
            dns["nameserver"],
            ["https://9.9.9.9/dns-query#Garasu", "https://149.112.112.112/dns-query#Garasu"],
        )
        group = next(p for p in config["proxy-groups"] if p["name"] == "Garasu")
        self.assertEqual(group["type"], "url-test")
        self.assertEqual(config["rules"][-1], "MATCH,Garasu")

    def test_shadowrocket_has_no_direct_public_doh(self):
        content = (ROOT / "release/shadowrocket/config.conf").read_text()
        self.assertIn("dns-server = system\n", content)
        self.assertIn("proxy-dns-server = system\n", content)
        self.assertIn("dns-direct-system = true\n", content)
        self.assertIn("dns-direct-fallback-proxy = true\n", content)
        general = content.partition("[Rule]")[0]
        self.assertNotIn("dns-server = https:", general)
        self.assertIn("FINAL,PROXY,dns-failed", content)

    def test_stash_does_not_dial_foreign_doh_directly(self):
        config = yaml.safe_load((ROOT / "release/stash/config.yaml").read_text())
        dns = config["dns"]
        self.assertEqual(dns["nameserver"], ["system"])
        self.assertEqual(dns["default-nameserver"], ["system"])
        self.assertEqual(dns["proxy-server-nameserver"], ["system"])

    def test_incy_and_happ_domestic_dns_is_unencrypted_local_udp(self):
        for path in ("release/incy/config.json", "release/happ/config.json"):
            with self.subTest(path=path):
                cfg = json.loads((ROOT / path).read_text())
                self.assertEqual(cfg["DomesticDNSType"], "DoU")
                self.assertEqual(cfg["DomesticDNSIP"], "77.88.8.8")
                self.assertEqual(cfg["DomesticDNSDomain"], "")
                self.assertEqual(cfg["RemoteDNSType"], "DoH")
                self.assertEqual(cfg["RemoteDNSDomain"], "https://dns.google/dns-query")
                self.assertNotIn("common.dot.dns.yandex.net", cfg["DnsHosts"])
                self.assertTrue(cfg["Geoipurl"].endswith("/geo/geoip.dat"))


if __name__ == "__main__":
    unittest.main()
