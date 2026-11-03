"""Verify read-only Garasu delivery diagnostics without private URLs."""
import hashlib
import unittest
from scripts import check_delivery


class DeliveryProbeTests(unittest.TestCase):
    def test_verify_asset_hash_and_size(self):
        payload=b"+.example.org\n"
        meta={"files":{"rules/example.list":{"sha256":hashlib.sha256(payload).hexdigest(),"bytes":len(payload)}}}
        self.assertTrue(check_delivery.verify_asset("rules/example.list",payload,meta))
        for invalid in (payload+b"+.evil.example\n",b"X"+payload[1:]):
            with self.subTest(value=invalid):
                with self.assertRaises(ValueError):
                    check_delivery.verify_asset("rules/example.list",invalid,meta)
        with self.assertRaises(ValueError):
            check_delivery.verify_asset("rules/other.list",payload,meta)

    def test_remote_mirror_url_must_have_valid_tls_without_credentials(self):
        self.assertEqual(check_delivery.validate_base_url(
            "https://rules.example.org/garasu/"),"https://rules.example.org/garasu")
        for url in ("http://rules.example.org","https://u:p@rules.example.org",
                    "https://rules.example.org/file?token=hidden",
                    "https://rules.example.org/#some",
                    "https://rules.example.org/a/../b"):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    check_delivery.validate_base_url(url)


if __name__=="__main__":
    unittest.main()
