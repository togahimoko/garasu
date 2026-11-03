"""Parity and safety assertions for opt-in Garasu routing canaries.

These are static policy checks; they do not prove Russian ISP reachability
or real Shadowrocket/Stash app runtime behaviour.
"""
import json
from pathlib import Path
import unittest
import yaml

ROOT=Path(__file__).resolve().parents[1]
C=ROOT/"clients"/"canary"


class CanaryRoutingTests(unittest.TestCase):
    def test_stable_mihomo_uses_full_blocked_before_ru_direct(self):
        rules = yaml.safe_load((ROOT/"clients/mihomo-remnawave.yaml").read_text())["rules"]
        self.assertLess(rules.index("RULE-SET,rkn-domains,Garasu"),
                        rules.index("DOMAIN-SUFFIX,ru,DIRECT"))
        self.assertLess(rules.index("RULE-SET,rkn-ips,Garasu"),
                        rules.index("RULE-SET,ru-ips,DIRECT,no-resolve"))

    def test_mihomo_and_stash_have_same_russian_ip_override(self):
        for name in ("mihomo-remnawave.yaml","stash-remnawave.yaml"):
            with self.subTest(name=name):
                d=yaml.safe_load((C/name).read_text())
                self.assertEqual(d["proxies"],None)
                rules=d["rules"]
                self.assertNotIn("GEOIP,RU,DIRECT",rules)
                self.assertLess(rules.index("RULE-SET,rkn-ips,Garasu"),
                                rules.index("RULE-SET,ru-ips,DIRECT,no-resolve"))
                self.assertLess(rules.index("RULE-SET,rkn-domains,Garasu"),
                                rules.index("DOMAIN-SUFFIX,ru,DIRECT"))
                p=d["rule-providers"]["ru-ips"]
                self.assertEqual(p["behavior"],"ipcidr")
                self.assertTrue(p["url"].endswith("/rules/ru-ips.cidr"))
                self.assertEqual(rules[-1],"MATCH,Garasu")

    def test_shadowrocket_canary_uses_its_own_auto_update_url(self):
        body=(C/"shadowrocket.conf").read_text()
        self.assertIn("update-url = https://raw.githubusercontent.com/togahimoko/garasu/main/clients/canary/shadowrocket.conf",body)
        self.assertNotIn("GEOIP,RU,DIRECT",body)
        self.assertLess(body.index("rkn-ips.list,PROXY"),body.index("ru-ips.list,DIRECT"))
        self.assertLess(body.index("rkn-domains.list,PROXY"),body.index("DOMAIN-SUFFIX,ru,DIRECT"))
        self.assertIn("FINAL,PROXY",body)

    def test_singbox_canary_has_remote_rules_and_no_real_node_credentials(self):
        d=json.loads((C/"singbox-remnawave-1.14.json").read_text())
        rules=d["route"]["rules"]
        rkn=next(i for i,r in enumerate(rules) if "garasu-rkn-domains" in r.get("rule_set",[]))
        rknip=next(i for i,r in enumerate(rules) if "garasu-rkn-ips" in r.get("rule_set",[]))
        direct=next(i for i,r in enumerate(rules) if "garasu-ru-ips" in r.get("rule_set",[]))
        russian=next(i for i,r in enumerate(rules) if "ru" in r.get("domain_suffix",[]))
        self.assertLess(rkn,direct)
        self.assertLess(rknip,direct)
        self.assertLess(rkn,russian)
        self.assertEqual(d["outbounds"][0]["outbounds"],None)
        self.assertEqual(d["route"]["final"],"→ Remnawave")

    def test_policy_examples_from_current_verified_domain_lists(self):
        names=["rkn-domains","youtube","discord","ai","crypto","proxy",
               "ads","games","direct"]
        compiled={}
        for name in names:
            content=(ROOT/"rules"/(name+".list")).read_text()
            compiled[name]={line.strip()[2:] for line in content.splitlines()
                            if line.startswith("+.")}
        def matches(domain,category):
            return any(domain==suffix or domain.endswith("."+suffix)
                       for suffix in compiled[category])
        def effective(domain):
            for cat in names:
                if matches(domain,cat):
                    return "REJECT" if cat=="ads" else "DIRECT" if cat in ("games","direct") else "PROXY"
            if domain.endswith((".ru",".su",".xn--p1ai")):
                return "DIRECT"
            return "PROXY"
        cases={
            "www.youtube.com":"PROXY",
            "chatgpt.com":"PROXY",
            "www.yandex.ru":"DIRECT",
            "www.4pda.ru":"PROXY",
            "unknown.example.org":"PROXY",
        }
        for domain,expected in cases.items():
            with self.subTest(domain=domain):
                self.assertEqual(effective(domain),expected)


if __name__=="__main__":
    unittest.main()
