#!/usr/bin/env python3
"""Build a single RU split-tunnel policy from Garasu-owned, pinned source data.

Remnawave receives small native templates; all large domain/CIDR lists are
published as separate Garasu-owned remote rule providers on GitHub.
Client caches and successful remote downloads are required for the full policy.
Mobile Xray-compatible formats use Garasu's paired GeoSite/GeoIP snapshot.
"""
from __future__ import annotations

import argparse
import base64
import ipaddress
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MIHOMO = "release/mihomo/config.yaml"
STASH = "release/stash/config.yaml"
CLASH = "release/clash/config.yaml"
SHADOW = "release/shadowrocket/config.conf"
SINGBOX = "release/singbox/config.json"
INCY = "release/incy/config.json"
HAPP = "release/happ/config.json"
XRAY = "release/xray/config.json"
TARGETS = (MIHOMO, STASH, CLASH, SHADOW, SINGBOX, INCY, HAPP, XRAY)
GEO_BASE = "https://raw.githubusercontent.com/togahimoko/garasu/main/geo/"
PROVIDERS_BASE = "https://raw.githubusercontent.com/togahimoko/garasu/main/release/providers/"
SINGBOX_BASE = "https://raw.githubusercontent.com/togahimoko/garasu/main/release/singbox/rules/"
CLASH_BASE = "https://raw.githubusercontent.com/togahimoko/garasu/main/release/clash/providers/"


def _domains(root: Path, filename: str) -> list[str]:
    values = [line.strip().lower().removeprefix("+.")
              for line in (root / "rules" / (filename + ".list")).read_text().splitlines()
              if line.strip() and not line.startswith("#")]
    if len(values) != len(set(values)):
        raise ValueError("Duplicate domain in " + filename)
    if any(not re.fullmatch(r"[a-z0-9_*.-]+", s) or s.endswith(".") for s in values):
        raise ValueError("Invalid domain in " + filename)
    return values


def _cidrs(root: Path, filename: str) -> list[str]:
    values = [line.strip() for line in (root / "rules" / (filename + ".cidr")).read_text().splitlines()
              if line.strip() and not line.startswith("#")]
    for item in values:
        ipaddress.ip_network(item, strict=False)
    if len(values) != len(set(values)):
        raise ValueError("Duplicate CIDR in " + filename)
    return values


def _suffix(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def load_policy(root: Path) -> dict:
    p = json.loads((root / "policy/universal.json").read_text(encoding="utf-8"))
    if (p.get("schema_version"), p.get("profiles"), p.get("name"), p.get("fallback")) != (
            1, 1, "Garasu", "PROXY"):
        raise ValueError("Only one fail-closed Garasu policy is supported")
    tlds = p["russian_tlds"]
    direct = p["critical_ru_direct_domains"]
    if not tlds or len(tlds) != len(set(tlds)) or len(direct) != len(set(direct)):
        raise ValueError("Duplicate/empty Russian direct category")
    for name in tlds + direct + p["ad_exempt_domains"]:
        if not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)*", name):
            raise ValueError("Invalid policy domain: " + name)
    for cidr in p["private_ipv4"] + p["private_ipv6"]:
        ipaddress.ip_network(cidr)
    manifest = json.loads((root / "install/manifest.json").read_text(encoding="utf-8"))
    p["_last_updated"] = str(max(1793815000, int(manifest.get("last_updated", "1793815000"))))
    p["_ads_domains"] = [x for x in _domains(root, "ads") if x not in p["ad_exempt_domains"]]
    p["_rkn_domains_all"] = _domains(root, "rkn-domains")
    # Domains outside Russian TLDs or the explicitly DIRECT roots already
    # fall through to VPN. Only exceptions that could bypass matter here.
    p["_rkn_domains"] = [x for x in p["_rkn_domains_all"] if
                         any(_suffix(x, t) for t in tlds) or
                         any(_suffix(x, root_name) for root_name in direct)]
    if len(p["_rkn_domains"]) < 10000:
        raise ValueError("Refusing incomplete Russian blocked-domain exceptions")
    p["_rkn_ips"] = _cidrs(root, "rkn-ips")
    p["_ru_ips"] = _cidrs(root, "ru-ips")
    if len(p["_rkn_ips"]) < 20000 or len(p["_ru_ips"]) < 20000:
        raise ValueError("Refusing incomplete RU/blocked IP source")
    p["_proxy_ips"] = _cidrs(root, "proxy-ips")
    p["_proxy_domains"] = {name: _domains(root, name) for name in
                            ("youtube", "discord", "ai", "crypto", "proxy")}
    if not set(p["ad_exempt_domains"]) <= set(_domains(root, "ads")):
        raise ValueError("Ad exceptions must be actual source entries")
    return p


