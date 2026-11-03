#!/usr/bin/env python3
"""Garasu routing data publisher. Standard library only; no VPN credentials."""
import base64
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
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
    "rkn-domains": ("release/refilter-domain.list", 10000),
    "youtube": ("release/youtube.list", 60),
}
IP = {
    "rkn-ips": ("release/refilter-ip.list", 600),
    "proxy-ips": ("release/proxy-ip.list", 4),
    "direct-ips": ("release/direct-ip.list", 15),
    "ru-ips": ("release/ru-ip.list", 15000),
}
GEO = {
    "geoip.dat": ("v2ray/geoip.dat", 200000),
    "geosite.dat": ("v2ray/geosite.dat", 200000),
}

def fetch(path):
    url = UPSTREAM + "/" + path
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

def domains(blob, minimum):
    lines = blob.decode("utf-8-sig").splitlines()
    found = []
    seen = set()
    for row in lines:
        value = row.strip()
        if not value or value.startswith("#"):
            continue
        if not re.fullmatch(r"[+.]?[a-zA-Z0-9_*.-]+", value):
            raise ValueError("Invalid domain entry " + value[:100])
        if value not in seen:
            found.append(value)
            seen.add(value)
    if len(found) < minimum:
        raise ValueError("Domain source shrank " + str(len(found)))
    return ("# Garasu MAX | Source DigneZzZ/routing; see SOURCES.md\n"
            + "\n".join(found) + "\n").encode(), len(found)

def ip_data(blob, minimum):
    raw = []
    seen = set()
    for row in blob.decode("utf-8-sig").splitlines():
        value = row.strip()
        if not value or value.startswith("#"):
            continue
        net = ipaddress.ip_network(value, strict=False)
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


def digest(data):
    return hashlib.sha256(data).hexdigest()

def run():
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", REPO):
        raise ValueError("Invalid GITHUB_REPOSITORY")
    with tempfile.TemporaryDirectory(prefix="garasu-") as tmp:
        temp = Path(tmp)
        records = {}
        generated = {}
        def add(path, data, source=None, count=None):
            generated[path] = data
            if source is not None:
                entry = {"source": UPSTREAM + "/" + source, "sha256": digest(data), "bytes": len(data)}
                if count is not None:
                    entry["entries"] = count
                records[path] = entry
        for name, (source, minimum) in DOMAIN.items():
            blob, count = domains(fetch(source), minimum)
            add("rules/" + name + ".list", blob, source, count)
            add("rules/singbox/" + name + ".json", singbox_domains(blob), source, count)
        for name, (source, minimum) in IP.items():
            original = fetch(source)
            sr, mihomo, count = ip_data(original, minimum)
            add("rules/" + name + ".list", sr, source, count)
            add("rules/" + name + ".cidr", mihomo, source, count)
            add("rules/singbox/" + name + ".json", singbox_ips(mihomo), source, count)
        for name, (source, minimum) in GEO.items():
            blob = fetch(source)
            if len(blob) < minimum or blob.startswith(b"<html"):
                raise ValueError("Invalid geodata " + name)
            add("geo/" + name, blob, source)
        previous_path = ROOT / "install/manifest.json"
        previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
        changed = previous.get("files") != records
        manifest = {"name": "Garasu MAX", "upstream": UPSTREAM, "files": records}
        add("install/manifest.json", (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode())
        base = "https://raw.githubusercontent.com/" + REPO + "/main"
        last_updated = str(int(time.time())) if changed else None
        for app in ("incy", "happ"):
            profile = json.loads((ROOT / "clients" / (app + ".json")).read_text())
            profile["Name"] = "Garasu MAX"
            profile["GlobalProxy"] = "true"
            profile["Geoipurl"] = base + "/geo/geoip.dat"
            profile["Geositeurl"] = base + "/geo/geosite.dat"
            if last_updated:
                profile["LastUpdated"] = last_updated
            encoded = (json.dumps(profile, ensure_ascii=False, indent=2) + "\n").encode()
            add("clients/" + app + ".json", encoded)
            if app == "happ":
                happ_link = "happ://routing/onadd/" + base64.b64encode(json.dumps(
                    profile, ensure_ascii=False, separators=(",", ":")).encode()).decode()
        links = {
            "shadowrocket": "shadowrocket://config/add/" + base + "/clients/shadowrocket.conf",
            "incy": "incy://autorouting/onadd/" + base + "/clients/incy.json",
            "happ": happ_link,
            "mihomo_template": base + "/clients/mihomo-remnawave.yaml",
            "stash_template": base + "/clients/stash-remnawave.yaml",
            "singbox_template": base + "/clients/singbox-remnawave.json",
        }
        add("install/links.json", (json.dumps(links, ensure_ascii=False, indent=2) + "\n").encode())
        # Validate all dependent artifacts before any persistent file write.
        assert "geoip:blocked-ru" in profile["ProxyIp"]
        assert "geosite:banned-ru" in profile["ProxySites"]
        assert len(records) == 32, len(records)
        assert json.loads(generated["clients/incy.json"])["Name"] == "Garasu MAX"
        for relative, data in generated.items():
            target = temp / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        for relative, data in generated.items():
            target = ROOT / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or target.read_bytes() != data:
                shutil.copyfile(temp / relative, target)
        print("Garasu MAX: " + str(len(records)) + " validated datasets; changed=" + str(changed))

if __name__ == "__main__":
    run()
