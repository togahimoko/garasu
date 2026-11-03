#!/usr/bin/env python3
"""Offline Garasu unified routing candidate builder; never touches live panel.

All adapters consume policy/unified-v1.json. The complete RKN snapshots are
pinned to the same DigneZzZ upstream revision as install/manifest.json.
Published main templates and Remnawave SRR are intentionally unchanged.
"""
import argparse
import hashlib
import ipaddress
import json
import re
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PROXY_TAG = "Garasu"
FULL = {
    "rkn-domains-full": "rules/unified/refilter-domain-full.list",
    "rkn-ips-full": "rules/unified/refilter-ip-full.cidr",
}
FULL_SB = {
    "rkn-domains-full": "rules/unified/refilter-domain-full.singbox.json",
    "rkn-ips-full": "rules/unified/refilter-ip-full.singbox.json",
}



SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SAFE_PATH = re.compile(r"^[a-zA-Z0-9_./-]+$")


def validate_release_lock(lock, policy):
    """Reject floating refs, unlisted assets, traversal and mixed snapshots."""
    if not isinstance(lock, dict) or lock.get("schema_version") != 1:
        raise ValueError("Invalid release lock schema")
    if lock.get("repository") != "togahimoko/garasu":
        raise ValueError("Unexpected release repository")
    if lock.get("source_revision") != policy["snapshot"]["upstream_revision"]:
        raise ValueError("Release lock / policy upstream revision mismatch")
    sources = lock.get("sources")
    if not isinstance(sources, dict) or set(sources) != {"base", "blocked"}:
        raise ValueError("Invalid release source set")
    for source in sources.values():
        if not isinstance(source, dict) or not SHA_RE.fullmatch(source.get("revision", "")):
            raise ValueError("Release sources must be immutable 40-char Git revisions")
    categories = lock.get("categories")
    wanted = {item["category"] for item in policy["priority"]}
    if not isinstance(categories, dict) or set(categories) != wanted:
        raise ValueError("Missing or extra release category")
    assets = lock.get("assets")
    if not isinstance(assets, dict):
        raise ValueError("Missing pinned assets")
    needed = set()
    for name, mapping in categories.items():
        expect = "blocked" if name.endswith("-full") else "base"
        if not isinstance(mapping, dict) or set(mapping) != {
                "source", "mihomo", "singbox", "shadowrocket"}:
            raise ValueError("Invalid category format mapping")
        if mapping["source"] != expect:
            raise ValueError("Mixed full-refilter and original release source")
        for engine in ("mihomo", "singbox", "shadowrocket"):
            candidate = mapping[engine]
            if not isinstance(candidate, str) or not candidate.startswith("rules/"):
                raise ValueError("Untrusted asset location")
            needed.add(candidate)
            if engine == "singbox" and not candidate.endswith(".json"):
                raise ValueError("sing-box source must be JSON")
            if engine == "mihomo" and name.endswith("ips") and not candidate.endswith(".cidr"):
                raise ValueError("Mihomo IP rule-set needs CIDR")
    geo = lock.get("geodata")
    if not isinstance(geo, dict) or set(geo) != {"source", "geoip", "geosite"}:
        raise ValueError("Geodata not declared")
    if geo["source"] != "base":
        raise ValueError("Geodata from unrelated release")
    for kind in ("geoip", "geosite"):
        path = geo[kind]
        if path != "geo/" + kind + ".dat":
            raise ValueError("Invalid GeoIP/GeoSite path")
        needed.add(path)
    if set(assets) != needed:
        raise ValueError("Release asset inventory is not exhaustive")
    for path, info in assets.items():
        if (not SAFE_PATH.fullmatch(path) or "\\" in path
                or any(x in ("", ".", "..") for x in PurePosixPath(path).parts)):
            raise ValueError("Path traversal or unusual release asset")
        if not isinstance(info, dict) or set(info) != {"source", "git_blob", "bytes"}:
            raise ValueError("Invalid pinned asset metadata")
        if (info["source"] not in sources or not SHA_RE.fullmatch(
                info.get("git_blob", "")) or not isinstance(info.get("bytes"), int)
                or info["bytes"] < 1):
            raise ValueError("Missing asset content integrity metadata")
    for entry in categories.values():
        for kind in ("mihomo", "singbox", "shadowrocket"):
            if assets[entry[kind]]["source"] != entry["source"]:
                raise ValueError("Asset revision disagrees with category source")
    if any(assets[geo[kind]]["source"] != "base" for kind in ("geoip", "geosite")):
        raise ValueError("Geodata revision disagrees with base release")
    return lock


