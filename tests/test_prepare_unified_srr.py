"""Exact eight-rule Remnawave SRR shape supplied by the operator.

No private subscription URL or personal VLESS node is used in these tests.
"""
import base64
import copy
import json
from pathlib import Path
import unittest

from scripts import prepare_unified_srr

ROOT = Path(__file__).resolve().parents[1]
REV = "2fb95bafa8e674b232187c6cdcd39aefd6131465"


def agent(name, pattern, operator="REGEX"):
    return {
        "name": name, "enabled": True, "operator": "AND",
        "conditions": [{"headerName": "user-agent", "operator": operator,
                        "value": pattern, "caseSensitive": False}],
    }


def eight_rules():
    inc = agent("INCY + Garasu MAX", "incy/", "STARTS_WITH")
    inc.update({"responseType": "XRAY_BASE64", "responseModifications": {
        "headers": [{"key": "autorouting", "value":
                     "incy://autorouting/onadd/https://example.org/old.json"}],
        "applyHeadersToEnd": True,
        "ignoreServeJsonAtBaseSubscription": True,
    }})
    happ = agent("Happ + Garasu MAX", "happ", "STARTS_WITH")
    happ.update({"responseType": "XRAY_BASE64", "responseModifications": {
        "headers": [{"key": "routing", "value": "happ://routing/onadd/OLD"}],
        "applyHeadersToEnd": True,
        "ignoreServeJsonAtBaseSubscription": True,
    }})
    mih = agent("Mihomo Clients",
                "^(?:flclash|rabbit|flowvy|murge|mihomo|prizrak-box|koala-clash|clash(?:-verge|-nyanpasu|x meta|[-.]?meta))")
    mih.update({"responseType": "MIHOMO", "responseModifications":
                {"subscriptionTemplate": "Garasu Mihomo"}})
    stash = agent("Stash (iOS, macOS)", "^stash")
    stash.update({"responseType": "STASH", "responseModifications":
                  {"subscriptionTemplate": "Garasu Stash"}})
    sing = agent("Sing-box clients", "^sfa|sfi|sfm|sft|karing|singbox")
    sing.update({"responseType": "SINGBOX", "responseModifications":
                 {"subscriptionTemplate": "Garasu Singbox"}})
    clash = agent("Clash Core Clients", "^clash")
    clash.update({"responseType": "CLASH"})
    browser = {"name": "Browser Subscription", "enabled": True,
               "responseType": "BROWSER", "operator": "AND",
               "conditions": [{"headerName": "accept", "operator": "CONTAINS",
                               "value": "text/html", "caseSensitive": True}]}
    fallback = {"name": "Fallback Base64", "enabled": True,
                "responseType": "XRAY_BASE64", "operator": "AND",
                "conditions": []}
    return {"version": "1",
            "settings": {"disableSubscriptionAccessByPath": False},
            "rules": [browser, inc, happ, mih, stash, sing, clash, fallback],
            "custom_metadata": {"preserve_this": True}}


