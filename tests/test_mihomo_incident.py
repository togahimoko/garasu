"""Live outage triage must identify broken macOS system-proxy wiring.

Only aggregate diagnostics are printed: no node names, subscription URLs,
credentials, or raw connection destinations.
"""
import json
import unittest
from scripts import diagnose_mihomo as d


class MihomoIncidentDiagnosticsTests(unittest.TestCase):
    def test_macos_system_proxy_port_and_disabled_state(self):
        state = d.parse_macos_system_proxy(
            "HTTPEnable : 1\nHTTPProxy : 127.0.0.1\nHTTPPort : 17897\n"
            "HTTPSEnable : 1\nHTTPSProxy : 127.0.0.1\nHTTPSPort : 17897\n"
            "SOCKSEnable : 0\n")
        self.assertEqual(state["enabled_ports"], [17897])
        self.assertEqual(state["enabled_hosts"], ["127.0.0.1"])
        self.assertEqual(d.parse_macos_system_proxy(
            "HTTPEnable : 0\nHTTPPort : 7897\n")["enabled_ports"], [])

    def test_broken_system_proxy_target_detected_even_with_other_open_listener(self):
        system = {"enabled_ports": [17897], "enabled_hosts": ["127.0.0.1"]}
        sockets = {"7897": True, "7890": False, "17897": False}
        issues = d.system_proxy_issues(system, sockets, mixed_port=7897)
        self.assertIn("SYSTEM_PROXY_TARGET_NOT_LISTENING", issues)
        self.assertIn("SYSTEM_PROXY_PORT_MISMATCH", issues)

    def test_system_proxy_port_correct_and_listening(self):
        system = {"enabled_ports": [7897], "enabled_hosts": ["127.0.0.1"]}
        sockets = {"7897": True, "7890": False, "17897": False}
        self.assertEqual(d.system_proxy_issues(system, sockets, mixed_port=7897), [])

    def test_health_history_is_aggregated_without_exposing_proxy_names(self):
        proxies = {"proxies": {
            "Garasu Auto": {"all": [
                "vless://private-user:secret@node.one",
                "private-internal-node-2",
                "private-internal-node-3",
            ], "now": "vless://private-user:secret@node.one"},
            "vless://private-user:secret@node.one": {
                "history": [{"delay": 51}]},
            "private-internal-node-2": {"history": [{"delay": 0}]},
            "private-internal-node-3": {"history": []},
        }}
        summary = d.proxy_health_summary(proxies)
        self.assertEqual(summary, {"node_count": 3, "last_delay_positive": 1,
                                   "last_delay_zero": 1, "untested": 1})
        output = json.dumps(summary)
        for secret in ("private-user", "secret", "node.one", "private-internal"):
            self.assertNotIn(secret, output)

    def test_no_live_nodes_is_a_distinct_fault(self):
        proxies = {"proxies": {"Garasu Auto": {"all": []}}}
        self.assertEqual(d.proxy_health_summary(proxies)["node_count"], 0)


if __name__ == "__main__":
    unittest.main()
