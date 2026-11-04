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

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://raw.githubusercontent.com/togahimoko/garasu/main"


def encoded(data):
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def expected_files(root=ROOT):
    """Return dependent public files with all production pointers synchronized."""
    release = root / "release"
    mobile = {
        app: json.loads((release / app / "config.json").read_text(encoding="utf-8"))
        for app in ("incy", "happ")
    }
    for app, profile in mobile.items():
        if profile["Name"] != "Garasu" or profile["BlockSites"] != ["geosite:garasu-ads"]:
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
