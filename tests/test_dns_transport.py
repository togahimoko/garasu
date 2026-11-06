"""DNS transport regression checks for the user-facing Garasu profiles."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DnsTransportTests(unittest.TestCase):
    def test_shadowrocket_disables_automatic_http3(self):
        for relative in ("clients/shadowrocket.conf", "release/shadowrocket/config.conf"):
            with self.subTest(path=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                dns_line = next(line.strip() for line in text.splitlines() if line.startswith("dns-server ="))
                self.assertEqual(
                    dns_line,
                    "dns-server = https://dns.google/dns-query#no-h3, "
                    "https://cloudflare-dns.com/dns-query#no-h3",
                )

    def test_mihomo_explicitly_disables_http3(self):
        for relative in ("clients/mihomo-remnawave.yaml", "release/mihomo/config.yaml"):
            with self.subTest(path=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn("dns:\n  enable: true\n  prefer-h3: false\n", text)
                self.assertNotIn("#h3", text)

    def test_published_profiles_match_sources(self):
        for source, deployed in (
            ("clients/shadowrocket.conf", "release/shadowrocket/config.conf"),
            ("clients/mihomo-remnawave.yaml", "release/mihomo/config.yaml"),
        ):
            with self.subTest(source=source):
                self.assertEqual(
                    (ROOT / source).read_bytes(), (ROOT / deployed).read_bytes()
                )


if __name__ == "__main__":
    unittest.main()
