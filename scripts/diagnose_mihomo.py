#!/usr/bin/env python3
"""Read-only local Mihomo diagnosis; never prints node names, URLs or credentials.

Reads the core's localhost controller and optionally checks real HTTPS traffic
through the local HTTP proxy. Does NOT modify selection, clear caches, download
subscriptions, or contact Remnawave. No personal VPN secrets are sent anywhere.
"""
import argparse
import http.client
import json
import os
import socket
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, ProxyHandler, build_opener

API_PORTS = (9097, 9090)
PROXY_PORTS = (7897, 7890, 17897)


def analyze(config, groups):
    """Safe aggregate report; never returns any individual proxy identifier."""
    proxies = groups.get("proxies", {}) if isinstance(groups, dict) else {}
    garasu = proxies.get("Garasu", {})
    auto = proxies.get("Garasu Auto", {})
    issues = []
    port = config.get("mixed-port", 0)
    if not isinstance(port, int) or port < 1 or port > 65535:
        issues.append("NO_MIXED_PORT")
        port = None
    if not garasu:
        issues.append("GARASU_GROUP_MISSING")
    elif garasu.get("now", "") == "DIRECT":
        issues.append("GARASU_DIRECT_SELECTED")
    if not auto:
        issues.append("AUTO_GROUP_MISSING")
    elif not auto.get("all"):
        issues.append("AUTO_GROUP_EMPTY")
    if config.get("mode", "").lower() != "rule":
        issues.append("NOT_RULE_MODE")
    tun = config.get("tun") if isinstance(config.get("tun"), dict) else {}
    return {
        "mode": str(config.get("mode", "unknown")).lower(),
        "mixed_port": port,
        "tun_enabled": bool(tun.get("enable", False)),
        "garasu_present": bool(garasu),
        "garasu_auto_selected": garasu.get("now") == "Garasu Auto",
        "auto_member_count": len(auto.get("all", [])) if isinstance(auto.get("all", []), list) else 0,
        "issues": issues,
    }


def read_json_local(port, path, secret=""):
    if not isinstance(port, int) or port < 1 or port > 65535:
        raise ValueError("Invalid port")
    url = "http://127.0.0.1:" + str(port) + path
    headers = {"Accept": "application/json", "User-Agent": "Garasu-Local-Diagnostics"}
    if secret:
        headers["Authorization"] = "Bearer " + secret
    request = Request(url, headers=headers)
    opener = build_opener(ProxyHandler({}))
    with opener.open(request, timeout=2) as response:
        data = response.read(1024 * 1024)
    return json.loads(data)


def probe_socket(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.6):
            return True
    except OSError:
        return False


def probe_https(mixed_port, host="www.gstatic.com", path="/generate_204"):
    """Check actual HTTPS CONNECT over the local HTTP proxy, no TUN required."""
    start = time.monotonic()
    context = ssl.create_default_context()
    con = http.client.HTTPSConnection("127.0.0.1", mixed_port, timeout=9,
                                       context=context)
    con.set_tunnel(host, 443)
    try:
        con.request("HEAD", path, headers={"Host": host})
        response = con.getresponse()
        response.read()
        return {"status": "ok" if 200 <= response.status < 400 else "http_error",
                "http_status": response.status,
                "elapsed_ms": round((time.monotonic() - start) * 1000)}
    except (OSError, TimeoutError, ssl.SSLError, http.client.HTTPException):
        return {"status": "connection_failed"}
    finally:
        con.close()


def main():
    parser = argparse.ArgumentParser(description="Privacy-safe read-only Mihomo core health check")
    parser.add_argument("--controller-port", type=int, default=0,
                        help="Optional local controller port, normally 9097 / 9090")
    parser.add_argument("--mixed-port", type=int, default=0,
                        help="Optional expected local mixed proxy port")
    parser.add_argument("--probe-net", action="store_true",
                        help="Send a HEAD request through the proxy to www.gstatic.com")
    args = parser.parse_args()
    secret = os.environ.get("GARASU_MIHOMO_API_SECRET", "")
    controller = None
    config = None
    proxies = None
    auth_required = False
    for port in ((args.controller_port,) if args.controller_port else API_PORTS):
        try:
            conf = read_json_local(port, "/configs", secret)
            found = read_json_local(port, "/proxies", secret)
            if isinstance(conf, dict) and isinstance(found, dict):
                controller, config, proxies = port, conf, found
                break
        except HTTPError as exc:
            if exc.code in (401, 403):
                auth_required = True
        except (OSError, URLError, ValueError, json.JSONDecodeError):
            pass
    report = {
        "controller_available": controller is not None,
        "controller_auth_required": auth_required and controller is None,
        "local_ports": {str(port): probe_socket(port) for port in PROXY_PORTS},
    }
    if config is not None:
        report.update(analyze(config, proxies))
    else:
        report["issues"] = ["CONTROLLER_NOT_ACCESSIBLE"]
        report["mixed_port"] = None
    port = args.mixed_port or report.get("mixed_port") or 0
    if port:
        report["chosen_proxy_port"] = port
        report["listener_open"] = probe_socket(port)
        if not report["listener_open"]:
            report["issues"].append("LOCAL_PROXY_NOT_LISTENING")
        if args.probe_net and report["listener_open"]:
            report["https_via_proxy"] = probe_https(port)
    # Only safe, aggregate statistics leave the process. Individual node names,
    # addresses, private subscription links and API secrets are never printed.
    print("SAFE MIHOMO REPORT")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