def _private_rules(p: dict) -> list[str]:
    out = ["DOMAIN-SUFFIX," + d + ",DIRECT" for d in p["private_domains"]]
    out += ["IP-CIDR," + n + ",DIRECT,no-resolve" for n in p["private_ipv4"]]
    out += ["IP-CIDR6," + n + ",DIRECT,no-resolve" for n in p["private_ipv6"]]
    return out


def native_rules(p: dict, group: str) -> list[str]:
    # Top-to-bottom priority: private, ads, explicit VPN, blocked sources,
    # Russian domestic, foreign fallback to VPN. Remote sets must load first.
    result = ["# GARASU SPLIT: remote RKN before RU, foreign -> VPN."]
    result += _private_rules(p)
    result += ["RULE-SET,ads,REJECT"]
    result += ["RULE-SET," + category + "," + group for category in
               ("rkn-domains", "youtube", "discord", "ai", "crypto", "proxy")]
    result += ["RULE-SET,rkn-ips," + group + ",no-resolve",
               "RULE-SET,proxy-ips," + group + ",no-resolve"]
    result += ["DOMAIN-SUFFIX," + d + ",DIRECT" for d in p["critical_ru_direct_domains"]]
    result += ["DOMAIN-SUFFIX," + d + ",DIRECT" for d in p["russian_tlds"]]
    result += ["RULE-SET,ru-ips,DIRECT,no-resolve", "MATCH," + group]
    return result


def provider_sets(p: dict) -> dict[str, tuple[str, list[str]]]:
    groups = {"ads": ("domain", p["_ads_domains"]),
              "rkn-domains": ("domain", p["_rkn_domains"]),
              "rkn-ips": ("ipcidr", p["_rkn_ips"]),
              "proxy-ips": ("ipcidr", p["_proxy_ips"]),
              "ru-ips": ("ipcidr", p["_ru_ips"])}
    for name, domains in p["_proxy_domains"].items():
        groups[name] = ("domain", domains)
    return groups


def provider_artifacts(p: dict) -> dict[str, str]:
    """Exact policy data: same ten sets for Mihomo, Stash and sing-box."""
    out = {}
    for key, (behavior, values) in provider_sets(p).items():
        if behavior == "domain":
            text = "\n".join("+." + v for v in values) + "\n"
        else:
            text = "\n".join(values) + "\n"
        out[f"release/providers/{key}.txt"] = text
        # Classic Clash/Premium understands remote YAML payloads, not MRS.
        # JSON double-quoted strings are valid YAML scalars and never auto-cast.
        clash_entries = ["payload:"]
        clash_entries.extend("  - " + json.dumps(
            ("." + v) if behavior == "domain" else v
        ) for v in values)
        out[f"release/clash/providers/{key}.yaml"] = "\n".join(clash_entries) + "\n"
        source = {
            "version": 3,
            "rules": [{"domain_suffix" if behavior == "domain" else "ip_cidr": values}]
        }
        out[f"release/singbox/rules/{key}.json"] = (
            json.dumps(source, ensure_ascii=False, separators=(",", ":")) + "\n")
    return out


