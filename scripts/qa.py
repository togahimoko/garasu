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
import time
import socket

ROOT = Path(__file__).resolve().parents[1]
# Running "python scripts/qa.py --core ..." puts scripts/ on sys.path,
# not the repository root, so the native verifier package import would fail.
# Keep both script and module execution independent of the caller's PYTHONPATH.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PYTHON = sys.executable


def run(title: str, argv: list[str], *, env=None) -> None:
    print("\n== " + title + " ==", flush=True)
    subprocess.run(argv, cwd=ROOT, env=env, check=True)
    print("PASS " + title, flush=True)


def check_native(core: Path) -> None:
    """Test binary MRS and 0/1/2/5 nodes with locally loaded provider fixtures."""
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("Native QA requires PyYAML") from exc

    from scripts.verify_release import digest, json_file
    from scripts.sync_universal_routing import offline_mihomo_fixture
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
            auto = cfg["proxy-groups"][0]
            auto["proxies"] = [proxy["name"] for proxy in cfg["proxies"]]
            # Offline native syntax testing: substitute local exact rule data
            # for HTTP providers. Production YAML remains remote and small.
            cfg = offline_mihomo_fixture(cfg, ROOT)
            if (len(cfg["rule-providers"]["rkn-domains"]["payload"]) < 10000 or
                    len(cfg["rule-providers"]["rkn-ips"]["payload"]) < 20000 or
                    len(cfg["rule-providers"]["ru-ips"]["payload"]) < 20000):
                raise RuntimeError("Incomplete local source snapshot")
            cfg["mixed-port"] = 18000 + count
            path = tmp / (f"synthetic-{count}.yaml")
            path.write_text(yaml.safe_dump(cfg, allow_unicode=True),
                            encoding="utf-8")
            run(f"Mihomo native syntax / {count} synthetic nodes",
                [str(core), "-t", "-d", str(tmp), "-f", str(path)])
        print("PASS native Mihomo validation", flush=True)


def check_singbox_native(core: Path) -> None:
    """Validate sing-box 1.14 native schema with exact locally published sources."""
    import json
    from scripts.sync_universal_routing import SINGBOX_BASE

    cfg = json.loads((ROOT / "release/singbox/config.json").read_text())
    if len(cfg["route"]["rule_set"]) != 10:
        raise RuntimeError("Unexpected sing-box provider count")
    for item in cfg["route"]["rule_set"]:
        name = item["tag"].removeprefix("garasu-")
        path = ROOT / "release/singbox/rules" / (name + ".srs")
        if (item.get("type"), item.get("format"), item.get("url")) != (
                "remote", "binary", SINGBOX_BASE + name + ".srs"):
            raise RuntimeError("Unrecognized sing-box remote rule-set: " + name)
        item.clear()
        item.update({"type": "local", "tag": "garasu-" + name,
                     "format": "binary", "path": str(path)})

    # No real node credentials or network services are ever used by this check.
    cfg["outbounds"].append({
        "type": "socks", "tag": "OFFLINE_TEST_NODE",
        "server": "127.0.0.1", "server_port": 19080, "version": "5"
    })
    group = next(x for x in cfg["outbounds"] if x["tag"] == "→ Remnawave")
    group["outbounds"] = ["OFFLINE_TEST_NODE"]
    # Do not rewrite HTTP client detour: that hid a production runtime bug.
    # The local rule fixtures allow startup without downloading from a proxy.
    with tempfile.TemporaryDirectory(prefix="garasu-singbox-native-") as directory:
        tmp = Path(directory)
        def free_local_port() -> int:
            with socket.socket() as server:
                server.bind(("127.0.0.1", 0))
                return server.getsockname()[1]
        cfg["inbounds"] = [{"type": "mixed", "tag": "QA_MIXED",
                            "listen": "127.0.0.1", "listen_port": free_local_port()}]
        cfg["experimental"].pop("clash_api", None)
        cfg["experimental"]["cache_file"]["path"] = str(tmp / "qa-cache.db")
        dest = tmp / "singbox.json"
        dest.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        run("sing-box native 1.14 schema + ten source rule-sets",
            [str(core), "check", "-c", str(dest)])
        proc = subprocess.Popen([str(core), "run", "-c", str(dest)],
                                cwd=directory, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                stdin=subprocess.DEVNULL)
        try:
            time.sleep(2.5)
            if proc.poll() is not None:
                output = proc.communicate(timeout=5)[0]
                raise RuntimeError("sing-box native runtime cannot start: " +
                                   output[-1600:])
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.communicate(timeout=6)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate()
        print("PASS sing-box real process startup with 10 native rule sets", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", choices=("main", "dev"), default="main",
                        help="Branch expected inside release URLs")
    parser.add_argument("--core", type=Path,
                        help="Optional local Mihomo binary for native offline tests")
    parser.add_argument("--singbox-core", type=Path,
                        help="Optional sing-box 1.14 binary for native source-format checks")
    parser.add_argument("--cold-network", action="store_true",
                        help="Also run isolated real cold-start 10/10 MRS and 10/10 SRS downloads via DIRECT; requires both cores and internet")
    args = parser.parse_args()
    if args.cold_network and not (args.core and args.singbox_core):
        parser.error("--cold-network needs --core and --singbox-core")
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
        ("One production subscription and public install links",
         [PYTHON, "scripts/sync_public_links.py", "--check"]),
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
        run("Classic Clash YAML provider parser / 1,2,5 synthetic nodes",
            [PYTHON, "scripts/check_clash_template.py", "--core", str(core)], env=env)
        run("Native offline DIRECT / PROXY / REJECT routing",
            [PYTHON, "scripts/smoke_universal_mihomo.py", "--core", str(core)],
            env=env)
    if args.singbox_core:
        binary = args.singbox_core.expanduser().resolve()
        if not binary.is_file():
            parser.error("sing-box binary not found: " + str(binary))
        check_singbox_native(binary)
    if args.cold_network:
        run("Native cold start without a working VPN (10 MRS + 10 SRS)",
            [PYTHON, "scripts/smoke_cold_bootstrap.py",
             "--mihomo-core", str(args.core.expanduser().resolve()),
             "--singbox-core", str(args.singbox_core.expanduser().resolve())],
            env=env)
    print("\nPASS Garasu release quality gate", flush=True)


if __name__ == "__main__":
    main()
