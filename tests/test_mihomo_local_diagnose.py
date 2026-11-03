"""The Mihomo local diagnostic must be accurate and credential-safe."""
import json
import unittest
from scripts import diagnose_mihomo


class MihomoLocalReportTests(unittest.TestCase):
    def test_detects_core_routing_and_proxy_port_faults(self):
        config = {"mixed-port": 0, "mode": "rule", "tun": {"enable": True}}
        groups = {"proxies": {
            "Garasu": {"type":"Selector", "now":"DIRECT", "all":["Garasu Auto","DIRECT"]},
            "Garasu Auto": {"type":"URLTest", "all": [], "now":""},
        }}
        report = diagnose_mihomo.analyze(config, groups)
        self.assertIn("NO_MIXED_PORT", report["issues"])
        self.assertIn("GARASU_DIRECT_SELECTED", report["issues"])
        self.assertIn("AUTO_GROUP_EMPTY", report["issues"])
        self.assertTrue(report["tun_enabled"])

    def test_normal_auto_group_is_not_a_false_positive(self):
        config = {"mixed-port":7897,"mode":"rule","tun":{"enable":False}}
        groups = {"proxies":{
            "Garasu":{"type":"Selector","now":"Garasu Auto","all":["Garasu Auto"]},
            "Garasu Auto":{"type":"URLTest","all":["My private node"],"now":"My private node",
                           "history":[{"time":"2026-11-03T10:00:00Z","delay":35}]},
        }}
        report=diagnose_mihomo.analyze(config,groups)
        self.assertNotIn("GARASU_DIRECT_SELECTED",report["issues"])
        self.assertNotIn("NO_MIXED_PORT",report["issues"])
        self.assertNotIn("AUTO_GROUP_EMPTY",report["issues"])
        self.assertEqual(report["auto_member_count"],1)

    def test_finds_single_open_local_proxy_without_controller_access(self):
        self.assertEqual(
            diagnose_mihomo.choose_port(None, 0, {"7897": True, "7890": False}),
            7897,
        )
        self.assertEqual(
            diagnose_mihomo.choose_port(None, 7890, {"7897": True, "7890": False}),
            7890,
        )
        self.assertIsNone(
            diagnose_mihomo.choose_port(None, 0, {"7897": True, "7890": True}),
        )
        self.assertIsNone(
            diagnose_mihomo.choose_port(None, 0, {"7897": False, "7890": False}),
        )

    def test_report_does_not_expose_proxy_names_or_credentials(self):
        config = {"mixed-port":7897,"mode":"rule","tun":{"enable":True}}
        groups = {"proxies":{
            "Garasu":{"type":"Selector","now":"Garasu Auto",
                      "all":["Garasu Auto","vless://token-user@private.host"]},
            "Garasu Auto":{"type":"URLTest",
                           "all":["vless://token-user@private.host"],"now":"vless://token-user@private.host"}
        }}
        report=diagnose_mihomo.analyze(config,groups)
        txt=json.dumps(report)
        self.assertNotIn("token-user",txt)
        self.assertNotIn("private.host",txt)
        self.assertNotIn("vless://",txt)

if __name__=="__main__":
    unittest.main()