def render_yaml(src: str, p: dict, *, stash: bool = False) -> str:
    marker = "\nrule-providers:\n"
    if marker not in src or "\nrules:\n" not in src:
        raise ValueError("Invalid Remnawave YAML template")
    prefix = src.split(marker, 1)[0].rstrip("\n")
    if prefix.count("proxies: # LEAVE THIS LINE!") < 2:
        raise ValueError("Missing Remnawave node injection markers")
    prefix = prefix.replace(
        "Native inline domain/ipcidr rule sets; no GitHub bootstrap at cold start.",
        "Remote Garasu rule sets; cache and first-download required.")
    prefix = prefix.replace(
        "No Moscow proxy chain. RKN/RU lists are embedded in the subscription; regenerate to update.",
        "No Moscow chain. Rules downloaded from canonical Garasu GitHub providers.")
    parts = [prefix, "", "rule-providers:"]
    for key, (behavior, _) in provider_sets(p).items():
        parts.extend([
            f"  {key}:",
            "    behavior: " + behavior,
            "    format: mrs",
            "    url: https://raw.githubusercontent.com/togahimoko/garasu/main/release/mihomo/.mrs/" + key + ".mrs",
            "    interval: 21600",
            "    path: ./rule-providers/garasu-" + key + ".mrs",
        ])
        if not stash:
            parts.extend([
                "    type: http",
                "    proxy: Garasu",
            ])
    parts.extend(["", "rules:"])
    for rule in native_rules(p, "Garasu"):
        parts.append("  " + rule if rule.startswith("#") else "  - " + rule)
    return "\n".join(parts) + "\n"



def render_clash(src: str, p: dict) -> str:
    marker = "\nrule-providers:\n"
    if marker not in src or "\nrules:\n" not in src:
        raise ValueError("Classic Clash template sections missing")
    prefix = src.split(marker, 1)[0].rstrip("\n")
    if prefix.count("proxies: # LEAVE THIS LINE!") != 2:
        raise ValueError("Classic Clash node insertion anchors missing")
    # No Mihomo-only fields: format=mrs, include-all, remnawave, hidden, etc.
    output = [prefix, "", "rule-providers:"]
    for key, (behavior, _) in provider_sets(p).items():
        output.extend((
            "  " + key + ":",
            "    type: http",
            "    behavior: " + behavior,
            "    url: " + CLASH_BASE + key + ".yaml",
            "    path: ./rule-providers/garasu-" + key + ".yaml",
            "    interval: 21600",
        ))
    output.extend(("", "rules:"))
    for rule in native_rules(p, "Garasu"):
        output.append("  " + rule if rule.startswith("#") else "  - " + rule)
    return "\n".join(output) + "\n"


def render_shadow(src: str, p: dict) -> str:
    marker = "\n[Rule]\n"
    if marker not in src:
        raise ValueError("Missing Shadowrocket native section")
    prefix = src.split(marker, 1)[0]
    prefix = prefix.replace("Shadowrocket managed routing profile.",
                            "Shadowrocket remote Garasu routing profile.")
    out = ["# GARASU SPLIT: remote provider lists; cache required."]
    out += _private_rules(p)
    for key in provider_sets(p):
        if key == "ads":
            out.append("DOMAIN-SET," + PROVIDERS_BASE + key + ".txt,REJECT")
        elif key in ("rkn-ips", "proxy-ips", "ru-ips"):
            action = "DIRECT" if key == "ru-ips" else "PROXY"
            out.append("RULE-SET,https://raw.githubusercontent.com/togahimoko/garasu/main/rules/" +
                       key + ".list," + action)
        elif key != "ru-ips":
            out.append("DOMAIN-SET," + PROVIDERS_BASE + key + ".txt,PROXY")
    out += ["DOMAIN-SUFFIX," + x + ",DIRECT" for x in
            p["critical_ru_direct_domains"] + p["russian_tlds"]]
    # Place RU IP DIRECT after all blocked IP providers and domain exceptions.
    ru = "RULE-SET,https://raw.githubusercontent.com/togahimoko/garasu/main/rules/ru-ips.list,DIRECT"
    out.remove(ru)
    out.append(ru)
    out.append("FINAL,PROXY,dns-failed")
    return prefix + marker + "\n".join(out) + "\n"