class UnifiedSRR(unittest.TestCase):
    def setUp(self):
        self.original = eight_rules()
        self.profile = json.loads(
            (ROOT / "clients/unified/happ.json").read_text(encoding="utf-8"))

    def test_full_preserves_critical_headers_agents_nodes_and_template_names(self):
        before = copy.deepcopy(self.original)
        output = prepare_unified_srr.prepare(self.original, REV, mode="full",
                                              root=ROOT)
        self.assertEqual(self.original, before)
        self.assertEqual(len(output["rules"]), 8)
        self.assertEqual(output["rules"][0], before["rules"][0])
        self.assertEqual(output["rules"][-1], before["rules"][-1])
        self.assertEqual(output["settings"], before["settings"])
        self.assertEqual(output["custom_metadata"], before["custom_metadata"])
        for i in [1, 2, 3, 4, 5, 6]:
            self.assertEqual(output["rules"][i]["conditions"] if i != 5
                             else output["rules"][i]["conditions"][0]["headerName"],
                             before["rules"][i]["conditions"] if i != 5
                             else before["rules"][i]["conditions"][0]["headerName"])
        self.assertEqual(
            [output["rules"][i]["responseModifications"]["subscriptionTemplate"]
             for i in (3, 4, 5)],
            ["Garasu Mihomo", "Garasu Stash", "Garasu Singbox"])
        self.assertEqual(output["rules"][5]["conditions"][0]["value"],
                         "^(?:sfa|sfi|sfm|sft|karing|singbox)")
        inc = output["rules"][1]["responseModifications"]["headers"][0]
        happ = output["rules"][2]["responseModifications"]["headers"][0]
        self.assertEqual(inc["key"], "autorouting")
        self.assertEqual(happ["key"], "routing")
        self.assertEqual(inc["value"], "incy://autorouting/onadd/https://raw.githubusercontent.com/togahimoko/garasu/" +
                         REV + "/clients/unified/incy.json")
        embedded = json.loads(base64.b64decode(happ["value"].split("/onadd/", 1)[1]))
        self.assertEqual(embedded, self.profile)
        self.assertEqual(embedded["DirectSites"], ["geosite:private"])
        self.assertEqual(embedded["DirectIp"], ["geoip:private"])
        self.assertEqual(embedded["BlockSites"], [])
        self.assertEqual(prepare_unified_srr.prepare(output, REV, mode="full", root=ROOT), output)

    def test_preview_uses_only_test_ua_and_preserves_all_existing_live_rules(self):
        output = prepare_unified_srr.prepare(self.original, REV, mode="preview", root=ROOT)
        self.assertEqual(output["rules"][0], self.original["rules"][0])
        self.assertEqual(output["rules"][-7:], self.original["rules"][1:])
        names = [r["name"] for r in output["rules"][1:6]]
        self.assertEqual(names, ["Garasu Unified INCY preview", "Garasu Unified Happ preview",
                                 "Garasu Unified Mihomo preview", "Garasu Unified Stash preview",
                                 "Garasu Unified Singbox preview"])
        for r in output["rules"][1:6]:
            c = r["conditions"]
            self.assertEqual(c[0]["headerName"], "user-agent")
            self.assertEqual(c[0]["operator"], "STARTS_WITH")
            self.assertTrue(c[0]["value"].startswith("garasu-test-"))
        self.assertEqual(prepare_unified_srr.prepare(output, REV, mode="preview", root=ROOT), output)

    def test_preview_stages_new_template_names_without_affecting_live_response(self):
        new = {"mihomo": "Garasu Unified Mihomo",
               "stash": "Garasu Unified Stash",
               "singbox": "Garasu Unified Singbox"}
        prev = prepare_unified_srr.prepare(
            self.original, REV, mode="preview", root=ROOT, template_names=new)
        for idx, expected in ((3, new["mihomo"]), (4, new["stash"]),
                              (5, new["singbox"])):
            self.assertEqual(prev["rules"][idx]["responseModifications"][
                "subscriptionTemplate"], expected)
        # Original active rules are preserved byte-for-byte, including names.
        self.assertEqual(prev["rules"][-7:], self.original["rules"][1:])
        full = prepare_unified_srr.prepare(
            self.original, REV, mode="full", root=ROOT, template_names=new)
        for idx, expected in ((3, new["mihomo"]), (4, new["stash"]),
                              (5, new["singbox"])):
            self.assertEqual(full["rules"][idx]["responseModifications"][
                "subscriptionTemplate"], expected)
        self.assertEqual(full["rules"][-1], self.original["rules"][-1])
        with self.assertRaises(ValueError):
            prepare_unified_srr.prepare(
                self.original, REV, root=ROOT,
                template_names={"mihomo": "only one"})

    def test_fail_closed_for_missing_or_reordered_browser_or_fallback(self):
        for idx, kind in [(0, "CLASH"), (-1, "CLASH")]:
            bad = eight_rules()
            bad["rules"][idx]["responseType"] = kind
            with self.subTest(idx=idx), self.assertRaises(ValueError):
                prepare_unified_srr.prepare(bad, REV, root=ROOT)
        bad = eight_rules()
        bad["rules"][-1]["conditions"] = [{"headerName": "user-agent", "operator": "CONTAINS", "value": "x"}]
        with self.assertRaises(ValueError):
            prepare_unified_srr.prepare(bad, REV, root=ROOT)
        bad = eight_rules()
        bad["rules"][4]["responseModifications"].pop("subscriptionTemplate")
        with self.assertRaises(ValueError):
            prepare_unified_srr.prepare(bad, REV, root=ROOT)

    def test_rejects_nonimmutable_revision_and_unsupported_rule_layout(self):
        for bad_ref in ("main", "feature/x", "deadbeef", "g" * 40):
            with self.subTest(ref=bad_ref), self.assertRaises(ValueError):
                prepare_unified_srr.prepare(self.original, bad_ref, root=ROOT)
        with self.assertRaises(ValueError):
            prepare_unified_srr.prepare({"version": "1", "rules": []}, REV, root=ROOT)


if __name__ == "__main__":
    unittest.main()
