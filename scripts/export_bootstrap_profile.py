#!/usr/bin/env python3
"""Build a personal offline Mihomo bootstrap file from Remnawave YAML on stdin.

Intended for sending as a private Telegram document. Never writes user nodes to
the public Garasu repository or makes a client fetch a subscription URL.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "release/mihomo/config.yaml"
SUPPORTED_TYPES = {"vless", "vmess", "trojan", "ss", "socks5", "hysteria2"}


def build_profile(source: dict, template: dict) -> dict:
    if not isinstance(source, dict) or not isinstance(template, dict):
        raise ValueError("Both inputs must be Mihomo YAML mappings")
    nodes = source.get("proxies")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("No subscriber nodes found; refusing to create unusable file")
    names = []
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("Invalid subscriber proxy")
        name = node.get("name")
        if (not isinstance(name, str) or not name.strip()
                or name in ("DIRECT", "REJECT", "Garasu") or name in names
                or node.get("type") not in SUPPORTED_TYPES):
            raise ValueError("Invalid, unsupported or duplicate subscriber proxy name/type")
        names.append(name)

    groups = template.get("proxy-groups", [])
    if len(groups) != 1 or groups[0].get("name") != "Garasu":
        raise ValueError("Unexpected Garasu template group")
    providers = template.get("rule-providers")
    if not isinstance(providers, dict) or len(providers) != 37:
        raise ValueError("Incomplete Garasu rule-provider template")
    if any(x.get("proxy") != "DIRECT" for x in providers.values()):
        raise ValueError("Bootstrap rules would require an existing VPN")

    # Start from the canonical routing/DNS template, inserting only user's nodes.
    template["proxies"] = nodes
    groups[0]["proxies"] = names
    return template


def export(source: str, destination: Path) -> Path:
    output = destination.expanduser().resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError("Private subscriber configuration must NOT enter public repository")
    if output.suffix.lower() not in (".yaml", ".yml"):
        raise ValueError("Expected .yaml/.yml destination")
    config = build_profile(yaml.safe_load(source), yaml.safe_load(TEMPLATE.read_text()))
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation (no overwrite), private by default.
    fd = os.open(str(output), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            yaml.safe_dump(config, handle, allow_unicode=True, sort_keys=False)
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    content = sys.stdin.read()
    path = export(content, args.output)
    print(f"PRIVATE_BOOTSTRAP_READY {path} (no credentials printed)")


if __name__ == "__main__":
    main()
