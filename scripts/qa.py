#!/usr/bin/env python3
"""Single offline quality gate for Garasu. No GitHub Actions, servers or subscriptions."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(title: str, argv: list[str], *, env=None) -> None:
    print("\n== " + title + " ==", flush=True)
    subprocess.run(argv, cwd=ROOT, env=env, check=True)
    print("PASS " + title, flush=True)


def check_native(core: Path) -> None:
    """Test actual binary MRS compilation and 0/1/2/5 synthetic node configs."""
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("Native QA requires PyYAML") from exc

    from scripts.verify_release import digest, json_file
    release = json_file(ROOT, "release/mihomo/.mrs/manifest.json")
    with tempfile.TemporaryDirectory(prefix="garasu-native-qa-") as directory:
        tmp = Path(directory)
        run("Rebuild binary MRS", [
            PYTHON, "release/mihomo/build.py",
            "--core", str(core), "--source-root", str(ROOT),
            "--output", str(tmp / "compiled"),
            "--source-commit", "qa-local-rebuild",
        ])
        for record in release["files"]:
            src = (ROOT / "release/mihomo/.mrs" /
                   (record["name"] + ".mrs")).read_bytes()
            rebuilt = (tmp / "compiled" /
                       (record["name"] + ".mrs")).read_bytes()
            if digest(src) != digest(rebuilt):
                raise RuntimeError("MRS rebuild changed: " + record["name"])
        print("PASS 13/13 reproduced binary MRS", flush=True)

        template = yaml.safe_load(
            (ROOT / "release/mihomo/config.yaml").read_text(encoding="utf-8"))
        for count in (0, 1, 2, 5):
            # Every test uses fake local endpoints and local MRS files.
            cfg = yaml.safe_load(yaml.safe_dump(template))
            cfg["proxies"] = [
                {"name": f"FAKE_NODE_{i}", "type": "socks5",
                 "server": "127.0.0.1", "port": 29000 + i}
                for i in range(count)
            ]
            selector, auto = cfg["proxy-groups"]
            selector["proxies"] = ["Garasu Auto"] + [
                proxy["name"] for proxy in cfg["proxies"]
            ]
            auto["proxies"] = []
            # The production universal profile must remain self-contained.
            if set(cfg["rule-providers"]) != {"ads"}:
                raise RuntimeError("Unexpected remote provider in universal mode")
            if cfg["rule-providers"]["ads"]["type"] != "inline":
                raise RuntimeError("Ads list must be inlined for offline startup")
            cfg["mixed-port"] = 18000 + count
            path = tmp / (f"synthetic-{count}.yaml")
            path.write_text(yaml.safe_dump(cfg, allow_unicode=True),
                            encoding="utf-8")
            run(f"Mihomo native syntax / {count} synthetic nodes",
                [str(core), "-t", "-d", str(tmp), "-f", str(path)])
        print("PASS native Mihomo validation", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", choices=("main", "dev"), default="main",
                        help="Branch expected inside release URLs")
    parser.add_argument("--core", type=Path,
                        help="Optional local Mihomo binary for native offline tests")
    args = parser.parse_args()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")

    steps = [
        ("Offline release invariants",
         [PYTHON, "scripts/verify_release.py", "--branch", args.branch]),
        ("Unit and regression tests",
         [PYTHON, "-m", "unittest", "discover", "-s", "tests", "-v"]),
        ("Public credential exposure",
         [PYTHON, "scripts/audit_public_exposure.py"]),
        ("Source rule consistency",
         [PYTHON, "scripts/audit_rules.py", "--check"]),
        ("Single universal Garasu routing policy",
         [PYTHON, "scripts/sync_universal_routing.py", "--check"]),
        ("Cross-client routing coverage",
         [PYTHON, "scripts/audit_route_coverage.py", "--check"]),
        ("Binary GeoSite/GeoIP semantic integrity",
         [PYTHON, "scripts/audit_geodata.py", "--check"]),
        ("Python syntax",
         [PYTHON, "-m", "compileall", "-q", "scripts", "tests",
          "release/mihomo/build.py"]),
    ]
    for title, argv in steps:
        run(title, argv, env=env)
    if args.core:
        core = args.core.expanduser().resolve()
        if not core.is_file():
            parser.error("Mihomo binary not found: " + str(core))
        check_native(core)
        run("Native offline DIRECT / PROXY / REJECT routing",
            [PYTHON, "scripts/smoke_universal_mihomo.py", "--core", str(core)],
            env=env)
    print("\nPASS Garasu release quality gate", flush=True)


if __name__ == "__main__":
    main()
