#!/usr/bin/env python3
"""Offline syntax/load check for legacy Clash-style YAML and remote YAML providers.

Validates with the available Mihomo parser (Clash superset), not a claim that
the unmaintained legacy Clash binary supports all modern proxy protocols.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile
import yaml

ROOT = Path(__file__).resolve().parents[1]


def check(core: Path) -> None:
    src = yaml.safe_load((ROOT / "release/clash/config.yaml").read_text())
    if len(src["proxy-groups"]) != 1 or src["proxy-groups"][0]["type"] != "url-test":
        raise ValueError("Clash has manual/invalid routing group")
    if not src["rule-providers"]:
        raise ValueError("Missing Clash providers")
    with tempfile.TemporaryDirectory(prefix="garasu-clash-parser-") as folder:
        home = Path(folder)
        dest = home / "rule-providers"
        dest.mkdir()
        for name, provider in src["rule-providers"].items():
            remote = "https://raw.githubusercontent.com/togahimoko/garasu/main/release/clash/providers/" + name + ".yaml"
            if provider.get("url") != remote or provider.get("interval") != 21600:
                raise ValueError("Clash remote provider mismatch: " + name)
            shutil.copy2(ROOT / "release/clash/providers" / (name + ".yaml"), dest / (name + ".yaml"))
        for count in (1, 2, 5):
            profile = yaml.safe_load(yaml.safe_dump(src))
            profile["mixed-port"] = 21800 + count
            profile["proxies"] = [
                {"name": "SYNTHETIC_" + str(i), "type": "socks5",
                 "server": "127.0.0.1", "port": 29000 + i}
                for i in range(count)
            ]
            profile["proxy-groups"][0]["proxies"] = [
                item["name"] for item in profile["proxies"]
            ]
            for name, provider in profile["rule-providers"].items():
                provider["type"] = "file"
                provider["path"] = "./rule-providers/" + name + ".yaml"
                provider.pop("url", None)
                provider.pop("interval", None)
            output = home / f"clash-{count}.yaml"
            output.write_text(yaml.safe_dump(profile, allow_unicode=True))
            p = subprocess.run([str(core), "-t", "-d", str(home), "-f", str(output)],
                               capture_output=True, text=True, timeout=45)
            if p.returncode:
                raise RuntimeError("Clash-style parser failed for " + str(count)
                                   + " nodes:\n" + (p.stdout+p.stderr)[-2500:])
            print(f"PASS Clash YAML providers native parser / {count} synthetic nodes")
    print("PASS Clash compatibility-template parser check")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--core", required=True, type=Path)
    args = cli.parse_args()
    check(args.core.resolve())
