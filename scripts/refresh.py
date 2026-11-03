#!/usr/bin/env python3
"""Garasu routing data publisher. Standard library only; no VPN credentials."""
import base64
from email.utils import parsedate_to_datetime
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
if not __package__:
    sys.path.insert(0, str(ROOT))
from scripts.routing_policy import validate_source_metadata
UPSTREAM = "https://raw.githubusercontent.com/DigneZzZ/routing/main"
REPO = os.environ.get("GITHUB_REPOSITORY", "togahimoko/garasu")
DOMAIN = {
    "ads": ("release/reject.list", 500),
    "ai": ("release/ai.list", 80),
    "crypto": ("release/crypto.list", 40),
    "direct": ("release/direct.list", 1000),
    "discord": ("release/discord.list", 15),
    "games": ("release/games.list", 60),
    "proxy": ("release/proxy.list", 80),
    "rkn-domains": ("release/refilter-domain-full.list", 70000),
    "youtube": ("release/youtube.list", 60),
}
IP = {
    "rkn-ips": ("release/refilter-ip-full.list", 20000),
    "proxy-ips": ("release/proxy-ip.list", 4),
    "direct-ips": ("release/direct-ip.list", 15),
    "ru-ips": ("release/ru-ip.list", 15000),
}
GEO = {
    "geoip.dat": ("v2ray/geoip.dat", 200000),
    "geosite.dat": ("v2ray/geosite.dat", 200000),
}

def parse_upstream_revision(blob):
    """GitHub API commit SHA; never trust a moving tag for a multi-file release."""
    response = json.loads(blob.decode("utf-8"))
    if "object" in response:
        if response.get("ref") != "refs/heads/main" or response["object"].get("type") != "commit":
            raise ValueError("GitHub revision lookup did not return a branch commit")
        revision = response["object"]["sha"]
    else:
        revision = response["sha"]
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Invalid immutable upstream commit SHA")
    return revision


def parse_git_revision(blob):
    """Parse exactly the main ref returned by git ls-remote."""
    lines = blob.decode("ascii").splitlines()
    if len(lines) != 1:
        raise ValueError("Unexpected upstream Git ref response")
    match = re.fullmatch(r"([0-9a-f]{40})\trefs/heads/main", lines[0])
    if not match:
        raise ValueError("Invalid upstream Git ref response")
    return match.group(1)


def upstream_raw_url(revision, path):
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Invalid upstream revision")
    if not path or not re.fullmatch(r"[A-Za-z0-9._/-]+", path) or ".." in path.split("/"):
        raise ValueError("Invalid source path")
    return "https://raw.githubusercontent.com/DigneZzZ/routing/" + revision + "/" + path


def resolve_upstream_revision():
    result = subprocess.run(
        ["git", "ls-remote", "https://github.com/DigneZzZ/routing.git",
         "refs/heads/main"], capture_output=True, check=True, timeout=30,
    )
    if len(result.stdout) > 1024:
        raise ValueError("Unexpectedly large upstream Git ref response")
    return parse_git_revision(result.stdout)


def parse_upstream_commit_date(blob, revision):
    """Extract a stable Unix timestamp from a patch for the pinned commit."""
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Invalid upstream revision")
    header = blob.decode("utf-8").split("\n\n", 1)[0].splitlines()
    if not header or header[0] != "From " + revision + " Mon Sep 17 00:00:00 2001":
        raise ValueError("Commit patch does not match upstream revision")
    dates = [line[6:] for line in header if line.startswith("Date: ")]
    if len(dates) != 1:
        raise ValueError("Commit patch has no unique date")
    parsed = parsedate_to_datetime(dates[0])
    if parsed.tzinfo is None:
        raise ValueError("Commit patch date has no timezone")
    return str(int(parsed.timestamp()))


