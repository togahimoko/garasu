"""No subscription URL/token may be printed by the refresh diagnostic."""
import io
import json
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
                self.assertIn(name.lower(), opener.seen_request.get_header("User-agent").lower())

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

    def test_response_body_is_bounded(self):
        opener = FakeOpener(b"A" * 200000)
        result = probe.request_once(SECRET, "clash", "direct", opener=opener)
        self.assertEqual(result["read_bytes"], 65536)
        self.assertTrue(result["truncated"])


if __name__ == "__main__":
    unittest.main()
