"""Real-world Remnawave six-rule exports must be safe to stage.

A normal panel often has Browser, MIHOMO, STASH, SINGBOX, CLASH and
XRAY_BASE64 fallback; it does not have individual Happ/INCY SRR entries.
"""
import base64
import copy
import json
import re
import unittest
from scripts import build_srr


def conditions(prefix):
    return [{"headerName": "user-agent", "operator": "STARTS_WITH",
             "value": prefix, "caseSensitive": False}]


def minimal_srr():
    return {
        "version": "1",
        "settings": {"disableSubscriptionAccessByPath": False},
        "rules": [
            {"name": "Browser", "responseType": "BROWSER",
             "conditions": [{"headerName": "accept", "operator": "CONTAINS",
                             "value": "text/html", "caseSensitive": False}]},
            {"name": "Mihomo", "responseType": "MIHOMO", "conditions": conditions("mihomo")},
            {"name": "Stash", "responseType": "STASH", "conditions": conditions("stash")},
            {"name": "Sing-box", "responseType": "SINGBOX", "conditions": conditions("singbox")},
            {"name": "Clash", "responseType": "CLASH", "conditions": conditions("clash")},
            {"name": "Fallback", "responseType": "XRAY_BASE64", "conditions": []},
        ],
    }


def stub_links():
    profile = base64.b64encode(json.dumps({"Name": "Garasu MAX"}).encode()).decode()
    return {
        "incy": "incy://autorouting/onadd/https://example.org/incy.json",
        "happ": "happ://routing/onadd/" + profile,
    }