def load_release_lock(path, policy):
    lock = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_release_lock(lock, policy)


def verify_release_assets(root, lock, *, paths=None):
    """Verify the exact on-disk Git blobs and lengths recorded in the lock.

    Call on a clean checkout before the rolling source-refresh CI job, not
    after it has intentionally regenerated the mutable production rules.
    """
    root = Path(root).resolve()
    assets = lock["assets"]
    selected = sorted(assets) if paths is None else list(paths)
    for relative in selected:
        if relative not in assets:
            raise ValueError("Unknown release asset integrity path: " + relative)
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("Missing or unsafe release asset integrity path: " + relative)
        data = path.read_bytes()
        metadata = assets[relative]
        git_blob = hashlib.sha1(
            b"blob " + str(len(data)).encode("ascii") + b"\x00" + data
        ).hexdigest()
        if len(data) != metadata["bytes"] or git_blob != metadata["git_blob"]:
            raise ValueError("Failed asset integrity check: " + relative)
    return len(selected)


def asset_url(lock, category, engine):
    mapping = lock["categories"][category]
    path = mapping[engine]
    rev = lock["sources"][mapping["source"]]["revision"]
    return "https://raw.githubusercontent.com/" + lock["repository"] + "/" + rev + "/" + path


def geo_url(lock, kind):
    source = lock["geodata"]["source"]
    revision = lock["sources"][source]["revision"]
    return ("https://raw.githubusercontent.com/" + lock["repository"] + "/"
            + revision + "/" + lock["geodata"][kind])

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
    # The existing production manifest advances during scheduled refresh jobs.
    # The unified source-lock is immutable and MUST NOT depend on that moving
    # production file; CI regenerates it from a newer upstream independently.
    pinned = data["snapshot"]["upstream_revision"]
    if not isinstance(pinned, str) or len(pinned) != 40 or any(
            ch not in "0123456789abcdef" for ch in pinned):
        raise ValueError("Invalid pinned source revision")
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


def decide_answers(policy, hostname, addresses, *, blocked_domains=(),
                   blocked_ips=(), ru_ips=(), verified_full_refilter=False):
    """Reference oracle for one DNS answer set; NOT a native routing guarantee.

    A blocked answer overrides an otherwise DIRECT Russian suffix; malformed,
    missing and private answers to a public name are conservative PROXY.
    All A and AAAA answers are checked without geo-CIDR escalation.
    """
    host = (hostname or "").lower().rstrip(".")
    if _domain_matches(host, policy["local_domain_suffixes"]):
        return "DIRECT"
    if _domain_matches(host, blocked_domains):
        return "PROXY"
    if not verified_full_refilter or not isinstance(addresses, (list, tuple)) or not addresses:
        return "PROXY"
    parsed = []
    for address in addresses:
        try:
            value = ipaddress.ip_address(address)
        except (TypeError, ValueError):
            return "PROXY"
        if value.is_private or value.is_link_local or value.is_loopback:
            return "PROXY"
        if any(value in network for network in blocked_ips):
            return "PROXY"
        parsed.append(value)
    if _domain_matches(host, policy["ru_tlds"]):
        return "DIRECT"
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and literal in parsed and any(
            literal in network for network in ru_ips):
        return "DIRECT"
    return "PROXY"


def _url(category, *, singbox=False, shadowrocket_ip=False, lock):
    engine = "singbox" if singbox else "shadowrocket" if shadowrocket_ip else "mihomo"
    return asset_url(lock, category, engine)


def _all_providers(policy, *, mihomo, lock):
    result = []
    for item in policy["priority"]:
        category = item["category"]
        ip = item["kind"] == "ipcidr"
        result.extend([
            "  " + category + ":",
            "    type: http",
            "    behavior: " + ("ipcidr" if ip else "domain"),
            "    format: text",
            "    url: " + _url(category, lock=lock),
        ])
        if mihomo:
            result.append("    proxy: Garasu Auto")
        result.extend(["    path: ./garasu-unified/" + category + ".txt",
                       "    interval: 21600"])
    return "\n".join(result) + "\n"


