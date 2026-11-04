"""Published legacy client URLs must resolve to the same current native profiles."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ALIASES = {
    "clients/mihomo-remnawave.yaml": "release/mihomo/config.yaml",
    "clients/stash-remnawave.yaml": "release/stash/config.yaml",
    "clients/singbox-remnawave.json": "release/singbox/config.json",
    "clients/singbox-remnawave-1.14.json": "release/singbox/config.json",
    "clients/shadowrocket.conf": "release/shadowrocket/config.conf",
}

class LegacyAliasConsistency(unittest.TestCase):
    def test_legacy_public_aliases_are_exactly_current_profiles(self):
        for alias, canonical in ALIASES.items():
            with self.subTest(alias=alias):
                self.assertEqual((ROOT / alias).read_bytes(), (ROOT / canonical).read_bytes())

if __name__ == "__main__":
    unittest.main()