def route_singbox(cfg: dict, p: dict) -> dict:
    cfg["route"]["rule_set"] = [
        {
            "type": "remote",
            "tag": "garasu-" + key,
            "format": "binary",
            "url": SINGBOX_BASE + key + ".srs",
            "update_interval": "6h",
            "http_client": "garasu-rules",
        }
        for key in provider_sets(p)
    ]
    # The existing http_clients tag is required for sing-box >= 1.14.
    clients = [item for item in cfg.get("http_clients", [])
               if item.get("tag") == "garasu-rules"]
    if len(clients) != 1:
        raise ValueError("Missing dedicated sing-box HTTP downloader")
    clients[0]["detour"] = "→ Remnawave"
    cfg["route"]["default_http_client"] = "garasu-rules"
    routes = [{"action": "sniff"}, {"protocol": "dns", "action": "hijack-dns"},
              {"domain_suffix": p["private_domains"], "outbound": "direct"},
              {"ip_cidr": p["private_ipv4"] + p["private_ipv6"], "outbound": "direct"},
              {"rule_set": ["garasu-ads"], "action": "reject"}]
    routes.extend({"rule_set": ["garasu-" + key], "outbound": "→ Remnawave"}
                  for key in ("rkn-domains", "youtube", "discord", "ai", "crypto", "proxy",
                              "rkn-ips", "proxy-ips"))
    routes.extend([{"domain_suffix": p["critical_ru_direct_domains"], "outbound": "direct"},
                   {"domain_suffix": p["russian_tlds"], "outbound": "direct"},
                   {"rule_set": ["garasu-ru-ips"], "outbound": "direct"}])
    cfg["route"]["rules"] = routes
    cfg["route"]["final"] = "→ Remnawave"
    dns = cfg.get("dns", {})
    dns.pop("independent_cache", None)  # Deprecated as of sing-box 1.14.
    dns["rules"] = [
        {"domain_suffix": p["private_domains"], "action": "route", "server": "local"},
        {"domain_suffix": p["critical_ru_direct_domains"] + p["russian_tlds"],
         "action": "route", "server": "local"},
    ] + [r for r in dns.get("rules", []) if "query_type" in r]
    return cfg


def route_incy(cfg: dict, p: dict) -> dict:
    cfg["Name"] = "Garasu"
    # Happ applies updated routing only when LastUpdated increases.
    cfg["LastUpdated"] = p["_last_updated"]
    cfg["GlobalProxy"] = "true"
    cfg["RouteOrder"] = "block-proxy-direct"
    cfg["DomainStrategy"] = "IPIfNonMatch"
    cfg["DirectSites"] = ["geosite:private", "geosite:category-ru",
                          "geosite:garasu-ru"] + ["domain:" + x for x in
                                                p["critical_ru_direct_domains"]]
    cfg["DirectIp"] = ["geoip:private", "geoip:ru"]
    cfg["ProxySites"] = ["geosite:banned-ru", "geosite:youtube",
                         "geosite:discord", "geosite:ai", "geosite:crypto",
                         "geosite:telegram", "geosite:github"]
    cfg["ProxyIp"] = ["geoip:blocked-ru"]
    cfg["BlockSites"] = ["geosite:garasu-ads"]
    cfg["BlockIp"] = []
    cfg["Geoipurl"] = GEO_BASE + "geoip.dat"
    cfg["Geositeurl"] = GEO_BASE + "geosite.dat"
    return cfg


def route_xray(cfg: dict, p: dict) -> dict:
    cfg["routing"]["domainStrategy"] = "AsIs"
    cfg["routing"]["rules"] = [
        {"type": "field", "domain": ["domain:" + x for x in p["private_domains"]],
         "outboundTag": "direct"},
        {"type": "field", "ip": p["private_ipv4"] + p["private_ipv6"],
         "outboundTag": "direct"},
        {"type": "field", "domain": ["geosite:garasu-ads"],
         "outboundTag": "block"},
        {"type": "field", "domain": ["geosite:banned-ru", "geosite:youtube",
                                      "geosite:discord", "geosite:ai", "geosite:crypto"],
         "outboundTag": "proxy"},
        {"type": "field", "ip": ["geoip:blocked-ru"], "outboundTag": "proxy"},
        {"type": "field",
         "domain": ["geosite:category-ru", "geosite:garasu-ru"] +
                   ["domain:" + x for x in p["critical_ru_direct_domains"]],
         "outboundTag": "direct"},
        {"type": "field", "ip": ["geoip:ru"], "outboundTag": "direct"},
        {"type": "field", "network": "tcp,udp", "outboundTag": "proxy"},
    ]
    return cfg


