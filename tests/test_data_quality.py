import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts import refresh
from scripts import audit_rules


def fixture():
    data = {
        "rules/rkn-domains.list": b"# header\n+.blocked.example.com\n",
        "rules/ai.list": b"+.copilot.microsoft.com\n",
        "rules/proxy.list": b"+.github.com\n",
        "rules/direct.list": b"+.example.com\n+.microsoft.com\n",
        "rules/ads.list": b"+.ads.example.net\n",
        "rules/rkn-ips.cidr": b"# header\n203.0.113.10/32\n",
        "rules/ru-ips.cidr": b"203.0.113.0/24\n",
    }
    # Include all canonical category names; production snapshots must be complete.
    for name in audit_rules.DOMAINS:
        data.setdefault("rules/" + name + ".list", b"")
    for name in audit_rules.IPS:
        data.setdefault("rules/" + name + ".cidr", b"")
    meta = {path: {"sha256": hashlib.sha256(content).hexdigest(),
                   "bytes": len(content)} for path, content in data.items()}
    return data, meta


class GarasuDataQualityTests(unittest.TestCase):
    def test_category_inventory_remains_in_sync_with_builder(self):
        self.assertEqual(set(audit_rules.DOMAINS), set(refresh.DOMAIN))
        self.assertEqual(set(audit_rules.IPS), set(refresh.IP))

    def test_detects_parent_direct_override_by_specific_proxy(self):
        data, meta = fixture()
        report = audit_rules.analyze(data, meta)
        overlaps = report["policy_overrides"]
        self.assertIn(
            {"higher_priority": "rkn-domains", "lower_priority": "direct",
             "examples": [{"proxied": "blocked.example.com", "direct_suffix": "example.com"}],
             "count": 1},
            overlaps,
        )
        self.assertIn(
            {"higher_priority": "ai", "lower_priority": "direct",
             "examples": [{"proxied": "copilot.microsoft.com", "direct_suffix": "microsoft.com"}],
             "count": 1},
            overlaps,
        )

    def test_records_ru_ip_conflicts_without_altering_routing(self):
        data, meta = fixture()
        report = audit_rules.analyze(data, meta)
        self.assertEqual(report["ip_overrides"]["rkn-ips -> ru-ips"]["count"], 1)
        self.assertEqual(report["domain_counts"]["direct"], 2)

    def test_report_deterministic_and_uses_verified_hashes(self):
        data, meta = fixture()
        first = audit_rules.analyze(data, meta)
        second = audit_rules.analyze(data, meta)
        self.assertEqual(audit_rules.to_json(first), audit_rules.to_json(second))
        self.assertEqual(audit_rules.to_markdown(first), audit_rules.to_markdown(second))
        self.assertIn("Garasu", audit_rules.to_markdown(first))
        self.assertTrue(first["snapshot_sha256"])
        tampered = dict(data)
        tampered["rules/direct.list"] = b"+.unexpected.example\n"
        with self.assertRaises(ValueError):
            audit_rules.analyze(tampered, meta)

    def test_missing_canonical_source_rejected(self):
        data, meta = fixture()
        data.pop("rules/direct.list")
        with self.assertRaises(ValueError):
            audit_rules.analyze(data, meta)

    def test_upstream_revision_urls_are_immutable(self):
        revision = "a" * 40
        raw = json.dumps({"sha": revision}).encode()
        self.assertEqual(refresh.parse_upstream_revision(raw), revision)
        self.assertEqual(refresh.parse_upstream_revision(json.dumps(
            {"ref": "refs/heads/main", "object": {"sha": revision, "type": "commit"}}
        ).encode()), revision)
        self.assertEqual(
            refresh.upstream_raw_url(revision, "release/youtube.list"),
            "https://raw.githubusercontent.com/DigneZzZ/routing/" + revision
            + "/release/youtube.list",
        )
        for invalid in (
            b'{"sha":"main"}', b'{"sha":"not-a-commit"}',
            b'{"sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/"}',
            b'{"message":"rate limit"}',
        ):
            with self.subTest(raw=invalid):
                with self.assertRaises((ValueError, KeyError)):
                    refresh.parse_upstream_revision(invalid)

    def test_no_customer_credentials_or_machine_specific_paths(self):
        data, meta = fixture()
        body = audit_rules.to_json(audit_rules.analyze(data, meta))
        self.assertNotIn("/Users/", body)
        self.assertNotIn("subscription-user", body)
        self.assertNotIn("VLESS", body)


if __name__ == "__main__":
    unittest.main()
