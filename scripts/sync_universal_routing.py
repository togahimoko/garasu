#!/usr/bin/env python3
"""Generate one Garasu first-match policy for all native client formats.

Only updates public routing sections; preserves Remnawave insertion markers,
subscriber-aware proxy groups and user-provided endpoints.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import ipaddress
import re

ROOT = Path(__file__).resolve().parents[1]
MIHOMO = "release/mihomo/config.yaml"
STASH = "release/stash/config.yaml"
SHADOW = "release/shadowrocket/config.conf"
SINGBOX = "release/singbox/config.json"
INCY = "release/incy/config.json"
HAPP = "release/happ/config.json"
XRAY = "release/xray/config.json"
TARGETS = (MIHOMO, STASH, SHADOW, SINGBOX, INCY, HAPP, XRAY)
BASE = "https://raw.githubusercontent.com/togahimoko/garasu/main/rules/"


def load_policy(root: Path) -> dict:
    config = json.loads((root / "policy/universal.json").read_text(encoding="utf-8"))
    domains = config["critical_ru_direct_domains"]
    if config["schema_version"] != 1 or config["profiles"] != 1 or config["name"] != "Garasu":
        raise ValueError("Only the single Garasu profile is supported")
    if config["fallback"] != "PROXY" or len(domains) != len(set(domains)):
        raise ValueError("Unexpected fallback or duplicate direct domains")
    if domains != sorted(domains):
        raise ValueError("Canonical domain list must be sorted")
    for domain in domains:
        if domain != domain.lower() or not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", domain):
            raise ValueError("Invalid direct domain: " + domain)
    for cidr in config["private_ipv4"] + config["private_ipv6"]:
        ipaddress.ip_network(cidr)
    for item in config["blocked_domain_sets"] + config["blocked_ip_sets"] + [config["ads_domain_set"]]:
        if not (root / "rules" / (item + (".cidr" if item.endswith("-ips") else ".list"))).is_file():
            raise ValueError("Missing source rule set " + item)
    return config


def native_rules(p: dict, group: str) -> list[str]:
    # Ads are embedded from the GitHub repository at build time. Every other
    # unrecognized site (including blocked/RKN) always takes the VPN route;
    # no remote provider is necessary at cold start.
    rules = ["# GARASU UNIVERSAL: no remote bootstrap dependency."]
    rules += ["DOMAIN-SUFFIX," + d + ",DIRECT" for d in p["private_domains"]]
    rules += ["IP-CIDR," + cidr + ",DIRECT,no-resolve" for cidr in p["private_ipv4"]]
    rules += ["IP-CIDR6," + cidr + ",DIRECT,no-resolve" for cidr in p["private_ipv6"]]
    rules += ["RULE-SET,ads,REJECT"]
    rules += ["DOMAIN-SUFFIX," + d + ",DIRECT" for d in p["critical_ru_direct_domains"]]
    rules += ["MATCH," + group]
    return rules

def render_yaml(src: str, p: dict) -> str:
    marker = "\nrule-providers:\n"
    if marker not in src or "\nrules:\n" not in src:
        raise ValueError("Missing YAML rule-provider/rules section")
    prefix = src.split(marker, 1)[0]
    if prefix.count("proxies: # LEAVE THIS LINE!") < 2:
        raise ValueError("Remnawave insertion markers are missing")
    # A single inline domain provider means a new customer can start even
    # if their ISP blocks GitHub, while the complete source stays in GitHub.
    header = "\nrule-providers:\n  ads:\n    type: inline\n    behavior: domain\n    payload:\n"
    header += "\n".join("      - '+." + d + "'" for d in p["_ads_domains"]) + "\n"
    routes = "\nrules:\n" + "\n".join(
        ("  # " + line.removeprefix("# ") if line.startswith("# ") else "  - " + line)
        for line in native_rules(p, "Garasu")
    ) + "\n"
    return prefix + header + routes

def render_shadow(src: str, p: dict) -> str:
    if "\n[Rule]\n" not in src:
        raise ValueError("Shadowrocket [Rule] section missing")
    prefix = src.split("\n[Rule]\n", 1)[0]
    output = ["# GARASU UNIVERSAL: no remote rule-provider at first run."]
    output += ["DOMAIN-SUFFIX," + d + ",DIRECT" for d in p["private_domains"]]
    output += ["IP-CIDR," + cidr + ",DIRECT,no-resolve" for cidr in p["private_ipv4"]]
    output += ["IP-CIDR6," + cidr + ",DIRECT,no-resolve" for cidr in p["private_ipv6"]]
    output += ["DOMAIN-SUFFIX," + d + ",REJECT" for d in p["_ads_domains"]]
    output += ["DOMAIN-SUFFIX," + d + ",DIRECT" for d in p["critical_ru_direct_domains"]]
    output += ["FINAL,PROXY,dns-failed"]
    return prefix + "\n[Rule]\n" + "\n".join(output) + "\n"

def route_singbox(cfg: dict, p: dict) -> dict:
    routes = [{"action": "sniff"}, {"protocol": "dns", "action": "hijack-dns"}]
    routes += [{"domain_suffix": p["private_domains"], "action": "route", "outbound": "direct"}]
    routes += [{"ip_cidr": p["private_ipv4"] + p["private_ipv6"],
                "action": "route", "outbound": "direct"}]
    routes += [{"rule_set": ["garasu-ads"], "action": "reject", "method": "default"}]
    routes += [{"domain_suffix": p["critical_ru_direct_domains"],
                "action": "route", "outbound": "direct"}]
    cfg["route"]["rules"] = routes
    cfg["route"]["final"] = "→ Remnawave"
    cfg["route"]["rule_set"] = [{"type": "inline", "tag": "garasu-ads",
                                   "rules": [{"domain_suffix": p["_ads_domains"]}]}]
    dns = cfg.get("dns", {})
    dns["rules"] = [
        {"domain_suffix": p["private_domains"], "action": "route", "server": "local"},
        {"domain_suffix": p["critical_ru_direct_domains"], "action": "route", "server": "local"},
    ] + [r for r in dns.get("rules", []) if "query_type" in r]
    # Keep the default DNS/client bootstrap unchanged. Routing no longer
    # depends on a remote binary rule set.
    return cfg

def route_incy(cfg: dict, p: dict) -> dict:
    cfg["Name"] = "Garasu"
    cfg["GlobalProxy"] = "true"
    cfg["RouteOrder"] = "block-proxy-direct"
    cfg["DirectSites"] = ["domain:" + x for x in
                          p["private_domains"] + p["critical_ru_direct_domains"]]
    cfg["DirectIp"] = list(p["private_ipv4"] + p["private_ipv6"])
    cfg["ProxySites"] = []
    cfg["ProxyIp"] = []
    cfg["BlockSites"] = ["domain:" + domain for domain in p["_ads_domains"]]
    cfg["BlockIp"] = []
    # Self-contained rules: no GeoSite/GeoIP download required to import.
    cfg["Geoipurl"] = ""
    cfg["Geositeurl"] = ""
    cfg["DomainStrategy"] = "AsIs"
    return cfg

def route_xray(cfg: dict, p: dict) -> dict:
    cfg["routing"]["rules"] = [
        {"type": "field",
         "domain": ["domain:" + d for d in p["private_domains"]],
         "outboundTag": "direct"},
        {"type": "field", "ip": p["private_ipv4"] + p["private_ipv6"],
         "outboundTag": "direct"},
        {"type": "field", "domain": ["domain:" + d for d in p["_ads_domains"]],
         "outboundTag": "block"},
        {"type": "field",
         "domain": ["domain:" + d for d in p["critical_ru_direct_domains"]],
         "outboundTag": "direct"},
        {"type": "field", "network": "tcp,udp", "outboundTag": "proxy"},
    ]
    cfg["routing"]["domainStrategy"] = "AsIs"
    return cfg

def render_json(text: str, p: dict, kind: str) -> str:
    obj = json.loads(text)
    if kind == SINGBOX:
        obj = route_singbox(obj, p)
    elif kind in (INCY, HAPP):
        obj = route_incy(obj, p)
    else:
        obj = route_xray(obj, p)
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def expected(root: Path) -> dict[str, str]:
    p = load_policy(root)
    values = [line.strip().lower().removeprefix("+.")
              for line in (root / "rules/ads.list").read_text().splitlines()
              if line.strip() and not line.startswith("#")]
    if len(values) != len(set(values)) or len(values) < 500:
        raise ValueError("Canonical ads source missing or duplicated")
    p["_ads_domains"] = sorted(set(values))
    output = {}
    for path in TARGETS:
        old = (root / path).read_text(encoding="utf-8")
        if path in (MIHOMO, STASH):
            output[path] = render_yaml(old, p)
        elif path == SHADOW:
            output[path] = render_shadow(old, p)
        else:
            output[path] = render_json(old, p, path)
    return output


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    flag = cli.add_mutually_exclusive_group(required=True)
    flag.add_argument("--write", action="store_true")
    flag.add_argument("--check", action="store_true")
    cli.add_argument("--root", type=Path, default=ROOT)
    args = cli.parse_args()
    root = args.root.resolve()
    changes = expected(root)
    for path, text in changes.items():
        full = root / path
        if args.write:
            full.write_text(text, encoding="utf-8")
            print("GENERATED", path)
        elif full.read_text(encoding="utf-8") != text:
            raise SystemExit("STALE universal Garasu policy: " + path)
        else:
            print("PASS", path)
    print("UNIVERSAL_GARASU_POLICY=PASS")


if __name__ == "__main__":
    main()