class SixRuleSRRRecovery(unittest.TestCase):
    def test_full_six_rule_export_adds_mobile_routing_headers_before_fallback(self):
        full = build_srr.patch(minimal_srr(), stub_links(), mode="full",
                               include_mobile=True, include_xray=True)
        self.assertEqual(full["rules"][-1], minimal_srr()["rules"][-1])
        self.assertEqual(len(full["rules"]), 9)
        routes = {r["name"]: r for r in full["rules"]}
        for name, key in (("INCY + Garasu MAX", "autorouting"),
                          ("Happ + Garasu MAX", "routing")):
            rule = routes[name]
            self.assertEqual(rule["responseType"], "XRAY_BASE64")
            self.assertEqual(rule["responseModifications"]["headers"][0]["key"], key)
            self.assertTrue(rule["responseModifications"]["headers"][0]["value"])
        self.assertEqual(build_srr.patch(full, stub_links(), mode="full",
                                         include_mobile=True, include_xray=True), full)

    def test_xray_json_is_opt_in_and_preserves_base64_fallback(self):
        original = minimal_srr()
        full = build_srr.patch(original, stub_links(), mode="full",
                               include_xray=True)
        self.assertEqual(len(full["rules"]), 7)
        self.assertEqual(full["rules"][-1], original["rules"][-1])
        xray = full["rules"][-2]
        self.assertEqual(xray["responseType"], "XRAY_JSON")
        self.assertEqual(xray["conditions"][0]["value"], "garasu-xray-json")
        self.assertEqual(xray["responseModifications"]["subscriptionTemplate"],
                         "Garasu Xray JSON")
        preview = build_srr.patch(original, stub_links(), mode="test",
                                  include_xray=True)
        self.assertEqual(len(preview["rules"]), 12)
        self.assertEqual(preview["rules"][7:], original["rules"][1:])
        self.assertEqual(preview["rules"][6]["responseType"], "XRAY_JSON")
        self.assertEqual(preview["rules"][6]["conditions"][0]["value"],
                         "garasu-test-xray")

    def test_singbox_regex_is_anchored_in_full_and_preview(self):
        original = minimal_srr()
        original["rules"][3]["conditions"] = [{
            "headerName": "user-agent", "operator": "REGEX",
            "value": "^sfa|sfi|sfm|sft|karing|singbox",
            "caseSensitive": False}]
        full = build_srr.patch(original, stub_links(), mode="full")
        regex = full["rules"][3]["conditions"][0]["value"]
        self.assertTrue(re.search(regex, "singbox/1.14", re.I))
        self.assertFalse(re.search(regex, "foo-karing", re.I))
        preview = build_srr.patch(original, stub_links(), mode="test")
        self.assertEqual(preview["rules"][8], original["rules"][3])

    def test_canary_does_not_touch_six_existing_live_rules(self):
        original = minimal_srr()
        saved = copy.deepcopy(original)
        staged = build_srr.patch(original, stub_links(), mode="test")
        self.assertEqual(original, saved)
        self.assertEqual(staged["settings"], original["settings"])
        self.assertEqual(staged["rules"][0], original["rules"][0])
        self.assertEqual(staged["rules"][6:], original["rules"][1:])
        self.assertEqual(len(staged["rules"]), 11)
        self.assertEqual(build_srr.patch(staged, stub_links(), mode="test"), staged)

    def test_canary_incy_happ_preview_isolated_from_unconditional_fallback(self):
        staged = build_srr.patch(minimal_srr(), stub_links(), mode="test")
        rules = {rule["name"]: rule for rule in staged["rules"]}
        self.assertEqual(rules["Garasu INCY preview"]["responseType"], "XRAY_BASE64")
        self.assertEqual(rules["Garasu Happ preview"]["responseType"], "XRAY_BASE64")
        self.assertEqual(rules["Garasu INCY preview"]["responseModifications"]["headers"][0]["key"],
                         "autorouting")
        self.assertEqual(rules["Garasu Happ preview"]["responseModifications"]["headers"][0]["key"],
                         "routing")
        self.assertEqual(staged["rules"][-1], minimal_srr()["rules"][-1])

    def test_full_mode_does_not_add_unrequested_client_rules(self):
        full = build_srr.patch(minimal_srr(), stub_links(), mode="full")
        self.assertEqual(len(full["rules"]), 6)
        self.assertEqual(full["rules"][4], minimal_srr()["rules"][4])
        self.assertEqual(full["rules"][5], minimal_srr()["rules"][5])
        for idx, template in ((1, "Garasu Mihomo"), (2, "Garasu Stash"),
                              (3, "Garasu Singbox")):
            self.assertEqual(full["rules"][idx]["responseModifications"]["subscriptionTemplate"],
                             template)
        self.assertEqual(build_srr.patch(full, stub_links(), mode="full"), full)

    def test_generic_clash_can_use_existing_mihomo_template_without_touching_other_rules(self):
        original = minimal_srr()
        baseline = build_srr.patch(original, stub_links(), mode="full")
        fixed = build_srr.patch(original, stub_links(), mode="full",
                                clash_mihomo_compat=True)
        self.assertEqual(len(fixed["rules"]), len(baseline["rules"]))
        for index in (0, 1, 2, 3, 5):
            self.assertEqual(fixed["rules"][index], baseline["rules"][index])
        clash = fixed["rules"][4]
        self.assertEqual(clash["responseType"], "MIHOMO")
        self.assertEqual(clash["responseModifications"]["subscriptionTemplate"],
                         "Garasu Mihomo")
        self.assertTrue(re.search(clash["conditions"][0]["value"], "clash/1.0", re.I))
        self.assertFalse(re.search(clash["conditions"][0]["value"], "clash-verge/2.0", re.I))
        self.assertEqual(build_srr.patch(fixed, stub_links(), mode="full",
                                         clash_mihomo_compat=True), fixed)
        with self.assertRaises(ValueError):
            build_srr.patch(original, stub_links(), mode="test",
                            clash_mihomo_compat=True)

    def test_rejects_missing_base64_fallback_in_six_rule_export(self):
        broken = minimal_srr()
        broken["rules"][-1]["responseType"] = "BROWSER"
        with self.assertRaises(ValueError):
            build_srr.patch(broken, stub_links(), mode="test")


if __name__ == "__main__":
    unittest.main()
