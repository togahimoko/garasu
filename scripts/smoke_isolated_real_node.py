#!/usr/bin/env python3
"""Read-only real-node smoke in an ISOLATED Mihomo instance.

Sources one personal node from an existing local YAML; does not print or copy
credentials outside an ephemeral 0600 directory. It never toggles TUN, system
proxy, Clash Verge settings, selected profile, or live runtime APIs.

All 37 rule provider downloads are served from a temporary local HTTP server,
so this proves cold-start provider wiring independent of GitHub availability.
The final outbound HTTPS probe is a real network test and can fail with an
unreachable personal node despite valid Garasu rules.
"""
from __future__ import annotations
import argparse
from collections import Counter
from contextlib import ExitStack
import http.server
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time

import yaml

ROOT = Path(__file__).resolve().parents[1]


class ConcurrentAssetServer(http.server.ThreadingHTTPServer):
    # Mihomo opens 37 provider connections concurrently; the default
    # Python server accept queue of 5 spuriously rejects local cold-starts.
    request_queue_size=128


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self,*args,directory=None,**kwargs):
        self.request_count=None
        super().__init__(*args,directory=directory,**kwargs)
    def log_message(self,*_):
        return


def freeport():
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1",0))
        return sock.getsockname()[1]


def smoke(core:Path,source:Path):
    source_data=yaml.safe_load(source.read_text())
    nodes=source_data.get("proxies")
    if not isinstance(nodes,list) or not nodes:
        raise ValueError("The local source profile contains no personal nodes")
    nodes=[dict(x) for x in nodes if isinstance(x,dict) and x.get("type")]
    if not nodes:
        raise ValueError("No usable nodes")
    profile=yaml.safe_load((ROOT/"release/mihomo/config.yaml").read_text())
    with tempfile.TemporaryDirectory(prefix="garasu-v2-isolated-") as location:
        tmp=Path(location)
        (tmp/"rule-providers").mkdir()
        assets=tmp/"http-assets"
        assets.mkdir()
        for name,provider in profile["rule-providers"].items():
            ext=".yaml" if provider["behavior"]=="classical" else ".mrs"
            source_path=(ROOT/"release/clash/providers"/(name+ext)
                         if ext==".yaml" else ROOT/"release/mihomo/.mrs"/(name+ext))
            if not source_path.is_file():
                raise RuntimeError("Missing rule-set asset: "+name)
            shutil.copyfile(source_path,assets/(name+ext))
        requests_seen=Counter()
        def handler(*args,**kwargs):
            class CountingHandler(QuietHandler):
                def do_GET(self):
                    if self.path.rsplit("/",1)[-1] in expected:
                        requests_seen[self.path.rsplit("/",1)[-1]]+=1
                    super().do_GET()
            return CountingHandler(*args,directory=str(assets),**kwargs)
        expected={item.name for item in assets.iterdir()}
        with ConcurrentAssetServer(("127.0.0.1",0),handler) as server:
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            try:
                port=server.server_address[1]
                for name,p in profile["rule-providers"].items():
                    ext=".yaml" if p["behavior"]=="classical" else ".mrs"
                    p["url"]="http://127.0.0.1:"+str(port)+"/"+name+ext
                    p["proxy"]="DIRECT"
                profile["proxies"]=nodes
                group=profile["proxy-groups"][0]
                group["proxies"]=[item["name"] for item in nodes]
                profile["mixed-port"]=freeport()
                profile["external-controller"]="127.0.0.1:"+str(freeport())
                profile["log-level"]="warning"
                profile.pop("tun",None)
                path=tmp/"config.yaml"
                path.write_text(yaml.safe_dump(profile,allow_unicode=True))
                os.chmod(path,0o600)
                validated=subprocess.run([str(core),"-t","-d",str(tmp),"-f",str(path)],
                                         capture_output=True,timeout=20)
                if validated.returncode:
                    print("REAL_PROFILE_SYNTAX=FAIL (details withheld; credential-safe)")
                    return 2
                print("REAL_PROFILE_SYNTAX=PASS")
                with (tmp/"mihomo.log").open("wb") as log:
                    proc=subprocess.Popen([str(core),"-d",str(tmp),"-f",str(path)],
                                          stdout=log,stderr=subprocess.STDOUT)
                    try:
                        for _ in range(350):
                            if proc.poll() is not None:
                                print("ISOLATED_CORE_START=FAIL")
                                return 3
                            if len(requests_seen)>=len(expected):
                                break
                            time.sleep(.1)
                        hits=len(requests_seen)
                        print("COLD_RULESET_FETCH="+str(hits)+"/"+str(len(expected)))
                        if hits!=len(expected):
                            print("COLD_RULESET_MISSING="+",".join(sorted(expected-set(requests_seen))))
                            print("COLD_RULESET_FETCH=INCOMPLETE")
                            return 4
                        # Use HTTPS through the *isolated* localhost proxy only.
                        request=subprocess.run([
                            "curl","--noproxy","","--proxy",
                            "http://127.0.0.1:"+str(profile["mixed-port"]),
                            "--connect-timeout","5","--max-time","14",
                            "-sS","-o","/dev/null","-w","%{http_code}",
                            "https://cp.cloudflare.com/generate_204"
                        ],capture_output=True,timeout=17)
                        if request.returncode:
                            print("REAL_PROXY_TUNNEL=FAIL (outbound unreachable or timed out)")
                            return 5
                        print("REAL_PROXY_TUNNEL="+("PASS" if request.stdout.strip() in (b"204",b"200") else "HTTP_ERROR"))
                        return 0 if request.stdout.strip() in (b"204",b"200") else 6
                    finally:
                        if proc.poll() is None:
                            proc.terminate()
                            try:proc.wait(timeout=3)
                            except subprocess.TimeoutExpired:
                                proc.kill()
                                proc.wait(timeout=3)
            finally:
                server.shutdown()
                thread.join(timeout=3)


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--core",type=Path,required=True)
    ap.add_argument("--source",type=Path,required=True)
    args=ap.parse_args()
    raise SystemExit(smoke(args.core,args.source))
