#!/usr/bin/env python3
"""Compile Garasu domain/IP rules into true Mihomo MRS assets.

Manual/offline release tool; never invokes GitHub Actions or live servers.
Does not upload, activate or overwrite a running client subscription.
Usage:
  python3 release/mihomo/build.py --core /path/to/mihomo --output /tmp/garasu-mrs-build
Optionally specify --source-commit to identify the exact checked-out source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

PROJECT = Path(__file__).resolve().parents[2]

CATEGORIES = {
    "rkn-domains": "domain",
    "youtube": "domain",
    "discord": "domain",
    "ai": "domain",
    "crypto": "domain",
    "proxy": "domain",
    "ads": "domain",
    "games": "domain",
    "direct": "domain",
    "rkn-ips": "ipcidr",
    "proxy-ips": "ipcidr",
    "direct-ips": "ipcidr",
    "ru-ips": "ipcidr",
}


def all_categories(root: Path) -> dict[str,str]:
    extra=json.loads((root/"policy/extra_categories.json").read_text())["categories"]
    combined=dict(CATEGORIES)
    for name,spec in extra.items():
        if spec["behavior"] not in ("domain","ipcidr"):
            continue  # Classical rules are YAML; MRS cannot encode regexp/keyword.
        if name in combined and combined[name] != spec["behavior"]:
            raise ValueError("Conflicting category behavior: " + name)
        combined[name]=spec["behavior"]
    return combined


def build(core: Path, source_root: Path, output: Path, source_commit: str) -> dict:
    if output.resolve() == (source_root / "release" / "mihomo" / ".mrs").resolve():
        raise ValueError("Refuse in-place replacement of published assets; build in a staging directory")
    if any(output.resolve() == (source_root / "rules" / name).resolve()
           for name in (".", "..")):
        raise ValueError("Output must be outside source rules directory")
    output.mkdir(parents=True, exist_ok=True)
    version = subprocess.run([str(core), "-v"], capture_output=True, text=True, check=True)
    entries = []
    for name, kind in all_categories(source_root).items():
        provider_rel = Path("release/providers") / (name + ".txt")
        source_rel = provider_rel if (source_root / provider_rel).exists() else Path("rules") / (name + (".list" if kind == "domain" else ".cidr"))
        source = source_root / source_rel
        if not source.is_file():
            raise FileNotFoundError(source)
        dst = output / (name + ".mrs")
        # Use a temporary file so a failed converter cannot leave a broken release.
        temporary = output / (name + ".mrs.part")
        try:
            subprocess.run([str(core), "convert-ruleset", kind, "text",
                            str(source), str(temporary)], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            data = temporary.read_bytes()
            if len(data) < 20:
                raise ValueError("Unexpectedly small binary file: " + name)
            temporary.replace(dst)
        finally:
            temporary.unlink(missing_ok=True)
        entries.append({
            "name": name,
            "kind": kind,
            "source": source_rel.as_posix(),
            "src_bytes": source.stat().st_size,
            "mrs_bytes": dst.stat().st_size,
            "sha256": hashlib.sha256(dst.read_bytes()).hexdigest(),
        })
    manifest = {
        "source_commit": source_commit,
        "extra_categories_commit": json.loads((source_root/"rules/extra/provenance.json").read_text())["geosite_revision"],
        "format": "mihomo-mrs",
        "compiler": version.stdout.strip().splitlines()[0],
        "command": "mihomo convert-ruleset <domain|ipcidr> text <source> <target.mrs>",
        "note": "Manual release only. Sync compiled binaries with source changes before promotion.",
        "files": entries,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--core", type=Path, required=True, help="Mihomo executable")
    p.add_argument("--source-root", type=Path, default=PROJECT)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--source-commit", default="working-tree")
    args = p.parse_args()
    result = build(args.core, args.source_root, args.output, args.source_commit)
    total = sum(x["mrs_bytes"] for x in result["files"])
    print(f"PASS: {len(result['files'])} real MRS files, {total} bytes.")
    print("Compare produced SHA256 values with manifest before publishing.")


if __name__ == "__main__":
    main()
