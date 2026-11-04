import base64
import json
from pathlib import Path
import tempfile
import unittest

from scripts import audit_public_exposure


class GarasuPublicExposureTests(unittest.TestCase):
    def test_public_bundle_contains_no_credentials_or_published_nodes(self):
        root = Path(__file__).resolve().parents[1]
        violations = audit_public_exposure.scan_release(root)
        self.assertEqual(violations, [], "\n".join(violations))

    def test_rejects_personal_subscription_urls_and_real_node_uris(self):
        for content in (
            "vless://12345678-1234-4123-8123-123456789abc@vpn.example:443",
            "trojan://secret-value@vpn.example:443",
            "https://vpn.example/sub/12345678-1234-4123-8123-123456789abc",
            "Authorization: Bearer abcdefghijklmnopqrs",
            "-----BEGIN PRIVATE KEY-----",
            "https://vpn.example/?token=abcdef1234567890",
        ):
            with self.subTest(content=content[:30]):
                self.assertTrue(
                    audit_public_exposure.find_exposures("clients/sample.txt", content),
                    "Sensitive content was accepted",
                )

    def test_public_rules_urls_and_dns_are_allowed(self):
        legitimate = (
            "https://raw.githubusercontent.com/togahimoko/garasu/main/rules/ai.list\n"
            "dns-server = https://dns.google/dns-query\n"
            "DOMAIN-SUFFIX,ru,DIRECT\n"
        )
        self.assertEqual(
            audit_public_exposure.find_exposures("clients/shadowrocket.conf", legitimate),
            [],
        )

    def test_happ_link_must_not_embed_nodes_or_sensitive_keys(self):
        payload = {
            "Name": "Garasu MAX",
            "Geoipurl": "https://raw.githubusercontent.com/togahimoko/garasu/main/geo/geoip.dat",
            "Geositeurl": "https://raw.githubusercontent.com/togahimoko/garasu/main/geo/geosite.dat",
            "ProxySites": ["geosite:youtube"],
        }
        link = "happ://routing/onadd/" + base64.b64encode(
            json.dumps(payload).encode()
        ).decode()
        self.assertEqual(audit_public_exposure.check_happ_link(link), [])
        payload["privateKey"] = "should-never-be-public"
        bad = "happ://routing/onadd/" + base64.b64encode(
            json.dumps(payload).encode()
        ).decode()
        self.assertTrue(audit_public_exposure.check_happ_link(bad))

    def test_deny_embedded_proxy_endpoints_in_public_template(self):
        self.assertTrue(audit_public_exposure.find_exposures(
            "clients/mihomo-remnawave.yaml",
            "proxies:\n  - name: node\n    type: vless\n    server: edge.example\n    port: 443\n",
        ))
        self.assertTrue(audit_public_exposure.find_exposures(
            "clients/shadowrocket.conf",
            "[Proxy]\nprivate-server = vless, edge.example, 443\n",
        ))

    def test_dns_and_loopback_inbound_are_not_private_exit_nodes(self):
        data = {
            "dns": {"servers": [{"type": "tls", "server": "1.1.1.1"}]},
            "inbounds": [{"type": "mixed", "listen": "127.0.0.1",
                          "platform": {"http_proxy": {
                              "server": "127.0.0.1", "server_port": 2412}}}],
            "outbounds": [{"type": "direct", "tag": "direct"}],
        }
        self.assertEqual(
            audit_public_exposure.find_exposures(
                "clients/singbox-remnawave.json", json.dumps(data)), [])

    def test_detects_actual_singbox_outbound_endpoint(self):
        data = {
            "dns": {"servers": [{"type": "tls", "server": "1.1.1.1"}]},
            "outbounds": [{"type": "vless", "server": "edge.example",
                           "server_port": 443, "uuid": "test-user-id"}],
        }
        self.assertTrue(
            audit_public_exposure.find_exposures(
                "clients/singbox-remnawave.json", json.dumps(data)))

    def test_nested_canary_files_are_scanned_for_secrets(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private = root / "clients" / "canary"
            private.mkdir(parents=True)
            (private / "unsafe.yaml").write_text(
                "proxies:\n  - name: Example\n"
                "    type: vless\n    server: secret.example.net\n    port: 443\n",
                encoding="utf-8",
            )
            self.assertTrue(audit_public_exposure.scan_release(root),
                            "Recursive canary scans must detect embedded nodes")

    def test_recursive_release_templates_are_audited(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file = root / "release" / "mihomo" / "unsafe.yaml"
            file.parent.mkdir(parents=True)
            file.write_text(
                "proxies:\n  - name: Subscriber\n    type: vless\n"
                "    server: private.example\n    port: 443\n",
                encoding="utf-8",
            )
            self.assertTrue(audit_public_exposure.scan_release(root))

    def test_no_full_subscription_urls_in_install_links(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "install").mkdir()
            (root / "clients").mkdir()
            (root / "install" / "links.json").write_text(json.dumps({
                "private_subscription": "https://vpn.example/sub/12345678-1234-4123-8123-123456789abc"
            }))
            self.assertTrue(audit_public_exposure.scan_release(root))


if __name__ == "__main__":
    unittest.main()
