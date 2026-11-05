#!/usr/bin/env python3
"""Read-only named-node probe for the local Mihomo controller.

Never changes proxy selection, profile, network settings or subscriptions.
Only prints safe aggregate results, never node names, URLs or credentials.
"""
import argparse
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import ProxyHandler, Request, build_opener

PORTS = (9097, 9090)
TEST_URL = "https://www.gstatic.com/generate_204"


def api_get(port, endpoint, secret="", timeout=4):
    request = Request(
        f"http://127.0.0.1:{port}{endpoint}",
        headers={"Accept": "application/json", **({"Authorization": f"Bearer {secret}"} if secret else {})},
    )
    with build_opener(ProxyHandler({})).open(request, timeout=timeout) as response:
        return json.load(response)


def choose_node(data, substring):
    """Return target name privately, plus count, only for actual proxy nodes."""
    proxies = data.get("proxies", {})
    candidates = [name for name, info in proxies.items()
                  if substring.lower() in name.lower()
                  and isinstance(info, dict)
                  and info.get("type", "").lower() not in
                  {"urltest", "selector", "fallback", "loadbalance", "relay", "compatible"}]
    return (candidates[0] if len(candidates) == 1 else None), len(candidates)


def group_summary(data, node):
    group = data.get("proxies", {}).get("Garasu", {})
    return {
        "group_type": group.get("type", "missing"),
        "node_in_group": node in group.get("all", []),
        "node_selected": group.get("now") == node,
        "group_has_fixed_selection": bool(group.get("fixed")),
    }


def diagnose(port, secret, fragment, count, interval):
    data = api_get(port, "/proxies", secret)
    node, matches = choose_node(data, fragment)
    report = {"controller_port": port, "matches": matches, "samples": []}
    if node is None:
        report["status"] = "NOT_FOUND_OR_AMBIGUOUS"
        return report
    report.update(group_summary(data, node))
    for i in range(count):
        start = time.monotonic()
        query = urlencode({"url": TEST_URL, "timeout": 8000, "expected": "204"})
        try:
            answer = api_get(port, f"/proxies/{quote(node, safe='')}/delay?{query}",
                             secret, timeout=10)
            result = {"ok": isinstance(answer.get("delay"), int),
                      "delay_ms": answer.get("delay")}
        except HTTPError as exc:
            result = {"ok": False, "http_error": exc.code}
        except (URLError, OSError, TimeoutError, ValueError, json.JSONDecodeError):
            result = {"ok": False, "error": "NETWORK_OR_CONTROLLER_TIMEOUT"}
        result["elapsed_ms"] = round((time.monotonic() - start) * 1000)
        report["samples"].append(result)
        if i + 1 < count:
            time.sleep(interval)
    report["successes"] = sum(x["ok"] for x in report["samples"])
    report["status"] = "ALL_PASS" if report["successes"] == count else "SOME_FAILED"
    return report


def main():
    p = argparse.ArgumentParser(description="Test one Mihomo node without switching Garasu")
    p.add_argument("--name-contains", required=True, help="Unique substring of node name")
    p.add_argument("--port", type=int, default=0, help="Mihomo local external-controller port")
    p.add_argument("--count", type=int, default=3)
    p.add_argument("--interval", type=float, default=5)
    args = p.parse_args()
    if not 1 <= args.count <= 100 or not 0 <= args.interval <= 120:
        p.error("count must be 1..100 and interval 0..120")
    secret = os.environ.get("GARASU_MIHOMO_API_SECRET", "")
    for port in ((args.port,) if args.port else PORTS):
        try:
            report = diagnose(port, secret, args.name_contains, args.count, args.interval)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return
        except HTTPError as exc:
            if exc.code in (401, 403):
                print(json.dumps({"status": "CONTROLLER_AUTH_REQUIRED", "port": port}))
                return
        except (URLError, OSError, TimeoutError, ValueError, json.JSONDecodeError):
            continue
    print(json.dumps({"status": "CONTROLLER_UNREACHABLE", "ports_checked": [args.port] if args.port else PORTS}))


if __name__ == "__main__":
    main()
