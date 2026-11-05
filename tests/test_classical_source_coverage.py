"""Keyword/regex GeoSite patterns are retained instead of silently lost."""
import json
from pathlib import Path
import unittest
import yaml

from scripts.sync_universal_routing import provider_sets, load_policy, native_rules

ROOT=Path(__file__).resolve().parents[1]
CLASSICAL={"ru-geoblock-patterns":110,"github-patterns":1}

class ClassicalCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=load_policy(ROOT)
        cls.sources=provider_sets(cls.p)

    def test_classical_sets_include_all_non_suffix_patterns(self):
        provenance=json.loads((ROOT/"rules/extra/provenance.json").read_text())["categories"]
        self.assertEqual(provenance["ru-geoblock"]["skipped"].get("keyword_omitted"),105)
        self.assertEqual(provenance["ru-geoblock"]["skipped"].get("regexp_omitted"),5)
        self.assertEqual(provenance["github"]["skipped"].get("regexp_omitted"),1)
        for name,n in CLASSICAL.items():
            with self.subTest(name=name):
                kind,rows=self.sources[name]
                self.assertEqual(kind,"classical")
                self.assertEqual(len(rows),n)
                self.assertTrue(all(x.startswith(("DOMAIN-KEYWORD,","DOMAIN-REGEX,")) for x in rows))

    def test_all_native_clients_reference_classical_rules(self):
        for client in ("mihomo","stash","clash"):
            cfg=yaml.safe_load((ROOT/f"release/{client}/config.yaml").read_text())
            for name in CLASSICAL:
                with self.subTest(client=client,provider=name):
                    p=cfg["rule-providers"][name]
                    self.assertEqual(p["behavior"],"classical")
                    self.assertEqual(p.get("format","yaml"),"yaml")
                    self.assertEqual(p["interval"],21600)
                    self.assertTrue(p["url"].endswith(f"/{name}.yaml"))
                    self.assertIn(f"RULE-SET,{name},Garasu",cfg["rules"])
        sb=json.loads((ROOT/"release/singbox/config.json").read_text())
        for name,n in CLASSICAL.items():
            entries=json.loads((ROOT/f"release/singbox/rules/{name}.json").read_text())["rules"][0]
            self.assertEqual(len(entries.get("domain_keyword",[]))+len(entries.get("domain_regex",[])),n)
            self.assertIn("garasu-"+name,{p["tag"] for p in sb["route"]["rule_set"]})
        for name in CLASSICAL:
            self.assertIn(f"RULE-SET,https://raw.githubusercontent.com/togahimoko/garasu/main/release/shadowrocket/providers/{name}.list,PROXY",
                          (ROOT/"release/shadowrocket/config.conf").read_text())

    def test_binary_rule_providers_do_not_fake_classical_mrs(self):
        mrs={x["name"] for x in json.loads((ROOT/"release/mihomo/.mrs/manifest.json").read_text())["files"]}
        self.assertTrue(set(CLASSICAL).isdisjoint(mrs))
        for name in CLASSICAL:
            self.assertTrue((ROOT/f"release/singbox/rules/{name}.srs").exists())

if __name__=="__main__":
    unittest.main()
