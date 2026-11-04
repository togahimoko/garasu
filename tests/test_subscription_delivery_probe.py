"""No subscription URL/token may be printed by the refresh diagnostic."""
import io
import json
from pathlib import Path
import unittest

from scripts import probe_subscription_delivery as probe

SECRET = "https://example.invalid/access/VERY_PRIVATE_SUBSCRIPTION_TOKEN"


class FakeResponse:
    def __init__(self, blob, status=200, content_type="text/plain"):
        self._blob = io.BytesIO(blob)
        self.status = status
        self.headers = {"Content-Type": content_type}

    def read(self, size=-1):
        return self._blob.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._blob.close()


class FakeOpener:
    def __init__(self, blob, status=200, kind="text/plain"):
        self.blob = blob
        self.status = status
        self.kind = kind
        self.seen_request = None

    def open(self, request, timeout=8):
        self.seen_request = request
        return FakeResponse(self.blob, self.status, self.kind)


class DeliveryProbe(unittest.TestCase):
    def test_preview_agents_use_isolated_srr_user_agents(self):
        for name in ("incy", "happ", "mihomo", "stash", "singbox", "xray"):
            client = "preview_" + name
            opener = FakeOpener(b"proxies:\n")
            probe.request_once(SECRET, client, "direct", opener=opener)
            self.assertEqual(opener.seen_request.get_header("User-agent"),
                             "garasu-test-" + name)

    def test_detects_independently_each_client_format_without_outputting_secret(self):
        cases = [
            ("mihomo", b"proxies:\n- name: node\n", "yaml"),
            ("mihomo", b"# generated template\nmode: rule\nproxies:\n- name: node\n", "yaml"),
            ("singbox", b'{"outbounds":[]}', "json"),
            ("stash", b"proxy-groups:\n- name: group\n", "yaml"),
            ("happ", b"dmxlc3M6Ly90ZXN0Cg==", "base64"),
            ("browser", b"<html><title>Subscription</title></html>", "html"),
        ]
        for name, response, expected in cases:
            with self.subTest(name=name):
                opener = FakeOpener(response)
                result = probe.request_once(SECRET, name, "direct", opener=opener)
                self.assertEqual(result["format"], expected)
                self.assertEqual(result["status"], 200)
                self.assertNotIn("url", result)
                self.assertNotIn("body", result)
                self.assertNotIn("SECRET", json.dumps(result))
                self.assertNotIn(SECRET, json.dumps(result))
                if name != "browser":
                    self.assertIn(name.lower(), opener.seen_request.get_header("User-agent").lower())

    def test_browser_probe_uses_a_real_browser_user_agent(self):
        opener = FakeOpener(b"<html></html>", kind="text/html")
        probe.request_once(SECRET, "browser", "proxy", opener=opener)
        self.assertIn("Mozilla/5.0", opener.seen_request.get_header("User-agent"))
        self.assertEqual(opener.seen_request.get_header("Accept"), "text/html")

    def test_reports_mobile_routing_headers_without_exposing_values(self):
        class HeaderOpener(FakeOpener):
            def open(self, request, timeout=8):
                response = super().open(request, timeout)
                response.headers["routing"] = "happ://private-routing-value"
                response.headers["autorouting"] = "incy://private-routing-value"
                return response

        result = probe.request_once(SECRET, "happ", "proxy",
                                    opener=HeaderOpener(b"dmxlc3M6Ly90ZXN0Cg=="))
        self.assertTrue(result["has_routing_header"])
        self.assertTrue(result["has_autorouting_header"])
        self.assertNotIn("private-routing-value", json.dumps(result))

    def test_network_errors_do_not_expose_sensitive_subscription_url(self):
        class Fail:
            def open(self, request, timeout=8):
                raise OSError("HTTPS handshake failed: " + SECRET)
        result = probe.request_once(SECRET, "mihomo", "direct", opener=Fail())
        self.assertEqual(result["error"], "OSError")
        self.assertNotIn(SECRET, json.dumps(result))

    def test_rejects_unsafe_input_and_unexpected_clients(self):
        with self.assertRaises(ValueError):
            probe.request_once("http://example.org/secret", "mihomo", "direct")
        with self.assertRaises(ValueError):
            probe.request_once(SECRET, "unexpected", "direct")
        with self.assertRaises(ValueError):
            probe.request_once(SECRET, "mihomo", "unrecognized")

    def test_counts_clash_nodes_and_garasu_sources_without_exposing_them(self):
        providers = sorted(probe.EXPECTED_GARASU_PROVIDERS)
        rules = ([b"  - RULE-SET,rkn-domains,Garasu\n",
                  b"  - RULE-SET,rkn-ips,Garasu\n",
                  b"  - RULE-SET,ads,REJECT\n"] +
                 [b"  - DOMAIN-SUFFIX,local,DIRECT\n"] * 10 +
                 [b"  - DOMAIN-SUFFIX,ru,DIRECT\n",
                  b"  - RULE-SET,ru-ips,DIRECT\n",
                  b"  - MATCH,Garasu\n"])
        raw = (b"proxies:\n  - name: PrivateOne\n    type: vless\n    server: hidden\n    port: 443\n"
               b"  - name: PrivateTwo\n    type: vless\n    server: hidden\n    port: 443\n"
               b"proxy-groups:\n  - name: Garasu\n    type: select\n"
               b"  - name: Garasu Auto\n    type: url-test\n"
               b"rule-providers:\n" +
               b"".join(("  %s:\n    type: inline\n" % n).encode() for n in providers) +
               b"rules:\n" + b"".join(rules))
        result = probe.request_once(SECRET, "clash", "proxy",
                                    opener=FakeOpener(raw, kind="application/x-yaml"))
        self.assertEqual(result["yaml_counts"], {
            "proxies": 2, "proxy_providers": 0, "proxy_groups": 2,
            "rule_providers": 10, "rules": 16})
        self.assertTrue(probe._clash_ready(result))
        self.assertTrue(all(result["yaml_checks"].values()))
        self.assertNotIn("PrivateOne", json.dumps(result))
        self.assertNotIn("PrivateTwo", json.dumps(result))
        result["yaml_counts"]["proxies"] = 0
        self.assertFalse(probe._clash_ready(result))
        result["yaml_counts"]["proxies"] = 2
        result["yaml_checks"]["garasu_route_order_valid"] = False
        self.assertFalse(probe._clash_ready(result))

    def test_live_sized_offline_template_can_be_checked_without_truncation(self):
        release = (Path(__file__).resolve().parents[1] /
                   "release/mihomo/config.yaml").read_bytes()
        self.assertGreater(len(release), 1_000_000)
        self.assertLess(len(release), probe.MAX_BYTES)
        fixtures = (b"proxies:\n"
                    b"  - name: MOCK_ONE\n    type: socks5\n    server: 127.0.0.1\n    port: 18001\n"
                    b"  - name: MOCK_TWO\n    type: socks5\n    server: 127.0.0.1\n    port: 18002\n")
        release = release.replace(b"proxies: # LEAVE THIS LINE!", fixtures, 1)
        result = probe.request_once(SECRET, "clash", "direct",
                                    opener=FakeOpener(release))
        self.assertFalse(result["truncated"])
        self.assertEqual(result["read_bytes"], len(release))
        self.assertTrue(probe._clash_ready(result))
        self.assertTrue(result["yaml_checks"]["garasu_providers_inline"])
        self.assertNotIn("MOCK_ONE", json.dumps(result))

    def test_rejects_remote_provider_even_with_valid_names(self):
        providers = sorted(probe.EXPECTED_GARASU_PROVIDERS)
        raw = ("rule-providers:\n" +
               "".join("  " + name + ":\n    type: http\n" for name in providers))
        self.assertFalse(probe._yaml_checks(raw.encode())["garasu_providers_inline"])

    def test_response_body_is_bounded(self):
        opener = FakeOpener(b"A" * (probe.MAX_BYTES + 4096))
        result = probe.request_once(SECRET, "clash", "direct", opener=opener)
        self.assertEqual(result["read_bytes"], probe.MAX_BYTES)
        self.assertTrue(result["truncated"])


if __name__ == "__main__":
    unittest.main()
