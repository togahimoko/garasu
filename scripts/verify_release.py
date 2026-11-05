#!/usr/bin/env python3
"""Deterministic offline integrity gate for Garasu release assets.

Only reads the supplied checkout; never reaches a VPS, opens a subscription,
modifies a user profile or refreshes upstream data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = (
    "rkn-domains", "youtube", "discord", "ai", "crypto", "proxy",
    "ads", "games", "direct", "rkn-ips", "proxy-ips", "direct-ips", "ru-ips",
)
GITHUB_RAW = re.compile(
    r"https://raw\.githubusercontent\.com/togahimoko/garasu/"
    r"(?P<branch>main|dev|staging|refactor)/(?P<path>[A-Za-z0-9_./-]+)"
)
MARKDOWN_LINK = re.compile(r"\]\(([^)]+)\)")


class ReleaseError(ValueError):
    """A release invariant is broken."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReleaseError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_file(root: Path, rel: str):
    return json.loads((root / rel).read_text(encoding="utf-8"))


def verify_manifest(root: Path) -> int:
    manifest_path = root / "install/manifest.json"
    manifest_data = manifest_path.read_bytes()
    manifest = json.loads(manifest_data)
    records = manifest.get("files")
    require(isinstance(records, dict) and len(records) >= 50,
            "install/manifest.json has an incomplete files map")
    for rel, info in records.items():
        p = root / rel
        require(p.is_file() and p.resolve().is_relative_to(root.resolve()),
                "Missing or unsafe manifest asset: " + rel)
        actual = p.read_bytes()
        require(len(actual) == info["bytes"] and digest(actual) == info["sha256"],
                "Manifest size/hash mismatch: " + rel)
    links = json_file(root, "install/links.json")
    require(links.get("manifest_sha256") == digest(manifest_data),
            "install/links.json has stale manifest SHA256")
    require(links.get("manifest_url") ==
            "https://raw.githubusercontent.com/togahimoko/garasu/main/install/manifest.json",
            "install/links.json points to an unexpected manifest")
    return len(records)


def verify_mrs(root: Path) -> int:
    base = root / "release/mihomo/.mrs"
    manifest = json_file(root, "release/mihomo/.mrs/manifest.json")
    records = manifest.get("files", [])
    extras = json_file(root, "policy/extra_categories.json")["categories"]
    expected = set(CATEGORIES) | {name for name,info in extras.items()
                                  if info["behavior"] in ("domain","ipcidr")}
    require({x["name"] for x in records} == expected
            and len(records) == len(expected),
            "Unexpected MRS categories or duplicate manifest entries")
    files = {p.name for p in base.glob("*.mrs")}
    require(files == {x + ".mrs" for x in expected},
            "Missing, extra or stale binary MRS file")
    for record in records:
        name = record["name"]
        blob = (base / (name + ".mrs")).read_bytes()
        require(len(blob) == record["mrs_bytes"] and
                digest(blob) == record["sha256"],
                "MRS integrity mismatch: " + name)
        src = root / record["source"]
        require(src.is_file() and src.resolve().is_relative_to(root.resolve()),
                "MRS source missing/unsafe: " + name)
        require(src.stat().st_size == record["src_bytes"],
                "Source changed without rebuilding MRS: " + name)
    return len(records)


