import unittest

from scripts.routing_policy import (
    classify_domain,
    classify_ip,
    validate_source_metadata,
)


class UnifiedPolicyTests(unittest.TestCase):
    def test_blocked_domain_wins_over_reviewed_direct_and_ru(self):
        categories = {
            "blocked": {"+.blocked.ru"},
            "direct": {"service.blocked.ru"},
            "ru": {"service.blocked.ru"},
        }
        self.assertEqual(classify_domain("service.blocked.ru", categories), "PROXY")

    def test_blocked_domain_wins_over_ads(self):
        categories = {"blocked": {"ads.service.ru"}, "ads": {"ads.service.ru"}}
        self.assertEqual(classify_domain("ads.service.ru", categories), "PROXY")

    def test_ordinary_ru_domain_uses_direct_fallback(self):
        self.assertEqual(classify_domain("example.ru", {}), "DIRECT")
        self.assertEqual(classify_domain("example.su", {}), "DIRECT")
        self.assertEqual(classify_domain("example.рф", {}), "DIRECT")

    def test_unknown_foreign_domain_uses_proxy(self):
        self.assertEqual(classify_domain("example.com", {}), "PROXY")

    def test_reviewed_foreign_direct_is_explicit(self):
        self.assertEqual(classify_domain("example.com", {"direct": {"example.com"}}), "DIRECT")
        self.assertEqual(classify_domain("otherexample.com", {"direct": {"example.com"}}), "PROXY")

    def test_local_names_win_over_other_categories(self):
        categories = {"blocked": {"printer.lan"}, "ads": {"printer.lan"}}
        self.assertEqual(classify_domain("printer.lan", categories), "DIRECT")
        self.assertEqual(classify_domain("localhost", {}), "DIRECT")

    def test_private_ip_uses_direct_for_both_families(self):
        self.assertEqual(classify_ip("192.168.1.2", {}), "DIRECT")
        self.assertEqual(classify_ip("fd00::2", {}), "DIRECT")

    def test_lan_ip_wins_over_blocked(self):
        categories = {"blocked": {"192.168.1.0/24"}}
        self.assertEqual(classify_ip("192.168.1.2", categories), "DIRECT")

    def test_blocked_ru_ip_wins_over_direct_and_ru(self):
        categories = {
            "blocked": {"203.0.113.0/24"},
            "direct": {"203.0.113.8/32"},
            "ru": {"203.0.113.0/24"},
        }
        self.assertEqual(classify_ip("203.0.113.8", categories), "PROXY")

    def test_ru_ip_and_unknown_foreign_ip(self):
        categories = {"ru": {"2001:db8:1::/48"}}
        self.assertEqual(classify_ip("2001:db8:1::5", categories), "DIRECT")
        self.assertEqual(classify_ip("2001:db8:2::5", categories), "PROXY")

    def test_reviewed_foreign_ip_direct_is_explicit(self):
        self.assertEqual(
            classify_ip("203.0.113.8", {"direct": {"203.0.113.8/32"}}),
            "DIRECT",
        )

    def test_source_metadata_requires_full_pinned_blocked_inputs(self):
        revision = "a" * 40
        good = {
            "blocked_domains": {
                "dataset": "refilter-domain-full",
                "url": f"https://raw.githubusercontent.com/DigneZzZ/routing/{revision}/release/refilter-domain-full.list",
                "revision": revision,
                "sha256": "b" * 64,
                "entries": 100,
            },
            "blocked_ips": {
                "dataset": "refilter-ip-full",
                "url": f"https://raw.githubusercontent.com/DigneZzZ/routing/{revision}/release/refilter-ip-full.list",
                "revision": revision,
                "sha256": "c" * 64,
                "entries": 50,
            },
        }
        validate_source_metadata(good)
        for bad in (
            {"blocked_domains": good["blocked_domains"]},
            {**good, "blocked_domains": {**good["blocked_domains"], "dataset": "refilter-domain"}},
            {**good, "blocked_ips": {**good["blocked_ips"], "sha256": ""}},
            {**good, "blocked_ips": {**good["blocked_ips"], "url": "https://raw.githubusercontent.com/DigneZzZ/routing/main/release/refilter-ip-full.list"}},
            {**good, "blocked_domains": {**good["blocked_domains"], "url": f"https://example.test/DigneZzZ/routing/{revision}/release/refilter-domain-full.list"}},
            {**good, "blocked_domains": {**good["blocked_domains"], "url": f"https://raw.githubusercontent.com/other/routing/{revision}/release/refilter-domain-full.list"}},
            {**good, "blocked_ips": {**good["blocked_ips"], "url": f"https://raw.githubusercontent.com/{revision}/DigneZzZ/routing/release/refilter-ip-full.list"}},
            {**good, "blocked_ips": {**good["blocked_ips"], "revision": "d" * 40}},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_source_metadata(bad)


if __name__ == "__main__":
    unittest.main()
