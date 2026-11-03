"""Fail-closed source validation for Garasu auto-published routing data."""
import unittest
from scripts import refresh


class SourceIntegrityTests(unittest.TestCase):
    def test_invalid_or_global_suffixes_must_not_route_the_world(self):
        for payload in (
            b"+.com\n", b"+.ru\n", b"+.*\n", b"+.example..com\n",
            b"+.-bad.com\n", b"+.bad-.com\n", b"+.bad.com.\n",
            b"+.bad.com\x00\n"
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    refresh.domains(payload, 1)
        result, count = refresh.domains(b"+.example.com\n+.xn--p1ai.ru\n", 2)
        self.assertEqual(count, 2)
        self.assertIn(b"+.example.com", result)

    def test_proxied_ip_sources_cannot_take_very_broad_networks(self):
        for source in ("rkn-ips", "proxy-ips"):
            for network in ("0.0.0.0/0", "0.0.0.0/1", "2000::/3"):
                with self.subTest(source=source, network=network):
                    with self.assertRaises(ValueError):
                        refresh.ip_data((network + "\n").encode(), 1, name=source)
        _, txt, count = refresh.ip_data(b"224.0.0.0/3\n", 1, name="direct-ips")
        self.assertIn(b"224.0.0.0/3", txt)
        self.assertEqual(count, 1)

    def test_mass_swap_detected_even_if_file_size_and_count_similar(self):
        old = b"# comment\n+.one.example\n+.two.example\n+.three.example\n+.four.example\n"
        replaced = b"+.evil1.example\n+.evil2.example\n+.evil3.example\n+.evil4.example\n"
        ordinary = b"+.one.example\n+.two.example\n+.three.example\n+.five.example\n"
        with self.assertRaises(ValueError):
            refresh.validate_source_churn("rules/direct.list", old, replaced, max_churn=.5)
        refresh.validate_source_churn("rules/direct.list", old, ordinary, max_churn=.5)
        refresh.validate_source_churn("rules/direct.list", None, ordinary, max_churn=.5)

    def test_sudden_count_changes_require_manual_review(self):
        previous = {"files": {"rules/direct.list": {"entries": 3000}}}
        refresh.validate_update_budget(
            {"rules/direct.list": {"entries": 2900}}, previous)
        with self.assertRaises(ValueError):
            refresh.validate_update_budget(
                {"rules/direct.list": {"entries": 1000}}, previous)
        with self.assertRaises(ValueError):
            refresh.validate_update_budget(
                {"rules/direct.list": {"entries": 9000}}, previous)

    def test_geodata_structure_and_required_categories(self):
        def vi(n):
            out = bytearray()
            while n > 127:
                out.append((n & 127) | 128)
                n >>= 7
            out.append(n)
            return bytes(out)
        def field(n, content):
            return vi((n << 3) | 2) + vi(len(content)) + content
        data = field(1, field(1, b"ru") + 2 * field(2, b"test"))
        found = refresh.validate_geodata("geoip.dat", data, {"ru": 2})
        self.assertEqual(found["ru"], 2)
        with self.assertRaises(ValueError):
            refresh.validate_geodata("geoip.dat", data, {"ru": 3})
        with self.assertRaises(ValueError):
            refresh.validate_geodata("geoip.dat", data[:-1], {"ru": 2})


if __name__ == "__main__":
    unittest.main()