def upstream_commit_date(revision):
    """Read immutable commit metadata without using GitHub's API endpoint."""
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Invalid upstream revision")
    url = "https://github.com/DigneZzZ/routing/commit/" + revision + ".patch"
    request = urllib.request.Request(url, headers={"User-Agent": "Garasu-Routing/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status != 200 or response.url != url:
            raise ValueError("Upstream commit patch lookup failed")
        header = response.read(8192)
    return parse_upstream_commit_date(header, revision)


def fetch(path, revision):
    url = upstream_raw_url(revision, path)
    error = None
    for retry in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Garasu-Routing/1.0"})
            with urllib.request.urlopen(req, timeout=45) as response:
                if response.status != 200:
                    raise ValueError("unexpected HTTP status")
                data = response.read(90000001)
            if not data or len(data) > 90000000:
                raise ValueError("empty or oversized source")
            return data
        except (OSError, ValueError) as exc:
            error = exc
            if retry < 2:
                time.sleep(2 ** retry)
    raise RuntimeError("Failed source " + path + ": " + str(error))

def _safe_domain_set_entry(value):
    """Accept only canonical multi-label domain suffixes from our upstream feed.

    Broad TLD or wildcard entries can unintentionally route an entire country
    or internet zone to an attacker-controlled destination.
    """
    if not value.startswith("+.") or len(value) > 255:
        return False
    host = value[2:]
    labels = host.split(".")
    if len(labels) < 2 or len(host) > 253:
        return False
    return all(len(label) <= 63 and
               re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", label)
               for label in labels)


def domains(blob, minimum):
    lines = blob.decode("utf-8-sig").splitlines()
    found = []
    seen = set()
    for row in lines:
        value = row.strip()
        if not value or value.startswith("#"):
            continue
        if not _safe_domain_set_entry(value):
            raise ValueError("Unsafe domain entry " + repr(value[:100]))
        if value not in seen:
            found.append(value)
            seen.add(value)
    if len(found) < minimum:
        raise ValueError("Domain source shrank " + str(len(found)))
    return ("# Garasu MAX | Source DigneZzZ/routing; see SOURCES.md\n"
            + "\n".join(found) + "\n").encode(), len(found)


def ip_data(blob, minimum, name=""):
    raw = []
    seen = set()
    for row in blob.decode("utf-8-sig").splitlines():
        value = row.strip()
        if not value or value.startswith("#"):
            continue
        net = ipaddress.ip_network(value, strict=False)
        if name in ("rkn-ips", "proxy-ips"):
            limit = 12 if net.version == 4 else 32
            if net.prefixlen < limit:
                raise ValueError("Unsafe broad " + name + " network " + str(net))
        value = str(net)
        if value not in seen:
            raw.append(value)
            seen.add(value)
    if len(raw) < minimum:
        raise ValueError("IP source shrank " + str(len(raw)))
    prefix = "# Garasu MAX | Source DigneZzZ/routing; see SOURCES.md\n"
    sr = prefix + "\n".join(("IP-CIDR6" if ":" in x else "IP-CIDR") + "," + x for x in raw) + "\n"
    mihomo = prefix + "\n".join(raw) + "\n"
    return sr.encode(), mihomo.encode(), len(raw)


def singbox_domains(blob):
    """Convert canonical +.domain provider lines to sing-box source rule sets."""
    items = [line.strip() for line in blob.decode("utf-8").splitlines()
             if line.strip() and not line.startswith("#")]
    suffixes = []
    exact = []
    for item in items:
        if item.startswith("+.") or item.startswith("*."):
            suffixes.append(item[2:])
        elif item.startswith("."):
            suffixes.append(item[1:])
        else:
            exact.append(item)
    rule = {}
    if suffixes:
        rule["domain_suffix"] = suffixes
    if exact:
        rule["domain"] = exact
    return (json.dumps({"version": 3, "rules": [rule]},
                       ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def singbox_ips(blob):
    """Convert canonical CIDR files to sing-box source rule sets."""
    entries = [line.strip() for line in blob.decode("utf-8").splitlines()
               if line.strip() and not line.startswith("#")]
    for net in entries:
        ipaddress.ip_network(net)
    return (json.dumps({"version": 3, "rules": [{"ip_cidr": entries}]},
                       ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def surge_domains(blob):
    """Create Surge/Loon rule-set syntax (policy supplied by referencing profile)."""
    rules = []
    for line in blob.decode("utf-8").splitlines():
        item = line.strip()
        if not item or item.startswith("#"):
            continue
        if item.startswith(("+.", "*.")):
            rules.append("DOMAIN-SUFFIX," + item[2:])
        elif item.startswith("."):
            rules.append("DOMAIN-SUFFIX," + item[1:])
        else:
            rules.append("DOMAIN," + item)
    return ("# Garasu MAX | Surge and Loon shared rule set\n" + "\n".join(rules) + "\n").encode()


def surge_ips(blob):
    """Create Surge/Loon IP rules from canonical CIDR lists."""
    rules = []
    for line in blob.decode("utf-8").splitlines():
        item = line.strip()
        if item and not item.startswith("#"):
            ipaddress.ip_network(item)
            rules.append(("IP-CIDR6," if ":" in item else "IP-CIDR,") + item)
    return ("# Garasu MAX | Surge and Loon shared IP rule set\n" + "\n".join(rules) + "\n").encode()


def quantumultx_domains(blob, policy):
    """Quantumult X remote filter entries with explicit fallback policy."""
    rules = []
    for line in blob.decode("utf-8").splitlines():
        item = line.strip()
        if not item or item.startswith("#"):
            continue
        if item.startswith(("+.", "*.")):
            rules.append("host-suffix, " + item[2:] + ", " + policy)
        elif item.startswith("."):
            rules.append("host-suffix, " + item[1:] + ", " + policy)
        else:
            rules.append("host, " + item + ", " + policy)
    return ("# Garasu MAX | Quantumult X filters\n" + "\n".join(rules) + "\n").encode()


def quantumultx_ips(blob, policy):
    rules = []
    for line in blob.decode("utf-8").splitlines():
        item = line.strip()
        if item and not item.startswith("#"):
            ipaddress.ip_network(item)
            rules.append(("ip6-cidr, " if ":" in item else "ip-cidr, ") + item + ", " + policy)
    return ("# Garasu MAX | Quantumult X IP filters\n" + "\n".join(rules) + "\n").encode()


def policy_for(name):
    return "reject" if name == "ads" else ("direct" if name in ("games", "direct", "direct-ips", "ru-ips") else "proxy")


def _protobuf_varint(data, index):
    result = 0
    for shift in range(0, 70, 7):
        if index >= len(data):
            raise ValueError("Truncated GeoIP/GeoSite protobuf")
        octet = data[index]
        index += 1
        result |= (octet & 127) << shift
        if not (octet & 128):
            return result, index
    raise ValueError("Invalid protobuf varint")


def _protobuf_fields(data):
    """Read protobuf wire fields without depending on non-standard packages."""
    pos = 0
    while pos < len(data):
        tag, pos = _protobuf_varint(data, pos)
        number, wire = tag >> 3, tag & 7
        if not number:
            raise ValueError("Invalid protobuf field 0")
        if wire == 0:
            _, pos = _protobuf_varint(data, pos)
        elif wire == 1:
            pos += 8
        elif wire == 2:
            length, pos = _protobuf_varint(data, pos)
            if length > len(data) - pos:
                raise ValueError("Truncated protobuf payload")
            yield number, data[pos:pos + length]
            pos += length
        elif wire == 5:
            pos += 4
        else:
            raise ValueError("Invalid protobuf wire type " + str(wire))
        if pos > len(data):
            raise ValueError("Truncated protobuf scalar")


def _protobuf_number(value):
    result = bytearray()
    while value >= 128:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def _protobuf_bytes(number, payload):
    return _protobuf_number(number << 3 | 2) + _protobuf_number(len(payload)) + payload


def replace_geodata_category(name, geodata, category, canonical):
    """Replace a binary category with the exact validated canonical rule set."""
    wanted = category.upper().encode("ascii")
    if name == "geosite.dat":
        values = [line[2:] for line in canonical.decode("utf-8").splitlines()
                  if line and not line.startswith("#")]
        if not values or any(not _safe_domain_set_entry("+." + value) for value in values):
            raise ValueError("Invalid canonical GeoSite source")
        # v2ray Domain.Type=2 means suffix, which includes the root domain.
        items = [b"\x08\x02" + _protobuf_bytes(2, value.encode("ascii"))
                 for value in values]
    elif name == "geoip.dat":
        values = [line for line in canonical.decode("utf-8").splitlines()
                  if line and not line.startswith("#")]
        networks = [ipaddress.ip_network(value, strict=True) for value in values]
        if not networks:
            raise ValueError("Empty canonical GeoIP source")
        items = [_protobuf_bytes(1, network.network_address.packed)
                 + _protobuf_number(2 << 3) + _protobuf_number(network.prefixlen)
                 for network in networks]
    else:
        raise ValueError("Unknown geodata file " + name)
    replacement = _protobuf_bytes(1, wanted) + b"".join(_protobuf_bytes(2, item) for item in items)
    output = bytearray()
    replaced = False
    for number, entry in _protobuf_fields(geodata):
        if number != 1:
            raise ValueError("Unexpected top-level geodata field")
        code = next((value for field, value in _protobuf_fields(entry) if field == 1), None)
        if code == wanted:
            if replaced:
                raise ValueError("Duplicate geodata category " + category)
            entry = replacement
            replaced = True
        output.extend(_protobuf_bytes(1, entry))
    if not replaced:
        raise ValueError("Missing geodata category " + category)
    return bytes(output)


GEODATA_REQUIRED = {
    "geosite.dat": {"category-geoblock-ru": 10000, "category-ru": 500,
                    "youtube": 70, "ai": 70, "banned-ru": 20,
                    "telegram": 5, "private": 20},
    "geoip.dat": {"ru": 10000, "blocked-ru": 500,
                  "telegram": 5, "private": 10},
}


def validate_geodata(name, data, requirements=None):
    """Validate GeoIPList/GeoSiteList data and presence of required categories.

    Schema: v2fly/v2ray-core app/router/routercommon/common.proto.
    Both top-level lists have repeated 'entry' in field 1.
    Each entry has country_code (field 1) and repeated domain/CIDR (field 2).
    """
    requirements = GEODATA_REQUIRED[name] if requirements is None else requirements
    categories = {}
    for number, entry in _protobuf_fields(data):
        if number != 1:
            continue
        code = None
        count = 0
        for field, value in _protobuf_fields(entry):
            if field == 1:
                code = value.decode("utf-8").lower()
            elif field == 2:
                count += 1
        if code:
            if code in categories:
                raise ValueError(name + ": duplicate geodata category " + code)
            categories[code] = count
    for code, minimum in requirements.items():
        if categories.get(code, 0) < minimum:
            raise ValueError(name + ": " + code + " is missing or too small: "
                             + str(categories.get(code, 0)))
    return categories


def validate_update_budget(records, previous):
    """Fail closed on unusually large upstream revisions; require manual review."""
    old = previous.get("files", {})
    for path, now in records.items():
        then = old.get(path)
        if not then:
            continue
        if is_complete_source_migration(path, then, now):
            continue
        before, after = then.get("entries"), now.get("entries")
        if isinstance(before, int) and before > 0 and isinstance(after, int):
            # Allow routine RKN churn, reject an abrupt 45% shrink or >2.5x growth.
            # The workflow must NOT publish partially trusted data automatically.
            if after < before * 0.55 or after > before * 2.5:
                raise ValueError("Source drift requires review: " + path
                                 + " before=" + str(before) + " after=" + str(after))


def is_complete_source_migration(path, previous, current):
    filename = path.rsplit("/", 1)[-1]
    stem = ("refilter-domain" if path.startswith("rules/") and filename in
            ("rkn-domains.list", "rkn-domains.json") else
            "refilter-ip" if path.startswith("rules/") and filename in
            ("rkn-ips.list", "rkn-ips.json", "rkn-ips.cidr") else None)
    return bool(stem and previous.get("source", "").endswith("/release/" + stem + ".list")
                and current.get("source", "").endswith("/release/" + stem + "-full.list"))


def validate_source_churn(path, previous_blob, current_blob, max_churn=0.5):
    """Reject high-volume source replacement even when entry counts match."""
    if previous_blob is None:
        return
    def entries(blob):
        return {line.strip() for line in blob.decode("utf-8-sig").splitlines()
                if line.strip() and not line.lstrip().startswith("#")}
    before = entries(previous_blob)
    after = entries(current_blob)
    if not before or not after:
        raise ValueError("Missing rule data in " + path)
    if not 0 <= max_churn <= 1:
        raise ValueError("Invalid source churn threshold")
    unchanged = len(before.intersection(after))
    churn = 1.0 - unchanged / max(len(before), len(after))
    if churn > max_churn:
        raise ValueError("Unsafe source replacement: " + path + " changed fraction "
                         + format(churn, ".1%") + "; manual review required")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def promote_staged(root, stage, generated):
    """Promote all files with prepared backups; restore on a write failure."""
    changed = {relative for relative, data in generated.items()
               if not (root / relative).is_file() or (root / relative).read_bytes() != data}
    if not changed:
        return
    with tempfile.TemporaryDirectory(prefix=".garasu-publish-", dir=root) as workspace:
        workspace = Path(workspace)
        incoming = workspace / "incoming"
        backups = workspace / "backups"
        existed = set()
        for relative in sorted(changed):
            prepared = incoming / relative
            prepared.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(stage / relative, prepared)
            target = root / relative
            if target.is_file():
                saved = backups / relative
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(target, saved)
                existed.add(relative)
        promoted = []
        try:
            for relative in sorted(changed):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(incoming / relative, target)
                promoted.append(relative)
        except OSError:
            failures = []
            for relative in reversed(promoted):
                target = root / relative
                try:
                    if relative in existed:
                        os.replace(backups / relative, target)
                    else:
                        target.unlink()
                except OSError as error:
                    failures.append(str(error))
            if failures:
                raise RuntimeError("Promotion failed and rollback was incomplete: "
                                   + "; ".join(failures))
            raise

def run():
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", REPO):
        raise ValueError("Invalid GITHUB_REPOSITORY")
    revision = resolve_upstream_revision()
    last_updated = upstream_commit_date(revision)
    upstream_origin = "https://raw.githubusercontent.com/DigneZzZ/routing/" + revision
    previous_path = ROOT / "install/manifest.json"
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
    with tempfile.TemporaryDirectory(prefix="garasu-") as tmp:
        temp = Path(tmp)
        records = {}
        generated = {}
        source_metadata = {}
        source_bytes = {}
        def add(path, data, source=None, count=None, source_blob=None):
            if path.startswith("rules/") and path.count("/") == 1:
                current = ROOT / path
                previous_blob = current.read_bytes() if current.is_file() else None
                threshold = 0.60 if "rkn-" in path else 0.50
                candidate = {"source": upstream_raw_url(revision, source)} if source else {}
                if not is_complete_source_migration(path, previous.get("files", {}).get(path, {}), candidate):
                    validate_source_churn(path, previous_blob, data, max_churn=threshold)
            generated[path] = data
            if source is not None:
                entry = {"source": upstream_raw_url(revision, source), "sha256": digest(data), "bytes": len(data)}
                if source_blob is not None:
                    entry["source_sha256"] = digest(source_blob)
                    entry["source_bytes"] = len(source_blob)
                if count is not None:
                    entry["entries"] = count
                records[path] = entry
        for name, (source, minimum) in DOMAIN.items():
            original = fetch(source, revision)
            blob, count = domains(original, minimum)
            if name == "rkn-domains":
                source_bytes["blocked_domains"] = original
                source_metadata["blocked_domains"] = {
                    "dataset": "refilter-domain-full", "url": upstream_raw_url(revision, source),
                    "revision": revision, "sha256": digest(original),
                    "bytes": len(original), "entries": count}
            add("rules/" + name + ".list", blob, source, count)
            add("rules/singbox/" + name + ".json", singbox_domains(blob), source, count)
            add("rules/surge/" + name + ".list", surge_domains(blob), source, count)
            add("rules/quantumultx/" + name + ".list",
                quantumultx_domains(blob, policy_for(name)), source, count)
        for name, (source, minimum) in IP.items():
            original = fetch(source, revision)
            sr, mihomo, count = ip_data(original, minimum, name=name)
            if name == "rkn-ips":
                source_bytes["blocked_ips"] = original
                source_metadata["blocked_ips"] = {
                    "dataset": "refilter-ip-full", "url": upstream_raw_url(revision, source),
                    "revision": revision, "sha256": digest(original),
                    "bytes": len(original), "entries": count}
            add("rules/" + name + ".list", sr, source, count)
            add("rules/" + name + ".cidr", mihomo, source, count)
            add("rules/singbox/" + name + ".json", singbox_ips(mihomo), source, count)
            add("rules/surge/" + name + ".list", surge_ips(mihomo), source, count)
            add("rules/quantumultx/" + name + ".list",
                quantumultx_ips(mihomo, policy_for(name)), source, count)
        validate_source_metadata(source_metadata)
        for key, info in source_metadata.items():
            if len(source_bytes[key]) != info["bytes"] or digest(source_bytes[key]) != info["sha256"]:
                raise ValueError("Blocked input integrity mismatch: " + key)
        for name, (source, minimum) in GEO.items():
            original = fetch(source, revision)
            blob = original
            if len(blob) < minimum or blob.startswith(b"<html"):
                raise ValueError("Invalid geodata " + name)
            validate_geodata(name, blob)
            if name == "geosite.dat":
                blob = replace_geodata_category(name, blob, "banned-ru",
                                                generated["rules/rkn-domains.list"])
                required_category = "banned-ru"
                required_count = source_metadata["blocked_domains"]["entries"]
            else:
                blob = replace_geodata_category(name, blob, "blocked-ru",
                                                generated["rules/rkn-ips.cidr"])
                required_category = "blocked-ru"
                required_count = source_metadata["blocked_ips"]["entries"]
            if validate_geodata(name, blob)[required_category] != required_count:
                raise ValueError("Geodata blocked category differs from complete source")
            add("geo/" + name, blob, source, source_blob=original)
        validate_update_budget(records, previous)
        changed = previous.get("files") != records
        manifest = {"name": "Garasu MAX", "upstream": upstream_origin,
                    "upstream_revision": revision, "sources": source_metadata,
                    "files": records}
        add("install/manifest.json", (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode())
        base = "https://raw.githubusercontent.com/" + REPO + "/main"
        for app in ("incy", "happ"):
            profile = json.loads((ROOT / "clients" / (app + ".json")).read_text())
            profile["Name"] = "Garasu MAX"
            profile["GlobalProxy"] = "true"
            profile["Geoipurl"] = base + "/geo/geoip.dat"
            profile["Geositeurl"] = base + "/geo/geosite.dat"
            profile["LastUpdated"] = last_updated
            encoded = (json.dumps(profile, ensure_ascii=False, indent=2) + "\n").encode()
            add("clients/" + app + ".json", encoded)
            if app == "happ":
                happ_link = "happ://routing/onadd/" + base64.b64encode(json.dumps(
                    profile, ensure_ascii=False, separators=(",", ":")).encode()).decode()
        qx_filters = []
        rule_order = ("rkn-domains", "rkn-ips", "youtube", "discord", "ai",
                      "crypto", "proxy", "proxy-ips", "ads", "games", "direct",
                      "direct-ips", "ru-ips")
        for name in rule_order:
            qx_filters.append(
                base + "/rules/quantumultx/" + name + ".list, tag=Garasu-" + name
                + ", force-policy=" + policy_for(name) + ", enabled=true")
        quantumultx_link = ("quantumult-x:///add-resource?remote-resource="
                           + quote(json.dumps({"filter_remote": qx_filters},
                                              separators=(",", ":")), safe=""))
        links = {
            "shadowrocket": "shadowrocket://config/add/" + base + "/clients/shadowrocket.conf",
            "incy": "incy://autorouting/onadd/" + base + "/clients/incy.json",
            "happ": happ_link,
            "mihomo_template": base + "/clients/mihomo-remnawave.yaml",
            "stash_template": base + "/clients/stash-remnawave.yaml",
            "singbox_template": base + "/clients/singbox-remnawave.json",
            "xray_advanced_template": base + "/clients/xray-advanced-remnawave.json",
            "quantumultx": quantumultx_link,
            "surge_rulesets": {n: base + "/rules/surge/" + n + ".list"
                               for n in rule_order},
        }
        add("install/links.json", (json.dumps(links, ensure_ascii=False, indent=2) + "\n").encode())
        # Validate all dependent artifacts before any persistent file write.
        assert "geoip:blocked-ru" in profile["ProxyIp"]
        assert "geosite:banned-ru" in profile["ProxySites"]
        assert len(records) == 58, len(records)
        assert json.loads(generated["clients/incy.json"])["Name"] == "Garasu MAX"
        for relative, data in generated.items():
            target = temp / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        # Generate the quality snapshot from the SAME validated stage tree.
        # If the audit fails, not a single persistent rule is published.
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/audit_rules.py"),
             "--root", str(temp), "--write"],
            check=True,
        )
        for relative in ("reports/quality.json", "reports/quality.md"):
            generated[relative] = (temp / relative).read_bytes()
        promote_staged(ROOT, temp, generated)
        print("Garasu MAX: " + str(len(records)) + " validated datasets; changed=" + str(changed))

if __name__ == "__main__":
    run()
