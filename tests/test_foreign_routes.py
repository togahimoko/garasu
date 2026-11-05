"""Russian split-tunnel routing matrix checked against reference policy."""
from pathlib import Path
import json
import unittest
import yaml
from scripts.sync_universal_routing import load_policy, provider_sets, _suffix

ROOT=Path(__file__).resolve().parents[1]
DIRECT=("microsoft","apple","twitch","pinterest","push","torrent-domains",
        "steam","epicgames","origin","riot","escapefromtarkov","faceit",
        "ru-services","ru-whitelist","direct-ips")
PROXY=("google-play","github","telegram","telegram-ips","twitch-ads",
       "ru-geoblock","ru-geoblock-patterns","google-deepmind")
REJECT=("category-ads","win-spy")
ESSENTIAL_DIRECT=("apple.com","microsoft.com","icloud.com","outlook.com")
BLOCKED_SAMPLES=("4pda.ru","copilot.microsoft.com","ads.twitch.tv")

class RussianRoutingMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy=json.loads((ROOT/"policy/extra_categories.json").read_text())
        cls.universal=json.loads((ROOT/"policy/universal.json").read_text())
        cls.mihomo=yaml.safe_load((ROOT/"release/mihomo/config.yaml").read_text())
        cls.stash=yaml.safe_load((ROOT/"release/stash/config.yaml").read_text())
        cls.clash=yaml.safe_load((ROOT/"release/clash/config.yaml").read_text())
        cls.singbox=json.loads((ROOT/"release/singbox/config.json").read_text())
        cls.shadow=(ROOT/"release/shadowrocket/config.conf").read_text()
        cls.source=provider_sets(load_policy(ROOT))

    def test_reference_category_matrix(self):
        for action,keys in (("DIRECT",DIRECT),("Garasu",PROXY),("REJECT",REJECT)):
            for key in keys:
                with self.subTest(key=key):
                    self.assertEqual(self.policy["categories"][key]["action"],action)

    def test_all_three_yaml_clients_and_no_manual_selector(self):
        for client,cfg in (("mihomo",self.mihomo),("stash",self.stash),("clash",self.clash)):
            self.assertEqual(len(cfg["proxy-groups"]),1,client)
            self.assertEqual(cfg["proxy-groups"][0]["type"],"url-test")
            rules=cfg["rules"]
            for action,keys in (("DIRECT",DIRECT),("Garasu",PROXY),("REJECT",REJECT)):
                for key in keys:
                    with self.subTest(client=client,key=key):
                        prefix=f"RULE-SET,{key},{action}"
                        self.assertTrue(any(rule.startswith(prefix) for rule in rules),
                                        f"{client}:{prefix}")
            self.assertEqual(rules[-1],"MATCH,Garasu")
            self.assertLess(rules.index("RULE-SET,twitch-ads,Garasu"),
                            rules.index("RULE-SET,twitch,DIRECT"))
            self.assertLess(rules.index("RULE-SET,push,DIRECT"),
                            rules.index("RULE-SET,google-play,Garasu"))
            self.assertLess(rules.index("RULE-SET,ru-geoblock,Garasu"),
                            rules.index("RULE-SET,ru-services,DIRECT"))
            self.assertLess(rules.index("RULE-SET,rkn-domains,Garasu"),
                            rules.index("DOMAIN-SUFFIX,ru,DIRECT"))
            for domain in ESSENTIAL_DIRECT:
                self.assertIn("DOMAIN-SUFFIX,"+domain+",DIRECT",rules)

    def test_singbox_action_matrix_and_precedence(self):
        rules=self.singbox["route"]["rules"]
        for action,keys in (("direct",DIRECT),("→ Remnawave",PROXY)):
            for name in keys:
                matches=[(i,x) for i,x in enumerate(rules)
                         if x.get("rule_set")==["garasu-"+name]]
                self.assertEqual(len(matches),1,name)
                self.assertEqual(matches[0][1].get("outbound"),action,name)
        for name in REJECT:
            self.assertEqual(next(x.get("action") for x in rules
                                  if x.get("rule_set")==["garasu-"+name]),"reject")
        def position(name):
            return next(i for i,x in enumerate(rules)
                        if x.get("rule_set")==["garasu-"+name])
        self.assertLess(position("twitch-ads"),position("twitch"))
        self.assertLess(position("push"),position("google-play"))
        self.assertLess(position("ru-geoblock"),position("ru-services"))
        self.assertTrue(any("apple.com" in r.get("domain_suffix",[]) and
                            r.get("outbound")=="direct" for r in rules))

    def test_shadowrocket_routes_are_equivalent(self):
        for action,keys in (("DIRECT",DIRECT),("PROXY",PROXY),("REJECT",REJECT)):
            for name in keys:
                suffix=(".list" if self.source[name][0] != "domain" else ".txt")
                self.assertIn("/"+name+suffix+","+action,self.shadow,name)
        self.assertLess(self.shadow.index("/twitch-ads.txt,PROXY"),
                        self.shadow.index("/twitch.txt,DIRECT"))
        self.assertLess(self.shadow.index("/push.txt,DIRECT"),
                        self.shadow.index("/google-play.txt,PROXY"))

    def test_selected_real_domains_follow_reference(self):
        rules=self.mihomo["rules"]
        def decide(host):
            for rule in rules:
                parts=rule.split(",")
                if parts[0]=="RULE-SET" and self.source[parts[1]][0]=="domain":
                    if any(_suffix(host,v) for v in self.source[parts[1]][1]):
                        return parts[2]
                if parts[0]=="DOMAIN-SUFFIX" and _suffix(host,parts[1]):
                    return parts[2]
                if parts[0]=="MATCH":
                    return parts[1]
            raise AssertionError("No route")
        expected={
            "apple.com":"DIRECT", "microsoft.com":"DIRECT",
            "icloud.com":"DIRECT", "outlook.com":"DIRECT",
            "mail.yandex.ru":"DIRECT","gosuslugi.ru":"DIRECT",
            "store.steampowered.com":"DIRECT","twitch.tv":"DIRECT",
            "ads.twitch.tv":"Garasu",
            "alt1-mtalk.google.com":"DIRECT",
            "android.clients.google.com":"DIRECT",
            "www.youtube.com":"Garasu","api.github.com":"Garasu",
            "4pda.ru":"Garasu","copilot.microsoft.com":"Garasu",
        }
        for domain,action in expected.items():
            with self.subTest(domain=domain):
                self.assertEqual(decide(domain),action)

if __name__=="__main__":
    unittest.main()