def verify_links(root: Path, target_branch: str) -> int:
    count = 0
    for doc in [root / "README.md", root / "SOURCES.md"] + list((root / "docs").rglob("*.md")) + list((root / "release").rglob("README.md")):
        for link in MARKDOWN_LINK.findall(doc.read_text(encoding="utf-8")):
            if link.startswith(("http:", "https:", "#", "mailto:")):
                continue
            candidate = (doc.parent / link.split("#", 1)[0]).resolve()
            require(candidate.is_relative_to(root.resolve()) and candidate.exists(),
                    "Broken local documentation link: " + str(doc.relative_to(root)) + " -> " + link)
            count += 1

    for source in [root / "README.md", root / "SOURCES.md"] + [
        p for p in (root / "release").rglob("*")
        if p.is_file() and p.suffix in (".json", ".yaml", ".conf", ".md")
    ]:
        contents = source.read_text(encoding="utf-8", errors="replace")
        for found in GITHUB_RAW.finditer(contents):
            ref, rel = found.group("branch", "path")
            require((root / rel).is_file(),
                    "Broken raw GitHub link: " + str(source.relative_to(root)) + " -> " + rel)
            require(ref not in ("staging", "refactor"),
                    "Obsolete branch in raw GitHub URL: " + str(source.relative_to(root)))
            count += 1
    for rel in ("release/mihomo/config.yaml", "release/stash/config.yaml",
                "release/shadowrocket/config.conf", "release/remnawave/srr.json"):
        text = (root / rel).read_text(encoding="utf-8")
        # The production profile must use canonical remote providers.
        if "raw.githubusercontent.com/togahimoko/garasu/" in text:
            require("/" + target_branch + "/release/" in text,
                    "Canonical release points to wrong branch: " + rel)
        require(not re.search(r"/(?:dev|staging|refactor)/release/", text)
                if target_branch == "main" else
                not re.search(r"/(?:staging|refactor)/release/", text),
                "Release has a non-target development URL: " + rel)
    return count


def verify_contract(root: Path) -> None:
    text = (root / "release/mihomo/config.yaml").read_text(encoding="utf-8")
    require(text.count("proxies: # LEAVE THIS LINE!") == 2,
            "Mihomo Remnawave insertion points changed")
    require("type: select" not in text and "name: Garasu" in text
            and "type: url-test" in text,
            "Mihomo automatic route missing")
    require("MATCH,Garasu" in text, "Mihomo fallback is missing")
    for p in (root / "release").rglob("*.json"):
        json.loads(p.read_text(encoding="utf-8"))
    srr = json_file(root, "release/remnawave/srr.json")
    active = [rule for rule in srr["rules"] if rule.get("enabled")]
    require(active[0]["responseType"] == "BROWSER"
            and active[-1]["responseType"] == "XRAY_BASE64",
            "SSR browser/fallback policy changed")
    require(all(rule.get("responseModifications", {})
                .get("subscriptionTemplate", "Default") == "Default"
                for rule in active),
            "SSR refers to an unverified named template")
    template_types = ("MIHOMO", "STASH", "SINGBOX", "CLASH", "XRAY_JSON")
    require(all(sum(r["responseType"] == t for r in active) == 1
                for t in template_types), "SSR missing/duplicate one of the five native formats")
    xray = next(r for r in active if r["responseType"] == "XRAY_JSON")
    xray_condition = xray["conditions"]
    require(len(xray_condition) == 1
            and xray_condition[0]["headerName"] == "user-agent"
            and xray_condition[0]["operator"] == "REGEX"
            and xray_condition[0]["value"].startswith("^(?:garasu-xray-json")
            and xray.get("responseModifications", {}).get("ignoreHostXrayJsonTemplate") is True,
            "Xray JSON must remain explicit opt-in, not a catch-all")
    require(active[-1]["conditions"] == []
            and all(r["conditions"] for r in active[:-1]),
            "SSR fallback must be the only catch-all")
    require(next(r for r in active if r["name"] == "Clash Core Clients")["responseType"] == "CLASH",
            "Clash clients must get their own native YAML, not MIHOMO")
    require(not list((root / ".github/workflows").glob("*.yml"))
            and not list((root / ".github/workflows").glob("*.yaml")),
            "Unexpected GitHub Actions workflow")


def verify(root: Path, branch: str = "main") -> dict:
    root = root.resolve()
    require(branch in ("main", "dev"), "Branch must be main or dev")
    require((root / "release/mihomo/config.yaml").is_file(),
            "Not a Garasu repository checkout")
    result = {
        "manifest_assets": verify_manifest(root),
        "binary_mrs": verify_mrs(root),
        "checked_links": verify_links(root, branch),
        "release_contract": "PASS",
    }
    verify_contract(root)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--branch", choices=("main", "dev"), default="main")
    args = parser.parse_args()
    result = verify(args.root, args.branch)
    for key, value in result.items():
        print("PASS", key, value)
    print("PASS offline Garasu release integrity")


if __name__ == "__main__":
    main()
