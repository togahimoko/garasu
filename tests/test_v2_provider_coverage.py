"""Production Garasu V2 must preserve RoscomVPN coverage with one automatic group."""
import json
from pathlib import Path
import unittest
import yaml

ROOT=Path(__file__).resolve().parents[1]
REQUIRED={
    "ads", "rkn-domains", "rkn-ips", "ru-ips", "proxy", "proxy-ips",
    "youtube", "discord", "ai", "crypto",
    "ru-services", "ru-whitelist", "microsoft", "apple", "google-play",
    "epicgames", "origin", "riot", "escapefromtarkov", "steam",
    "twitch", "pinterest", "faceit", "github", "twitch-ads", "telegram",
    "win-spy", "torrent-domains", "category-ads", "ru-geoblock",
    "google-deepmind", "push", "youtube-global", "direct-ips",
    "telegram-ips",
}

class Coverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mihomo=yaml.safe_load((ROOT/'release/mihomo/config.yaml').read_text())
        cls.stash=yaml.safe_load((ROOT/'release/stash/config.yaml').read_text())
        cls.clash=yaml.safe_load((ROOT/'release/clash/config.yaml').read_text())
        cls.singbox=json.loads((ROOT/'release/singbox/config.json').read_text())

    def test_required_coverage_not_just_ten_bundles(self):
        for name,cfg in (("mihomo",self.mihomo),("stash",self.stash),("clash",self.clash)):
            with self.subTest(client=name):
                providers=cfg['rule-providers']
                self.assertGreaterEqual(len(providers),len(REQUIRED))
                self.assertTrue(REQUIRED<=set(providers),sorted(REQUIRED-set(providers)))
                self.assertTrue(all(p['interval']==21600 for p in providers.values()))
                self.assertTrue(all("togahimoko/garasu/main/" in p['url'] for p in providers.values()))
        native={x['tag'].removeprefix('garasu-') for x in self.singbox['route']['rule_set']}
        self.assertTrue(REQUIRED<=native,sorted(REQUIRED-native))
        self.assertTrue(all(x['update_interval']=='6h' for x in self.singbox['route']['rule_set']))

    def test_single_auto_group_and_small_configs(self):
        for name,cfg in (("mihomo",self.mihomo),("stash",self.stash),("clash",self.clash)):
            with self.subTest(name=name):
                self.assertEqual(len(cfg['proxy-groups']),1)
                self.assertEqual(cfg['proxy-groups'][0]['type'],'url-test')
                self.assertEqual(cfg['proxy-groups'][0]['name'],'Garasu')
                self.assertEqual(cfg['rules'][-1],'MATCH,Garasu')
                self.assertLess((ROOT/f'release/{name}/config.yaml').stat().st_size,18000)
        self.assertTrue(all(x['type']=='remote' for x in self.singbox['route']['rule_set']))

    def test_action_precedence_and_ip_leak_prevention(self):
        rules=self.mihomo['rules']
        def pos(prefix):
            return next(i for i,r in enumerate(rules) if r.startswith(prefix))
        self.assertLess(pos('RULE-SET,rkn-domains,Garasu'),pos('RULE-SET,ru-whitelist,DIRECT'))
        self.assertLess(pos('RULE-SET,ru-geoblock,Garasu'),pos('RULE-SET,ru-services,DIRECT'))
        self.assertLess(pos('RULE-SET,telegram,Garasu'),pos('RULE-SET,ru-services,DIRECT'))
        self.assertLess(pos('RULE-SET,telegram-ips,Garasu'),pos('RULE-SET,ru-ips,DIRECT'))
        self.assertLess(pos('RULE-SET,win-spy,REJECT'),pos('RULE-SET,microsoft,DIRECT'))
        for category in ('ru-services','ru-whitelist'):
            contents=(ROOT/f'rules/extra/{category}.list').read_text()
            for domain in ('ipify.org','checkip.amazonaws.com','ifconfig.me','ipapi.is','iplocate.io','ip.sb'):
                with self.subTest(category=category,domain=domain):
                    self.assertNotIn('+.'+domain+'\n',contents)

    def test_local_reproducible_binary_sets(self):
        categories=json.loads((ROOT/'release/mihomo/.mrs/manifest.json').read_text())['files']
        names={x['name'] for x in categories}
        self.assertTrue(REQUIRED<=names)
        for name in REQUIRED:
            self.assertGreater((ROOT/'release/mihomo/.mrs'/f'{name}.mrs').stat().st_size,20)
            self.assertGreater((ROOT/'release/singbox/rules'/f'{name}.srs').stat().st_size,20)
        self.assertTrue((ROOT/'docs/licenses/roscomvpn-geosite-MIT.txt').is_file())

if __name__=='__main__':
    unittest.main()
