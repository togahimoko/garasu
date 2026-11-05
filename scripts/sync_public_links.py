#!/usr/bin/env python3
"""Reconcile legacy install endpoints with ONE production Garasu release.

No personal subscription or server is accessed. Read-only unless --write.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
BASE = "https://raw.githubusercontent.com/togahimoko/garasu/main"


def encoded(data):
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def expected_files(root=ROOT):
    """Return dependent public files with all production pointers synchronized."""
    release = root / "release"
    if (release/"remnawave/srr-test.json").exists():
        raise ValueError("A separate test SSR must not be shipped")
    mobile = {
        app: json.loads((release / app / "config.json").read_text(encoding="utf-8"))
        for app in ("incy", "happ")
    }
    from scripts.sync_universal_routing import load_policy, mobile_routing_matrix
    # Thin fixture copies can omit source policy, but full release validates
    # every field against the canonical generator; both clients must match.
    matrix = (mobile_routing_matrix(load_policy(root))
              if (root/"policy/universal.json").exists() else None)
    for app, profile in mobile.items():
        if (profile["Name"] != "Garasu"
            or profile["RouteOrder"] != "block-proxy-direct"
            or not {"geosite:garasu-ads","geosite:category-ads","geosite:win-spy"} <= set(profile["BlockSites"])
            or (matrix is not None and (
                profile["BlockSites"] != matrix["block"]
                or profile["ProxySites"] != matrix["proxy"]
                or profile["DirectSites"] != matrix["direct"]))):
            raise ValueError(f"{app}: not the canonical Garasu mobile policy")
        for field, dataset in (("Geositeurl", "geosite.dat"), ("Geoipurl", "geoip.dat")):
            if profile[field] != BASE + "/geo/" + dataset:
                raise ValueError(f"{app}: unexpected geo asset URL")
    if mobile["happ"] != mobile["incy"]:
        raise ValueError("INCY and Happ production profiles differ")

    ssr = json.loads((release / "remnawave/srr.json").read_text(encoding="utf-8"))
    happ_rules = [r for r in ssr["rules"] if r["name"] == "Happ Garasu" and r["enabled"]]
    if len(happ_rules) != 1:
        raise ValueError("One enabled production Happ rule is required")
    headers = happ_rules[0]["responseModifications"]["headers"]
    happ_header = next(h["value"] for h in headers if h["key"].lower() == "routing")
    if not happ_header.startswith("happ://routing/onadd/") or len(happ_header) > 3500:
        raise ValueError("Invalid or oversized Happ header")
    decoded = json.loads(base64.b64decode(happ_header.split("/onadd/", 1)[1], validate=True))
    if decoded != mobile["happ"]:
        raise ValueError("Production SSR Happ profile diverges from release")

    manifest = json.loads((root / "install/manifest.json").read_text(encoding="utf-8"))
    # Every published binary, rule-set and licensed extra category is hashed
    # independently. An absent/stale file must fail publication/QA.
    tracked = []
    if (root/"policy/extra_categories.json").exists():
        tracked = ["policy/universal.json","policy/extra_categories.json",
                   "docs/licenses/roscomvpn-geosite-MIT.txt"]
        for directory in ("rules/extra", "release/providers", "release/clash/providers",
                          "release/singbox/rules", "release/mihomo/.mrs",
                          "release/shadowrocket/providers"):
            tracked.extend(p.relative_to(root).as_posix() for p in
                           (root / directory).rglob("*") if p.is_file())
    for relative in sorted(set(tracked)):
        blob=(root / relative).read_bytes()
        record=manifest["files"].setdefault(relative,{})
        record["sha256"]=sha(blob)
        record["bytes"]=len(blob)
    output = {}
    # Legacy public URLs must not leak old manual selectors or text providers.
    # Keep the exact native template at each compatibility path.
    aliases = {
        "clients/mihomo-remnawave.yaml": "release/mihomo/config.yaml",
        "clients/stash-remnawave.yaml": "release/stash/config.yaml",
        "clients/singbox-remnawave.json": "release/singbox/config.json",
        "clients/singbox-remnawave-1.14.json": "release/singbox/config.json",
        "clients/shadowrocket.conf": "release/shadowrocket/config.conf",
    }
    for legacy, current in aliases.items():
        blob = (root / current).read_bytes()
        output[legacy] = blob
        if legacy in manifest["files"]:
            manifest["files"][legacy]["sha256"] = sha(blob)
            manifest["files"][legacy]["bytes"] = len(blob)

    for app, profile in mobile.items():
        key = "clients/" + app + ".json"
        blob = encoded(profile)
        meta = manifest["files"][key]
        meta["sha256"] = sha(blob)
        meta["bytes"] = len(blob)
        output[key] = blob
    mbytes = encoded(manifest)
    output["install/manifest.json"] = mbytes

    links = json.loads((root / "install/links.json").read_text(encoding="utf-8"))
    links.update({
        "shadowrocket": "shadowrocket://config/add/" + BASE + "/release/shadowrocket/config.conf",
        "incy": "incy://autorouting/onadd/" + BASE + "/release/incy/config.json",
        "happ": happ_header,
        "mihomo_template": BASE + "/release/mihomo/config.yaml",
        "clash_template": BASE + "/release/clash/config.yaml",
        "stash_template": BASE + "/release/stash/config.yaml",
        "singbox_template": BASE + "/release/singbox/config.json",
        "xray_advanced_template": BASE + "/release/xray/config.json",
        "manifest_sha256": sha(mbytes),
    })
    output["install/links.json"] = encoded(links)
    if (release / "remnawave/srr-test.json").exists():
        raise ValueError("A separate test SSR must not be shipped")
    return output


def sync(write=False, root=ROOT):
    expected = expected_files(root)
    changed = [key for key, value in expected.items()
               if (root / key).read_bytes() != value]
    if changed and not write:
        raise SystemExit("STALE production install data: " + ", ".join(changed))
    if write:
        for name in changed:
            (root / name).write_bytes(expected[name])
            print("GENERATED", name, len(expected[name]))
    print("PASS one Garasu production policy and links")
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--write", action="store_true")
    args = parser.parse_args()
    sync(write=args.write)


if __name__ == "__main__":
    main()