def _local_yaml(source):
    local = source.split("rules:\n", 1)[1]
    return local.split("  - RULE-SET,rkn-domains,Garasu", 1)[0]


def _render_yaml(root, policy, filename, *, mihomo, lock):
    source = (root / "clients/canary" / filename).read_text(encoding="utf-8")
    prefix = source.split("rule-providers:\n", 1)[0]
    intro = ("# Garasu Unified v1 CANDIDATE — not activated in Remnawave.\n"
             "# RU bypass is disabled until complete blocked-registry startup is\n"
             "# verified on the native client (no fail-open on cold cache).\n")
    result = intro + prefix + "rule-providers:\n" + _all_providers(policy, mihomo=mihomo, lock=lock)
    result += "rules:\n" + _local_yaml(source)
    for item in policy["priority"]:
        cat = item["category"]
        outbound = "REJECT" if item["action"] == "REJECT" else PROXY_TAG
        suffix = ",no-resolve" if item["kind"] == "ipcidr" else ""
        result += "  - RULE-SET," + cat + "," + outbound + suffix + "\n"
    result += "  - MATCH,Garasu\n"
    return result


def _render_shadowrocket(root, policy, lock):
    original = (root / "clients/canary/shadowrocket.conf").read_text(encoding="utf-8")
    intro = ("# Garasu Unified v1 CANDIDATE; import personal nodes separately.\n"
             "# General RU bypass deliberately disabled for cold-start safety.\n")
    prefix = original.split("[Rule]\n", 1)[0]
    prefix = prefix.replace(
        "update-url = https://raw.githubusercontent.com/togahimoko/garasu/main/clients/canary/shadowrocket.conf",
        "# update-url disabled until the profile receives an immutable release URL")
    local = original.split("[Rule]\n", 1)[1].split("# RKN exceptions", 1)[0]
    result = intro + prefix + "[Rule]\n" + local
    for item in policy["priority"]:
        cat = item["category"]
        ip = item["kind"] == "ipcidr"
        kind = "RULE-SET" if ip else "DOMAIN-SET"
        action = item["action"]
        result += kind + "," + asset_url(lock, cat, "shadowrocket") + "," + action + "\n"
    return result + "FINAL,PROXY,dns-failed\n"


def _render_singbox(root, policy, lock):
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
        item["url"] = _url(category, singbox=True, lock=lock)
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
    # Keep the LAN and public-hostname rebinding guards from the source
    # profile, while withholding the broad RU fallback in this candidate.
    # Service PROXY must precede the optional advertisement block rule.
    config["routing"]["rules"] = [
        rule for rule in rules
        if not (rule.get("outboundTag") == "direct" and (
            rule.get("ip") == ["geoip:ru"] or
            any(value.startswith("regexp:(?i)")
                for value in rule.get("domain", []))))
    ]
    return json.dumps(config, ensure_ascii=False, indent=2) + "\n"


def _render_mobile_xray(root, policy, lock):
    config = json.loads((root / "clients/incy.json").read_text())
    config["Name"] = "Garasu Unified v1 CANDIDATE"
    # The production profile contains a moving refresh timestamp. Unified
    # candidates are pinned; never inherit a mutable LastUpdated value.
    config.pop("LastUpdated", None)
    config["DirectSites"] = ["geosite:private"]
    config["DirectIp"] = ["geoip:private"]
    # RouteOrder=block-proxy-direct cannot guarantee service priority.
    # Keep native ad filtering off until the proprietary client is tested.
    config["BlockSites"] = []
    config["BlockIp"] = []
    config["Geoipurl"] = geo_url(lock, "geoip")
    config["Geositeurl"] = geo_url(lock, "geosite")
    return json.dumps(config, ensure_ascii=False, indent=2) + "\n"


