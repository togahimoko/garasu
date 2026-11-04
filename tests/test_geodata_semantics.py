"""Binary V2Ray .dat semantic integrity, not merely file hashes."""
import json
from pathlib import Path
import unittest

from scripts.audit_geodata import audit, categories, fields, varint

ROOT = Path(__file__).resolve().parents[1]


class BinaryGeoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = audit(ROOT)

    def test_full_blocked_datasets_match_inputs(self):
        self.assertGreater(self.record["banned_ru_exact_match"], 70000)
        self.assertGreater(self.record["blocked_ru_ip_exact_match"], 20000)
        source = (ROOT / "rules/ru-ips.cidr").read_text().splitlines()
        valid = [row for row in source if row.strip() and not row.startswith("#")]
        self.assertEqual(self.record["ru_ip_exact_match"], len(valid))

    def test_reports_summarize_actual_binary_membership(self):
        stored = json.loads(
            (ROOT / "reports/geodata-integrity.json").read_text(encoding="utf-8"))
        self.assertEqual(stored, self.record)
        self.assertGreaterEqual(self.record["ads_only_in_text"], 0)
        self.assertGreaterEqual(self.record["ads_only_in_binary"], 0)

    def test_malformed_wire_data_fails_closed(self):
        for blob in (b"\x0a\xff", b"\x00", b"\xff" * 11):
            with self.subTest(blob=blob):
                with self.assertRaises(ValueError):
                    categories(blob)


if __name__ == "__main__":
    unittest.main()
