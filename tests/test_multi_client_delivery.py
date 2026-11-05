"""Regression tests: all subscription clients receive compatible nodes, not empty YAML."""
import base64
import io
import json
import unittest

from scripts import probe_subscription_delivery as probe


class Response:
    status = 200

    def __init__(self, payload, content_type="text/plain", headers=None):
        self.file = io.BytesIO(payload)
        self.headers = {"Content-Type": content_type, **(headers or {})}

    def read(self, size=-1):
        return self.file.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.file.close()


class Opener:
    def __init__(self, payload, mime="text/plain", headers=None):
        self.payload, self.mime, self.headers = payload, mime, headers

    def open(self, request, timeout=8):
        return Response(self.payload, self.mime, self.headers)


URL = "https://example.invalid/PRIVATE_TOKEN"
WS = ("vless://USER_ID@node.example:443?type=ws&security=tls"
      "&path=%2Fws&sni=node.example#CDN")
REALITY = ("vless://USER_ID@node.example:443?type=tcp&security=reality"
           "&flow=xtls-rprx-vision#REALITY")


class MultiClientDeliveryTests(unittest.TestCase):
    def test_each_real_client_has_dispatch_ua_and_expected_format(self):
        for client in ("mihomo", "clash", "stash", "singbox", "happ", "incy",
                       "shadowrocket", "browser", "xray", "xray-json"):
            self.assertIn(client, probe.AGENTS)
            self.assertIn(client, probe.EXPECTED_FORMATS)

    def test_base64_nodes_include_vless_ws_and_reality(self):
        blob = base64.b64encode((WS + "\n" + REALITY + "\n").encode())
        summary = probe._node_summary(blob, "base64")
        self.assertEqual(summary, {"node_count": 2,
                                   "vless_ws_tls_443": 1,
                                   "vless_reality_443": 1})
        self.assertNotIn("USER_ID", json.dumps(summary))
        self.assertNotIn("node.example", json.dumps(summary))

    def test_mihomo_yaml_parses_nodes_without_exposing_identity(self):
        raw = b"""mode: rule
proxies:
  - name: CDN
    type: vless
    server: private.example
    port: 443
    network: ws
    tls: true
    ws-opts:
      path: /ws
  - name: Reality
    type: vless
    server: private.example
    port: 443
    network: tcp
    tls: true
proxy-groups:
  - name: Garasu
    type: url-test
"""
        count = probe._node_summary(raw, "yaml")
        self.assertEqual(count["node_count"], 2)
        self.assertEqual(count["vless_ws_tls_443"], 1)
        self.assertNotIn("private.example", json.dumps(count))

    def test_classic_clash_empty_yaml_is_not_claimed_healthy(self):
        raw = b"proxies: []\nproxy-groups:\n  - name: Garasu\n    type: url-test\n"
        report = probe.request_once(URL, "clash", "proxy",
                                    opener=Opener(raw, "application/x-yaml"))
        self.assertEqual(report["format"], "yaml")
        self.assertEqual(report["nodes"]["node_count"], 0)
        self.assertIn("NO_COMPATIBLE_NODES", report["issues"])
        self.assertNotIn("PRIVATE_TOKEN", json.dumps(report))

    def test_incy_and_happ_require_distinct_routing_headers(self):
        encoded = base64.b64encode((WS + "\n").encode())
        incy = probe.request_once(URL, "incy", "proxy", opener=Opener(encoded))
        happ = probe.request_once(URL, "happ", "proxy", opener=Opener(encoded))
        self.assertIn("INCY_AUTOROUTING_HEADER_MISSING", incy["issues"])
        self.assertIn("HAPP_ROUTING_HEADER_MISSING", happ["issues"])
        self.assertEqual(incy["nodes"]["vless_ws_tls_443"], 1)
        incy_ok = probe.request_once(
            URL, "incy", "proxy", opener=Opener(encoded,
                                               headers={"autorouting": "PRIVATE"}))
        self.assertFalse(incy_ok["issues"])

    def test_shadowrocket_marks_routing_setup_separately(self):
        encoded = base64.b64encode((WS + "\n").encode())
        report = probe.request_once(URL, "shadowrocket", "proxy",
                                    opener=Opener(encoded))
        self.assertFalse(report["issues"])
        self.assertEqual(report["routing_profile"], "separate-managed-config")
        self.assertEqual(report["nodes"]["vless_ws_tls_443"], 1)

    def test_singbox_json_detects_vless_ws_node(self):
        data = {"outbounds": [
            {"type": "urltest", "tag": "Auto", "outbounds": ["CDN"]},
            {"type": "vless", "tag": "CDN", "server": "node.example",
             "server_port": 443, "tls": {"enabled": True},
             "transport": {"type": "ws", "path": "/ws"}},
            {"type": "direct", "tag": "DIRECT"}]}
        blob = json.dumps(data).encode()
        summary = probe._node_summary(blob, "json")
        self.assertEqual(summary["node_count"], 1)
        self.assertEqual(summary["vless_ws_tls_443"], 1)

    def test_format_mismatch_detected(self):
        result = probe.request_once(URL, "mihomo", "proxy",
                                    opener=Opener(base64.b64encode(WS.encode())))
        self.assertIn("FORMAT_MISMATCH", result["issues"])


if __name__ == "__main__":
    unittest.main()