def build_candidates(root, policy):
    root = Path(root)
    lock = load_release_lock(root / "policy/unified-release-lock.json", policy)
    # Candidate-only outputs: NEVER write clients/ production paths.
    result = {
        "clients/unified/mihomo-remnawave.yaml":
            _render_yaml(root, policy, "mihomo-remnawave.yaml", mihomo=True, lock=lock),
        "clients/unified/stash-remnawave.yaml":
            _render_yaml(root, policy, "stash-remnawave.yaml", mihomo=False, lock=lock),
        "clients/unified/shadowrocket.conf": _render_shadowrocket(root, policy, lock),
        "clients/unified/singbox-remnawave-1.14.json": _render_singbox(root, policy, lock),
        "clients/unified/xray-advanced-remnawave.json": _render_xray(root, policy),
        "clients/unified/incy.json": _render_mobile_xray(root, policy, lock),
        "clients/unified/happ.json": _render_mobile_xray(root, policy, lock),
    }
    return result


def build_ru_tld_mihomo_candidate(root, policy):
    """Opt-in self-contained RU-TLD DIRECT candidate for offline core review.

    Unlike remote HTTP providers, the complete blocked-domain and blocked-IP
    registries are embedded *inside* this profile. There is no provider cache
    that can silently be absent during cold start. It remains a candidate:
    we do not claim native multi-A/AAAA or real ISP acceptance.
    """
    root = Path(root)
    lock = load_release_lock(root / "policy/unified-release-lock.json", policy)
    from scripts import verify_unified_git_objects
    verify_unified_git_objects.verify_history(root, lock)
    if policy["ru_bypass_enabled"] is not False:
        raise ValueError("Unexpected production-wide RU bypass")
    domains = [line for line in
               (root / "rules/unified/refilter-domain-full.list").read_text(
                   encoding="utf-8").splitlines() if line.startswith("+.")]
    ips = [line for line in
           (root / "rules/unified/refilter-ip-full.cidr").read_text(
               encoding="utf-8").splitlines()
           if line and not line.startswith("#")]
    if len(domains) != policy["snapshot"]["domain_count"] or len(ips) != policy["snapshot"]["ip_count"]:
        raise ValueError("Incomplete full blocked registry; refuse RU DIRECT")
    source = build_candidates(root, policy)["clients/unified/mihomo-remnawave.yaml"]
    for category, behavior, rows in (
            ("rkn-domains-full", "domain", domains),
            ("rkn-ips-full", "ipcidr", ips)):
        regex = re.compile(r"(?m)^  " + re.escape(category) +
                           r":\n(?:^    [^\n]*\n)+")
        matches = list(regex.finditer(source))
        if len(matches) != 1:
            raise ValueError("Cannot bind full inline registry unambiguously")
        payload = "".join("      - '" + row.replace("'", "''") + "'\n"
                          for row in rows)
        replacement = ("  " + category + ":\n"
                       "    type: inline\n"
                       "    behavior: " + behavior + "\n"
                       "    payload:\n" + payload)
        source = (source[:matches[0].start()] + replacement +
                  source[matches[0].end():])
    ip_rule = "  - RULE-SET,rkn-ips-full,Garasu,no-resolve\n"
    if source.count(ip_rule) != 1:
        raise ValueError("Missing blocked-IP routing decision")
    source = source.replace(ip_rule,
                            "  - RULE-SET,rkn-ips-full,Garasu\n")
    final = "  - MATCH,Garasu\n"
    if source.count(final) != 1:
        raise ValueError("Expected fail-closed PROXY final decision")
    direct = "".join("  - DOMAIN-SUFFIX," + tld + ",DIRECT\n"
                     for tld in policy["ru_tlds"])
    return (
        "# Optional VERIFIED-SNAPSHOT RU TLD DIRECT candidate only.\n"
        "# Full blockers are embedded in this YAML; not live Remnawave.\n"
        "# Real DNS / multi-A/AAAA/ISP testing still required.\n"
        + source.replace(final, direct + final)
    )


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
    group.add_argument("--verify-assets", action="store_true")
    args = p.parse_args()
    policy = load_policy(ROOT / "policy/unified-v1.json")
    if args.verify_assets:
        lock = load_release_lock(ROOT / "policy/unified-release-lock.json", policy)
        print("Verified pinned release asset integrity:", verify_release_assets(ROOT, lock))
    elif args.check:
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
