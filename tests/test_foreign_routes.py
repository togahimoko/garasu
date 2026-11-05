"""Overseas services must never bypass Garasu to the home IP."""
from pathlib import Path
import json
import unittest
import yaml

ROOT=Path(__file__).resolve().parents[1]
OVERSEAS=("microsoft","apple","google-play","twitch","pinterest",
          "torrent-domains","push")
RU_DIRECT=("ru-services","ru-whitelist","direct-ips")

class ForeignRoutingContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy=json.loads((ROOT/"policy/extra_categories.json").read_text())
        cls.mihomo=yaml.safe_load((ROOT/"release/mihomo/config.yaml").read_text())
        cls.stash=yaml.safe_load((ROOT/"release/stash/config.yaml").read_text())
        cls.clash=yaml.safe_load((ROOT/"release/clash/config.yaml").read_text())
        cls.singbox=json.loads((ROOT/"release/singbox/config.json").read_text())
        cls.shadow=(ROOT/"release/shadowrocket/config.conf").read_text()

    def test_canonical_foreign_actions(self):
        for name in OVERSEAS:
            with self.subTest(name=name):
                self.assertEqual(self.policy["categories"][name]["action"],"Garasu")
        for name in RU_DIRECT:
            with self.subTest(name=name):
                self.assertEqual(self.policy["categories"][name]["action"],"DIRECT")

    def test_mihomo_stash_classic_clash(self):
        for client,cfg in (("mihomo",self.mihomo),("stash",self.stash),("clash",self.clash)):
            rules=cfg["rules"]
            for name in OVERSEAS:
                with self.subTest(client=client,name=name):
                    self.assertIn("RULE-SET,"+name+",Garasu",rules)
                    self.assertNotIn("RULE-SET,"+name+",DIRECT",rules)
            for name in RU_DIRECT:
                self.assertTrue(any(x.startswith("RULE-SET,"+name+",DIRECT") for x in rules))

    def test_singbox_and_shadowrocket_foreign_proxy(self):
        rules=self.singbox["route"]["rules"]
        for name in OVERSEAS:
            with self.subTest(name=name):
                matched=[rule for rule in rules if rule.get("rule_set")==["garasu-"+name]]
                self.assertEqual(len(matched),1)
                self.assertEqual(matched[0].get("outbound"),"→ Remnawave")
                self.assertIn("/"+name+".txt,PROXY",self.shadow)
                self.assertNotIn("/"+name+".txt,DIRECT",self.shadow)

if __name__=="__main__":
    unittest.main()
