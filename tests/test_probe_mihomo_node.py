"""Read-only diagnostics for named Mihomo nodes; no sensitive names in reports."""
import unittest
from unittest.mock import patch

import probe_mihomo_node as nodeprobe


class NodeProbeTests(unittest.TestCase):
    def setUp(self):
        self.data = {"proxies": {
            "Garasu": {"type": "URLTest", "all": ["AEON CDN WS", "Other"], "now": "Other"},
            "AEON CDN WS": {"type": "Vless"},
            "Other": {"type": "Vless"},
        }}

    def test_chooses_exactly_one_node_without_changing_group(self):
        name, count = nodeprobe.choose_node(self.data, "cdn")
        self.assertEqual((name, count), ("AEON CDN WS", 1))
        summary = nodeprobe.group_summary(self.data, name)
        self.assertEqual(summary["group_type"], "URLTest")
        self.assertTrue(summary["node_in_group"])
        self.assertFalse(summary["node_selected"])

    def test_ambiguous_node_match_is_safe(self):
        self.assertEqual(nodeprobe.choose_node(self.data, ""), (None, 2))
        self.assertEqual(nodeprobe.choose_node(self.data, "missing"), (None, 0))

    @patch.object(nodeprobe, "api_get")
    def test_probe_queries_specific_node_with_only_get(self, get):
        get.side_effect = [self.data, {"delay": 40}, {"delay": 50}]
        report = nodeprobe.diagnose(9097, "", "CDN", 2, 0)
        self.assertEqual(report["status"], "ALL_PASS")
        self.assertEqual(report["successes"], 2)
        self.assertNotIn("AEON CDN WS", str(report))
        self.assertIn("/proxies/AEON%20CDN%20WS/delay?", get.call_args_list[1].args[1])
        self.assertIn("expected=204", get.call_args_list[1].args[1])

    @patch.object(nodeprobe, "api_get")
    def test_one_timeout_reports_failure_without_falsely_claiming_tunnel_down(self, get):
        from urllib.error import HTTPError
        get.side_effect = [self.data, {"delay": 42}, HTTPError("http://localhost/", 504, "timeout", {}, None)]
        report = nodeprobe.diagnose(9097, "", "CDN", 2, 0)
        self.assertEqual(report["status"], "SOME_FAILED")
        self.assertEqual(report["successes"], 1)
        self.assertEqual(report["samples"][1]["http_error"], 504)


if __name__ == "__main__":
    unittest.main()