def offline_mihomo_fixture(config: dict, root: Path) -> dict:
    """Offline tests use VERIFIED local source sets; production stays HTTP-based."""
    import copy
    cfg = copy.deepcopy(config)
    for key, item in cfg["rule-providers"].items():
        expected = "https://raw.githubusercontent.com/togahimoko/garasu/main/release/mihomo/.mrs/" + key + ".mrs"
        if item.get("type") != "http" or item.get("url") != expected or item.get("format") != "mrs":
            raise ValueError("Unrecognized remote Garasu provider: " + key)
        text = (root / "release/providers" / (key + ".txt")).read_text()
        payload = [line for line in text.splitlines() if line and not line.startswith("#")]
        if not payload:
            raise ValueError("Empty remote rule provider: " + key)
        cfg["rule-providers"][key] = {
            "type": "inline", "behavior": item["behavior"], "payload": payload
        }
    return cfg


def expected(root: Path) -> dict[str, str]:
    p = load_policy(root)
    out = provider_artifacts(p)
    for name in TARGETS:
        old = (root / name).read_text(encoding="utf-8")
        if name in (MIHOMO, STASH):
            out[name] = render_yaml(old, p, stash=(name == STASH))
        elif name == CLASH:
            out[name] = render_clash(old, p)
        elif name == SHADOW:
            out[name] = render_shadow(old, p)
        else:
            obj = json.loads(old)
            if name == SINGBOX:
                obj = route_singbox(obj, p)
            elif name in (INCY, HAPP):
                obj = route_incy(obj, p)
            else:
                obj = route_xray(obj, p)
            out[name] = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    return out


def expected_srr(root: Path, happ_json: str) -> str:
    """Keep Happ routing header and delivered profile exactly equivalent."""
    path = root / "release/remnawave/srr.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    matches = [r for r in data["rules"] if r.get("name") == "Happ Garasu"]
    if len(matches) != 1:
        raise ValueError("Expected exactly one Happ routing response")
    headers = matches[0]["responseModifications"]["headers"]
    if len(headers) != 1 or headers[0]["key"].lower() != "routing":
        raise ValueError("Invalid Happ subscription header")
    payload = json.dumps(json.loads(happ_json), separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
    headers[0]["value"] = "happ://routing/onadd/" + base64.b64encode(payload).decode("ascii")
    if len(headers[0]["value"].encode("ascii")) > 3500:
        raise ValueError("Happ routing header exceeds safe 3.5KB proxy budget")
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    modes = cli.add_mutually_exclusive_group(required=True)
    modes.add_argument("--write", action="store_true")
    modes.add_argument("--check", action="store_true")
    cli.add_argument("--root", type=Path, default=ROOT)
    args = cli.parse_args()
    root = args.root.resolve()
    rendered = expected(root)
    for name, data in rendered.items():
        target = root / name
        if args.write:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(data, encoding="utf-8")
            print("GENERATED", name, len(data))
        elif target.read_text(encoding="utf-8") != data:
            raise SystemExit("STALE Roscom-style Garasu profile: " + name)
        else:
            print("PASS", name)
    header_path = root / "release/remnawave/srr.json"
    srr = expected_srr(root, rendered[HAPP])
    if args.write:
        header_path.write_text(srr, encoding="utf-8")
        print("GENERATED", "release/remnawave/srr.json")
    elif header_path.read_text(encoding="utf-8") != srr:
        raise SystemExit("STALE Happ SRR routing header")
    else:
        print("PASS", "release/remnawave/srr.json")
    print("GARASU_RU_SPLIT_POLICY=PASS")


if __name__ == "__main__":
    main()
