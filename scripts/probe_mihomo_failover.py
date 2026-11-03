#!/usr/bin/env python3
"""Mihomo multi-node automatic failover test using only synthetic localhost nodes.

Starts three injected nodes: first healthy, second healthy, third unreachable.
Kills the first proxy and waits for automatic health-based selection of #2.
This exercises real Mihomo, not real user VPN credentials or ISP connectivity.
"""
import http.client
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import urllib.parse

import yaml

from smoke_cores import prepare_mihomo
from probe_mihomo_runtime import (
    API_PORT, LISTENER_PORT, MockProxy, ThreadedTCPServer, assert_port, local_json
)

TEST_URL = "http://garasu-probe.invalid/generate_204"


def group_health():
    query = ("/group/" + urllib.parse.quote("Garasu Auto", safe="") +
             "/delay?url=" + urllib.parse.quote(TEST_URL, safe="") +
             "&timeout=1000&expected=204")
    return local_json("http://127.0.0.1:" + str(API_PORT) + query, timeout=8)


def groups():
    result = local_json("http://127.0.0.1:" + str(API_PORT) + "/proxies")
    return result["proxies"]


def proxy_http_body():
    try:
        con = http.client.HTTPConnection("127.0.0.1", LISTENER_PORT, timeout=3)
        try:
            con.request("GET", "http://garasu-probe.invalid/proxy-path",
                        headers={"Host": "garasu-probe.invalid", "Connection": "close"})
            response = con.getresponse()
            return response.status, response.read()
        finally:
            con.close()
    except (OSError, TimeoutError, http.client.HTTPException):
        return 0, b""


def await_route(expected, max_wait=14):
    end = time.monotonic() + max_wait
    last = None
    while time.monotonic() < end:
        status = groups()
        now = status["Garasu Auto"].get("now")
        code, body = proxy_http_body()
        last = (now, code, body[:80])
        if now == expected and code == 200 and body == expected.encode():
            return
        time.sleep(0.6)
    raise AssertionError("Failover did not converge: " + repr(last))


def run():
    with tempfile.TemporaryDirectory(prefix="garasu-failover-") as tmp:
        out = Path(tmp)
        fixture = prepare_mihomo(
            "clients/canary/mihomo-remnawave.yaml", out, node_count=3
        )
        doc = yaml.safe_load(fixture.read_text(encoding="utf-8"))
        nodes = [p["name"] for p in doc["proxies"]]
        if len(set(nodes)) != 3:
            raise AssertionError("Unexpected injected node count")
        doc["proxy-groups"][1]["url"] = TEST_URL
        doc["proxy-groups"][1]["interval"] = 2
        doc["proxy-groups"][1]["tolerance"] = 25
        doc["proxy-groups"][1]["timeout"] = 1000
        doc["external-controller"] = "127.0.0.1:" + str(API_PORT)
        config = out / "failover.yaml"
        config.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
                          encoding="utf-8")

        # One intentionally unreachable node is a negative test.
        with (ThreadedTCPServer(("127.0.0.1", 1080), MockProxy) as primary,
              ThreadedTCPServer(("127.0.0.1", 1081), MockProxy) as standby):
            primary.health_delay = 0.04
            standby.health_delay = 0.14
            primary.ok_body = nodes[0].encode()
            standby.ok_body = nodes[1].encode()
            for server in (primary, standby):
                server.seen = []
                threading.Thread(target=server.serve_forever, daemon=True).start()
            proc = subprocess.Popen(
                ["docker", "run", "--rm", "--network", "host",
                 "--name", "garasu-mihomo-ci-failover",
                 "-v", str(out) + ":" + str(out),
                 "metacubex/mihomo:v1.19.32",
                 "-f", str(config), "-d", str(out)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            try:
                for _ in range(50):
                    if proc.poll() is not None:
                        raise AssertionError("Mihomo exited before opening listener")
                    try:
                        assert_port(LISTENER_PORT)
                        if len(groups()["Garasu Auto"].get("all", [])) == 3:
                            break
                    except (OSError, ValueError, KeyError):
                        pass
                    time.sleep(.2)
                else:
                    raise AssertionError("3-node auto-group did not appear")

                # Initial probe is only to establish test baseline. After
                # shutdown no manual API healthcheck is made: switch is automatic.
                observed = group_health()
                if nodes[0] not in observed or nodes[1] not in observed:
                    raise AssertionError("Healthy injected nodes not measured")
                await_route(nodes[0], max_wait=10)
                print("PASS: 3 nodes injected, primary selected automatically", flush=True)

                primary.shutdown()
                primary.server_close()
                await_route(nodes[1], max_wait=16)
                print("PASS: lost primary -> automatic standby failover", flush=True)
                status = groups()
                if status["Garasu"]["now"] != "Garasu Auto":
                    raise AssertionError("Garasu selected a non-auto group")
                if "DIRECT" in status["Garasu Auto"]["all"]:
                    raise AssertionError("Automatic fallback silently allows DIRECT")
            finally:
                proc.terminate()
                try:
                    output, _ = proc.communicate(timeout=9)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    output, _ = proc.communicate(timeout=5)
                print("Mihomo failover diagnostics (synthetic only):",
                      output[-2200:], flush=True)
                standby.shutdown()


if __name__ == "__main__":
    run()
