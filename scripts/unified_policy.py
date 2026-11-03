#!/usr/bin/env python3
"""Offline Garasu unified routing candidate builder; never touches live panel.

All adapters consume policy/unified-v1.json. The complete RKN snapshots are
pinned to the same DigneZzZ upstream revision as install/manifest.json.
Published main templates and Remnawave SRR are intentionally unchanged.
"""
import argparse
import ipaddress
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "feature/unified-routing-astra-2026-11-03"
BASE = "https://raw.githubusercontent.com/togahimoko/garasu/" + BRANCH
PROXY_TAG = "Garasu"
FULL = {
    "rkn-domains-full": "rules/unified/refilter-domain-full.list",
    "rkn-ips-full": "rules/unified/refilter-ip-full.cidr",
}
FULL_SB = {
    "rkn-domains-full": "rules/unified/refilter-domain-full.singbox.json",
    "rkn-ips-full": "rules/unified/refilter-ip-full.singbox.json",
}


def load_policy(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if (data.get("schema_version") != 1
            or data.get("default_action") != "PROXY"
            or data.get("empty_nodes") != "REJECT"
            or data.get("foreign_direct_exceptions") != []
            or data.get("full_refilter_required_for_ru_bypass") is not True
            or data.get("ru_bypass_enabled") is not False):
        raise ValueError("Unverified or unsafe policy; reject generation")
    kinds = {entry["category"]: entry["kind"] for entry in data["priority"]}
    if set(kinds) != {"rkn-domains-full", "rkn-ips-full", "youtube", "discord",
                      "ai", "crypto", "proxy", "proxy-ips", "ads"}:
        raise ValueError("Unexpected policy categories")
    if any(item["action"] not in ("PROXY", "REJECT")
           for item in data["priority"]):
        raise ValueError("Unexpected implicit DIRECT in policy")
    manifest_path = ROOT / data["snapshot"]["base_manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("upstream_revision") != data["snapshot"]["upstream_revision"]:
        raise ValueError("Full RKN snapshot revision disagrees with current manifest")
    return data


def _domain_matches(host, names):
    return any(host == item or host.endswith("." + item) for item in names)


def decide(policy, hostname, address=None, *, blocked_domains=(),
           blocked_ips=(), ru_ips=(), verified_full_refilter=False):
    """Conservative reference oracle. This does NOT simulate a native client's DNS."""
    host = (hostname or "").lower().rstrip(".")
    literal = None
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        pass
    ip = ipaddress.ip_address(address) if address else literal
    if _domain_matches(host, policy["local_domain_suffixes"]):
        return "DIRECT"
    if literal is not None and literal.is_private:
        return "DIRECT"
    if _domain_matches(host, blocked_domains):
        return "PROXY"
    if ip is not None and any(ip in net for net in blocked_ips):
        return "PROXY"
    if not verified_full_refilter:
        return "PROXY"
    if _domain_matches(host, policy["ru_tlds"]):
        return "DIRECT"
    if literal is not None and any(literal in net for net in ru_ips):
        return "DIRECT"
    return "PROXY"


def _url(category, *, singbox=False, shadowrocket_ip=False):
    if singbox and category in FULL_SB:
        return BASE + "/" + FULL_SB[category]
    if shadowrocket_ip and category == "rkn-ips-full":
        return BASE + "/rules/unified/refilter-ip-full-shadowrocket.list"
    if category in FULL:
        return BASE + "/" + FULL[category]
    suffix = ".cidr" if category == "proxy-ips" and not singbox else ".list"
    if singbox:
        return ("https://raw.githubusercontent.com/togahimoko/garasu/main/rules/singbox/"
                + category + ".json")
    if shadowrocket_ip and category == "proxy-ips":
        suffix = ".list"
    return "https://raw.githubusercontent.com/togahimoko/garasu/main/rules/" + category + suffix


def _all_providers(policy, *, mihomo):
    result = []
    for item in policy["priority"]:
        category = item["category"]
        ip = item["kind"] == "ipcidr"
        result.extend([
            "  " + category + ":",
            "    type: http",
            "    behavior: " + ("ipcidr" if ip else "domain"),
            "    format: text",
            "    url: " + _url(category),
        ])
        if mihomo:
            result.append("    proxy: Garasu Auto")
        result.extend(["    path: ./garasu-unified/" + category + ".txt",
                       "    interval: 21600"])
    return "\n".join(result) + "\n"


def _local_yaml(source):
    local = source.split("rules:\n", 1)[1]
    return local.split("  - RULE-SET,rkn-domains,Garasu", 1)[0]


def _render_yaml(root, policy, filename, *, mihomo):
    source = (root / "clients/canary" / filename).read_text(encoding="utf-8")
    prefix = source.split("rule-providers:\n", 1)[0]
    intro = ("# Garasu Unified v1 CANDIDATE — not activated in Remnawave.\n"
             "# RU bypass is disabled until complete blocked-registry startup is\n"
             "# verified on the native client (no fail-open on cold cache).\n")
    result = intro + prefix + "rule-providers:\n" + _all_providers(policy, mihomo=mihomo)
    result += "rules:\n" + _local_yaml(source)
    for item in policy["priority"]:
        cat = item["category"]
        outbound = "REJECT" if item["action"] == "REJECT" else PROXY_TAG
        suffix = ",no-resolve" if item["kind"] == "ipcidr" else ""
        result += "  - RULE-SET," + cat + "," + outbound + suffix + "\n"
    result += "  - MATCH,Garasu\n"
    return result


def _render_shadowrocket(root, policy):
    original = (root / "clients/canary/shadowrocket.conf").read_text(encoding="utf-8")
    intro = ("# Garasu Unified v1 CANDIDATE; import personal nodes separately.\n"
             "# General RU bypass deliberately disabled for cold-start safety.\n")
    prefix = original.split("[Rule]\n", 1)[0]
    prefix = prefix.replace(
        "https://raw.githubusercontent.com/togahimoko/garasu/main/clients/canary/shadowrocket.conf",
        BASE + "/clients/unified/shadowrocket.conf")
    local = original.split("[Rule]\n", 1)[1].split("# RKN exceptions", 1)[0]
    result = intro + prefix + "[Rule]\n" + local
    for item in policy["priority"]:
        cat = item["category"]
        ip = item["kind"] == "ipcidr"
        kind = "RULE-SET" if ip else "DOMAIN-SET"
        action = item["action"]
        result += kind + "," + _url(cat, shadowrocket_ip=ip) + "," + action + "\n"
    return result + "FINAL,PROXY,dns-failed\n"


def _render_singbox(root, policy):
    base = json.loads((root / "clients/canary/singbox-remnawave-1.14.json").read_text())
    previous = {x["tag"]: x for x in base["route"]["rule_set"]}
    providers = []
    for entry in policy["priority"]:
        category = entry["category"]
        tag = "garasu-" + category
        if tag in previous:
            item = previous[tag].copy()
        else:
            item = {"type": "remote", "tag": tag, "format": "source",
                    "update_interval": "6h", "http_client": "garasu-rules"}
        item["url"] = _url(category, singbox=True)
        providers.append(item)
    base["route"]["rule_set"] = providers
    old = base["route"]["rules"]
    local = old[:4]
    proxy = [x for x in policy["priority"] if x["action"] == "PROXY"]
    ads = [x for x in policy["priority"] if x["action"] == "REJECT"]
    base["route"]["rules"] = local + [
        {"rule_set": ["garasu-" + x["category"] for x in proxy],
         "action": "route", "outbound": "→ Remnawave"},
    ] + ([{"rule_set": ["garasu-" + x["category"] for x in ads],
           "action": "reject", "method": "default"}] if ads else [])
    return json.dumps(base, ensure_ascii=False, indent=2) + "\n"


def _render_xray(root, policy):
    config = json.loads((root / "clients/xray-advanced-remnawave.json").read_text())
    rules = config["routing"]["rules"]
    # Existing geodata is pinned to the same upstream revision, but its
    # banned-ru category is NOT a full-refilter substitute. No RU DIRECT here.
    config["routing"]["rules"] = rules[:5] + [rules[-1]]
    return json.dumps(config, ensure_ascii=False, indent=2) + "\n"


def _render_mobile_xray(root, policy):
    config = json.loads((root / "clients/incy.json").read_text())
    config["Name"] = "Garasu Unified v1 CANDIDATE"
    config["DirectSites"] = ["geosite:private"]
    config["DirectIp"] = ["geoip:private"]
    return json.dumps(config, ensure_ascii=False, indent=2) + "\n"


def build_candidates(root, policy):
    root = Path(root)
    # Candidate-only outputs: NEVER write clients/ production paths.
    result = {
        "clients/unified/mihomo-remnawave.yaml":
            _render_yaml(root, policy, "mihomo-remnawave.yaml", mihomo=True),
        "clients/unified/stash-remnawave.yaml":
            _render_yaml(root, policy, "stash-remnawave.yaml", mihomo=False),
        "clients/unified/shadowrocket.conf": _render_shadowrocket(root, policy),
        "clients/unified/singbox-remnawave-1.14.json": _render_singbox(root, policy),
        "clients/unified/xray-advanced-remnawave.json": _render_xray(root, policy),
        "clients/unified/incy.json": _render_mobile_xray(root, policy),
        "clients/unified/happ.json": _render_mobile_xray(root, policy),
    }
    return result


def candidate_drift(root, policy):
    expected = build_candidates(root, policy)
    return sorted(path for path, contents in expected.items()
                  if not (Path(root) / path).is_file()
                  or (Path(root) / path).read_text(encoding="utf-8") != contents)


def check_candidates(root, policy):
    return not candidate_drift(root, policy)


def main():
    p = argparse.ArgumentParser()
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = p.parse_args()
    policy = load_policy(ROOT / "policy/unified-v1.json")
    if args.check:
        if not check_candidates(ROOT, policy):
            p.error("Generated candidate files missing or differ; run --write in branch")
        print("Unified candidate profiles match one policy snapshot")
    else:
        for path, value in build_candidates(ROOT, policy).items():
            target = ROOT / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(value, encoding="utf-8")
            print("WROTE", path)
        print("No production templates or live subscription settings changed")


if __name__ == "__main__":
    main()
