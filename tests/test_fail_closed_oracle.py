"""Regression tests for complete proxy-pool outage and subsequent recovery.

These tests exercise the safety oracle used by the Docker runtime scenario.
The Docker job separately tests the oracle against a real Mihomo core.
"""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import probe_mihomo_failover as probe


class FailClosedOracleTests(unittest.TestCase):
    def setUp(self):
        self.groups = {
            "Garasu": {"now": "Garasu Auto", "all": ["Garasu Auto"]},
            "Garasu Auto": {
                "now": "garasu-ci-node-1",
                "all": ["garasu-ci-node-1", "garasu-ci-node-2", "garasu-ci-node-3"],
            },
        }

    def test_all_dead_nodes_fail_closed_on_repeated_attempts(self):
        with patch.object(probe, "groups", return_value=self.groups), \
             patch.object(probe, "proxy_http_body",
                          side_effect=[(0, b""), (0, b""), (0, b"")]) as request:
            probe.assert_all_proxies_down(samples=3)
            self.assertEqual(request.call_count, 3)

    def test_success_while_all_nodes_declared_down_is_a_failure(self):
        with patch.object(probe, "groups", return_value=self.groups), \
             patch.object(probe, "proxy_http_body",
                          side_effect=[(0, b""), (200, b"unexpected")]):
            with self.assertRaisesRegex(AssertionError, "unexpected outbound"):
                probe.assert_all_proxies_down(samples=2)

    def test_any_direct_in_proxy_group_is_a_failure(self):
        self.groups["Garasu Auto"]["all"].append("DIRECT")
        with patch.object(probe, "groups", return_value=self.groups), \
             patch.object(probe, "proxy_http_body", return_value=(0, b"")):
            with self.assertRaisesRegex(AssertionError, "DIRECT"):
                probe.assert_all_proxies_down(samples=2)

    def test_group_must_remain_auto_during_full_outage(self):
        self.groups["Garasu"]["now"] = "DIRECT"
        with patch.object(probe, "groups", return_value=self.groups), \
             patch.object(probe, "proxy_http_body", return_value=(0, b"")):
            with self.assertRaisesRegex(AssertionError, "Garasu Auto"):
                probe.assert_all_proxies_down(samples=2)


if __name__ == "__main__":
    unittest.main()
