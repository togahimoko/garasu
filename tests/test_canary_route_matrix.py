"""Offline cross-format policy oracle for one Czech node.

Uses committed rule sets and exact order from canary profile files.
This catches policy drift and adapter inconsistencies, not client runtime
support, DNS/IP resolution, Remnawave delivery, or physical egress.
"""
import json
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CANARY = ROOT / "clients" / "canary"
ROOT_URL = "https://raw.githubusercontent.com/togahimoko/garasu/main/rules/"
PROXY = "PROXY"
DIRECT = "DIRECT"
REJECT = "REJECT"

GOLDEN = {
    # Hostname -> intended policy. One Remnawave node, not multiple exits.
    "printer.local": DIRECT,
    "printer.home.arpa": DIRECT,
    "www.yandex.ru": DIRECT,
    "ordinary-example.ru": DIRECT,
    "www.youtube.com": PROXY,
    "chatgpt.com": PROXY,
    "github.com": PROXY,
    "www.4pda.ru": PROXY,
    "blaper.artstation.com": PROXY,  # specific RKN entry overrides games
    "ads.twitch.tv": PROXY,          # explicit proxy overrides general ads
    "steampowered.com": DIRECT,      # known CURRENT exception; review later
    "unknown.example.org": PROXY,
}


def suffix_matches(host, values):
    return any(host == d or host.endswith("." + d) for d in values)


def text_domains(name):
    content = (ROOT / "rules" / (name + ".list")).read_text(encoding="utf-8")
    return {line.strip()[2:] for line in content.splitlines()
            if line.startswith("+.")}


def singbox_domains(name):
    doc = json.loads((ROOT / "rules" / "singbox" / (name + ".json"))
                     .read_text(encoding="utf-8"))
    suffixes = set()
    exact = set()
    for entry in doc["rules"]:
        suffixes.update(entry.get("domain_suffix", []))
        exact.update(entry.get("domain", []))
    return suffixes, exact


class CanaryRouteMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suffix = {
            n: text_domains(n) for n in (
                "rkn-domains", "youtube", "discord", "ai", "crypto",
                "proxy", "ads", "games", "direct")
        }
        cls.sb_domains = {n: singbox_domains(n) for n in cls.suffix}
        cls.mihomo = yaml.safe_load(
            (CANARY / "mihomo-remnawave.yaml").read_text(encoding="utf-8"))
        cls.stash = yaml.safe_load(
            (CANARY / "stash-remnawave.yaml").read_text(encoding="utf-8"))
        cls.singbox = json.loads(
            (CANARY / "singbox-remnawave-1.14.json").read_text(encoding="utf-8"))
        shadow_text = (CANARY / "shadowrocket.conf").read_text(encoding="utf-8")
        cls.shadow_rules = shadow_text.split("[Rule]", 1)[1].strip().splitlines()

    @classmethod
    def mihomo_route(cls, rules, host):
        for rule in rules:
            parts = rule.split(",")
            kind = parts[0]
            if kind == "DOMAIN-SUFFIX" and suffix_matches(host, [parts[1]]):
                return parts[2]
            if kind == "RULE-SET":
                category = parts[1]
                if category in cls.suffix and suffix_matches(host, cls.suffix[category]):
                    return PROXY if parts[2] == "Garasu" else parts[2]
            if kind == "MATCH":
                return PROXY if parts[1] == "Garasu" else parts[1]
        raise AssertionError("No Mihomo fallback: " + host)

    @classmethod
    def shadow_route(cls, host):
        for raw in cls.shadow_rules:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = [x.strip() for x in line.split(",")]
            kind = parts[0]
            if kind == "DOMAIN-SUFFIX" and suffix_matches(host, [parts[1]]):
                return parts[2]
            if kind == "DOMAIN-SET":
                self_name = parts[1].rsplit("/", 1)[-1].removesuffix(".list")
                if self_name in cls.suffix and suffix_matches(host, cls.suffix[self_name]):
                    return parts[2]
            if kind == "FINAL":
                return parts[1]
        raise AssertionError("No Shadowrocket fallback: " + host)

    @classmethod
    def singbox_route(cls, host):
        for rule in cls.singbox["route"]["rules"]:
            if rule.get("domain_suffix") and suffix_matches(host, rule["domain_suffix"]):
                return DIRECT if rule.get("outbound") == "direct" else PROXY
            if rule.get("rule_set"):
                match = False
                for ref in rule["rule_set"]:
                    category = ref.removeprefix("garasu-")
                    if category not in cls.sb_domains:
                        continue
                    suffix, exact = cls.sb_domains[category]
                    if host in exact or suffix_matches(host, suffix):
                        match = True
                        break
                if match:
                    return (REJECT if rule.get("action") == "reject" else
                            DIRECT if rule.get("outbound") == "direct" else PROXY)
        return PROXY if cls.singbox["route"]["final"] == "→ Remnawave" else DIRECT

    def test_every_domain_has_same_policy_in_all_canary_formats(self):
        for host, expected in GOLDEN.items():
            decisions = {
                "Mihomo": self.mihomo_route(self.mihomo["rules"], host),
                "Stash": self.mihomo_route(self.stash["rules"], host),
                "Shadowrocket": self.shadow_route(host),
                "sing-box 1.14": self.singbox_route(host),
            }
            for client, decision in decisions.items():
                with self.subTest(host=host, client=client):
                    self.assertEqual(decision, expected)

    def test_singbox_adapter_contains_every_canonical_domain_suffix(self):
        for name, source in self.suffix.items():
            with self.subTest(category=name):
                generated, exact = self.sb_domains[name]
                self.assertTrue(source.issubset(generated | exact),
                                "sing-box conversion dropped source domains")


if __name__ == "__main__":
    unittest.main()
