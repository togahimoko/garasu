"""Cross-engine IPv4 route-order regression tests for Garasu CZ-only canary.

Static policy oracle; no claims about live DNS resolution or real exit IP.
"""
import ipaddress
import json
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CANARY = ROOT / "clients" / "canary"
CATEGORIES = ("rkn-ips", "proxy-ips", "direct-ips", "ru-ips")
CZR = "PROXY"
DIR = "DIRECT"
BASE = "https://raw.githubusercontent.com/togahimoko/garasu/main/rules/"


def networks(name):
    raw = (ROOT / "rules" / (name + ".cidr")).read_text()
    return tuple(ipaddress.ip_network(s.strip()) for s in raw.splitlines()
                 if s.strip() and not s.startswith("#"))


class CanaryIpMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = {name: networks(name) for name in CATEGORIES}
        cls.mihomo = yaml.safe_load((CANARY / "mihomo-remnawave.yaml").read_text())
        cls.stash = yaml.safe_load((CANARY / "stash-remnawave.yaml").read_text())
        cls.shadow = (CANARY / "shadowrocket.conf").read_text().split("[Rule]", 1)[1]
        cls.singbox = json.loads((CANARY / "singbox-remnawave-1.14.json").read_text())
        cls.singbox_data = {}
        for name in CATEGORIES:
            raw = json.loads((ROOT / "rules" / "singbox" / (name + ".json")).read_text())
            cls.singbox_data[name] = tuple(
                ipaddress.ip_network(ip) for rule in raw["rules"]
                for ip in rule.get("ip_cidr", [])
            )
        for name in CATEGORIES:
            if set(cls.data[name]) != set(cls.singbox_data[name]):
                raise AssertionError("IP adapter mismatch: " + name)

    @staticmethod
    def belongs(ip, networks):
        return any(ip in net for net in networks if ip.version == net.version)

    @classmethod
    def mihomo_route(cls, profile, ip):
        for s in profile["rules"]:
            items = s.split(",")
            if items[0] in ("IP-CIDR", "IP-CIDR6"):
                net = ipaddress.ip_network(items[1])
                if ip.version == net.version and ip in net:
                    return CZR if items[2] == "Garasu" else items[2]
            elif items[0] == "RULE-SET" and items[1] in cls.data:
                if cls.belongs(ip, cls.data[items[1]]):
                    return CZR if items[2] == "Garasu" else items[2]
            elif items[0] == "GEOIP" and items[1] == "LAN" and ip.is_private:
                return DIR
            elif items[0] == "MATCH":
                return CZR if items[1] == "Garasu" else items[1]
        raise AssertionError("No final Mihomo rule")

    @classmethod
    def shadow_route(cls, ip):
        for s in cls.shadow.splitlines():
            if not s or s.lstrip().startswith("#"):
                continue
            items = [part.strip() for part in s.split(",")]
            if items[0] in ("IP-CIDR", "IP-CIDR6"):
                net = ipaddress.ip_network(items[1])
                if ip.version == net.version and ip in net:
                    return items[2]
            elif items[0] == "RULE-SET":
                ref = items[1]
                name = ref.removeprefix(BASE).removesuffix(".list")
                if name in cls.data and cls.belongs(ip, cls.data[name]):
                    return items[2]
            elif items[0] == "GEOIP" and items[1] == "LAN" and ip.is_private:
                return DIR
            elif items[0] == "FINAL":
                return items[1]
        raise AssertionError("No final Shadowrocket rule")

    @classmethod
    def singbox_route(cls, ip):
        for r in cls.singbox["route"]["rules"]:
            if r.get("ip_is_private") and ip.is_private:
                return DIR if r["outbound"] == "direct" else CZR
            for ref in r.get("rule_set", []):
                name = ref.removeprefix("garasu-")
                if name in cls.singbox_data and cls.belongs(ip, cls.singbox_data[name]):
                    return DIR if r.get("outbound") == "direct" else CZR
        return CZR if cls.singbox["route"]["final"] == "→ Remnawave" else DIR

    def test_selected_ip_policy_is_identical_in_four_clients(self):
        examples = [
            ("loopback", ipaddress.ip_address("127.0.0.1"), DIR),
            ("home", ipaddress.ip_address("192.168.1.1"), DIR),
            ("cgnat", ipaddress.ip_address("100.64.1.1"), DIR),
            ("link_local", ipaddress.ip_address("169.254.2.3"), DIR),
            ("foreign", ipaddress.ip_address("1.1.1.1"), CZR),
        ]
        for name in ("rkn-ips", "proxy-ips"):
            net = next(n for n in self.data[name] if n.version == 4)
            examples.append((name, net.network_address, CZR))
        ru = next(n for n in self.data["ru-ips"] if n.version == 4 and
                  not self.belongs(n.network_address, self.data["rkn-ips"]) and
                  not self.belongs(n.network_address, self.data["proxy-ips"]))
        examples.append(("ordinary_ru", ru.network_address, DIR))

        for label, ip, expected in examples:
            routes = {
                "Mihomo": self.mihomo_route(self.mihomo, ip),
                "Stash": self.mihomo_route(self.stash, ip),
                "Shadowrocket": self.shadow_route(ip),
                "sing-box": self.singbox_route(ip),
            }
            for client, actual in routes.items():
                with self.subTest(label=label, ip=str(ip), client=client):
                    self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
