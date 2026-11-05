#!/usr/bin/env python3
"""Real cold-start remote rule download test, isolated from running VPN clients.

Uses ONLY fake localhost SOCKS nodes, ephemeral listening ports and temporary
cache directories. No active client settings, personal URLs or network routes
are modified. Downloads only public Garasu MRS/SRS assets.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time

import yaml

ROOT = Path(__file__).resolve().parents[1]
from scripts.sync_universal_routing import load_policy, provider_sets
ALL_PROVIDERS = provider_sets(load_policy(ROOT))
MRS_NAMES = frozenset(name for name,(behavior,_) in ALL_PROVIDERS.items()
                      if behavior in ("domain","ipcidr"))
CLASSICAL_NAMES = frozenset(ALL_PROVIDERS)-MRS_NAMES


def local_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def run_for(command: list[str], *, cwd: Path, seconds: int,
            validate) -> None:
    proc = subprocess.Popen(command, cwd=str(cwd),
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True)
    alive = False
    try:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            time.sleep(0.25)
        alive = proc.poll() is None
    finally:
        if alive:
            proc.terminate()
        try:
            output, _ = proc.communicate(timeout=7)
        except subprocess.TimeoutExpired:
            proc.kill()
            output, _ = proc.communicate()
    if not alive:
        raise RuntimeError("Isolated core exited before test completed: " +
                           output[-900:])
    validate(output)


def mihomo(core: Path, seconds: int, ref: str) -> None:
    cfg = yaml.safe_load((ROOT / "release/mihomo/config.yaml").read_text())
    if any(x.get("proxy") != "DIRECT" for x in cfg["rule-providers"].values()):
        raise RuntimeError("Mihomo remote assets still depend on a proxy")
    with tempfile.TemporaryDirectory(prefix="garasu-mihomo-cold-") as dirname:
        folder = Path(dirname)
        cfg["proxies"] = [{"name": "OFFLINE_SYNTHETIC", "type": "socks5",
                           "server": "127.0.0.1", "port": 29999}]
        cfg["proxy-groups"][0]["proxies"] = ["OFFLINE_SYNTHETIC"]
        for provider in cfg["rule-providers"].values():
            provider["url"]=provider["url"].replace(
                "/garasu/main/", "/garasu/"+ref+"/")
        cfg["mixed-port"] = local_port()
        path = folder / "config.yaml"
        path.write_text(yaml.safe_dump(cfg, allow_unicode=True))
        def validate(_log: str):
            names = {p.name.removeprefix("garasu-").removesuffix(".mrs")
                     for p in (folder / "rule-providers").glob("garasu-*.mrs")}
            classical={p.name.removeprefix("garasu-").removesuffix(".yaml")
                       for p in (folder/"rule-providers").glob("garasu-*.yaml")}
            if names!=MRS_NAMES or classical!=CLASSICAL_NAMES:
                raise RuntimeError("Mihomo cold cache incomplete: "+
                                   str(len(names))+"/"+str(len(MRS_NAMES))+" MRS, "+
                                   str(len(classical))+"/"+str(len(CLASSICAL_NAMES))+" classical")
            print(f"PASS Mihomo cold startup: {len(names)}/{len(MRS_NAMES)} MRS + "
                  f"{len(classical)} classical YAML fetched, VPN node offline")
        run_for([str(core), "-d", dirname, "-f", str(path)],
                cwd=folder, seconds=seconds, validate=validate)


def singbox(core: Path, seconds: int, ref: str) -> None:
    cfg = json.loads((ROOT / "release/singbox/config.json").read_text())
    if len(cfg["route"]["rule_set"]) != len(ALL_PROVIDERS):
        raise RuntimeError("Unexpected SRS rule-set count")
    for rule in cfg["route"]["rule_set"]:
        rule["url"]=rule["url"].replace(
            "/garasu/main/","/garasu/"+ref+"/")
    client = next(c for c in cfg["http_clients"] if c["tag"] == "garasu-rules")
    if "detour" in client:
        raise RuntimeError("SRS downloader still has proxy/detour dependency")
    with tempfile.TemporaryDirectory(prefix="garasu-singbox-cold-") as dirname:
        folder = Path(dirname)
        cfg["log"]["level"] = "info"
        cfg["inbounds"] = [{"type": "mixed", "tag": "QA_MIXED",
                            "listen": "127.0.0.1",
                            "listen_port": local_port()}]
        cfg["outbounds"].append({"type": "socks", "tag": "OFFLINE_SYNTHETIC",
                                 "server": "127.0.0.1",
                                 "server_port": 29999, "version": "5"})
        group = next(x for x in cfg["outbounds"] if x["type"] == "urltest")
        group["outbounds"] = ["OFFLINE_SYNTHETIC"]
        cfg["experimental"]["cache_file"]["path"] = str(folder / "cache.db")
        cfg["experimental"].pop("clash_api", None)
        path = folder / "config.json"
        path.write_text(json.dumps(cfg, ensure_ascii=False))
        def validate(log: str):
            tags = set(re.findall(r"updated rule-set (garasu-[a-z0-9-]+)",
                                  log))
            expected = {"garasu-" + n for n in ALL_PROVIDERS}
            if tags != expected:
                raise RuntimeError("sing-box cold SRS cache incomplete: "+
                                   str(len(tags))+"/"+str(len(expected)))
            print(f"PASS sing-box cold startup: {len(tags)}/{len(expected)} SRS fetched, VPN node offline")
        run_for([str(core), "run", "-c", str(path)], cwd=folder,
                seconds=seconds, validate=validate)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mihomo-core", type=Path, required=True)
    parser.add_argument("--singbox-core", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=20)
    parser.add_argument("--ref", default="main",
                        help="Public branch containing all Garasu source assets")
    args = parser.parse_args()
    if args.seconds < 4 or args.seconds > 90:
        parser.error("--seconds must be between 4 and 90")
    if not re.fullmatch(r"[a-zA-Z0-9/_-]{1,100}",args.ref) or ".." in args.ref:
        parser.error("Invalid public branch/ref")
    mihomo(args.mihomo_core.resolve(), args.seconds, args.ref)
    singbox(args.singbox_core.resolve(), args.seconds, args.ref)


if __name__ == "__main__":
    main()
