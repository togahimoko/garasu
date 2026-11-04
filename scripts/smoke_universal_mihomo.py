#!/usr/bin/env python3
"""Offline end-to-end routing smoke: direct, selected proxy and ad rejection.

Uses an isolated Mihomo core and locally simulated HTTP/SOCKS5 servers.
No VPN credentials, Remote DNS, external service calls or production changes.
"""
from __future__ import annotations

import argparse
import http.server
from pathlib import Path
import select
import socket
import socketserver
import subprocess
import tempfile
import threading
import time

import yaml

from scripts.sync_universal_routing import offline_mihomo_fixture

ROOT = Path(__file__).resolve().parents[1]


def exact(sock: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        fragment = sock.recv(size - len(data))
        if not fragment:
            raise ConnectionError("Incomplete SOCKS handshake")
        data.extend(fragment)
    return bytes(data)


class MockHTTP(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"GARASU_DIRECT_OR_PROXY_OK")

    def log_message(self, *args):
        pass


class MockSocks(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(4)
        try:
            if exact(self.request, 1) != b"\x05":
                return
            methods = exact(self.request, 1)[0]
            exact(self.request, methods)
            self.request.sendall(b"\x05\x00")
            header = exact(self.request, 4)
            if header[:3] != b"\x05\x01\x00":
                return
            if header[3] == 1:
                name = socket.inet_ntoa(exact(self.request, 4))
            elif header[3] == 3:
                size = exact(self.request, 1)[0]
                name = exact(self.request, size).decode("ascii")
            elif header[3] == 4:
                name = socket.inet_ntop(socket.AF_INET6, exact(self.request, 16))
            else:
                return
            destination_port = int.from_bytes(exact(self.request, 2), "big")
            self.server.requests.append((name, destination_port))
            # All test traffic goes to the local HTTP sentinel only.
            upstream = socket.create_connection(("127.0.0.1", self.server.mock_http_port),
                                                timeout=4)
            try:
                self.request.sendall(b"\x05\x00\x00\x01\x7f\x00\x00\x01\x00\x00")
                upstream.settimeout(4)
                sockets = [self.request, upstream]
                while True:
                    ready, _, _ = select.select(sockets, [], [], 4)
                    if not ready:
                        break
                    for s in ready:
                        data = s.recv(16384)
                        if not data:
                            return
                        (upstream if s is self.request else self.request).sendall(data)
            finally:
                upstream.close()
        except (OSError, ConnectionError):
            return


class ThreadingServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def allocate_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    args = parser.parse_args()
    core = args.core.resolve()

    with http.server.ThreadingHTTPServer(("127.0.0.1", 0), MockHTTP) as httpd, \
         ThreadingServer(("127.0.0.1", 0), MockSocks) as sockd, \
         tempfile.TemporaryDirectory(prefix="garasu-single-offline-") as folder:
        sockd.requests = []
        sockd.mock_http_port = httpd.server_port
        threads = []
        for server in (httpd, sockd):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            threads.append(thread)
        root = Path(folder)
        config = yaml.safe_load((ROOT / "release/mihomo/config.yaml").read_text())
        # Only the temporary LOCAL TEST fixture is inline. Actual release
        # uses HTTP providers and needs available/cached GitHub rule sets.
        if any(item.get("type") != "http"
               for item in config["rule-providers"].values()):
            raise AssertionError("Production provider must be remote")
        config = offline_mihomo_fixture(config, ROOT)
        providers = config["rule-providers"]
        if len(providers["ads"]["payload"]) < 1000:
            raise AssertionError("Downloaded rules fixture truncated")
        ads_domain = providers["ads"]["payload"][0].removeprefix("+.")

        config["mixed-port"] = allocate_port()
        config["external-controller"] = "127.0.0.1:" + str(allocate_port())
        config["log-level"] = "info"
        config["dns"]["enhanced-mode"] = "redir-host"
        domains = ("sberbank.ru", "unlisted-garasu-test.net", ads_domain, "003.su")
        config["hosts"] = {host: "127.0.0.1" for host in domains}
        config["proxies"] = [{
            "name": "LOCAL_TEST_PROXY",
            "type": "socks5",
            "server": "127.0.0.1",
            "port": sockd.server_address[1],
        }]
        config["proxy-groups"][0]["proxies"] = ["LOCAL_TEST_PROXY"]
        # Pure domain-routing scenario: remove private-IP rules only in the
        # ephemeral fixture, because all test hosts resolve to loopback.
        config["rules"] = [
            rule for rule in config["rules"]
            if not rule.startswith(("IP-CIDR,", "IP-CIDR6,", "GEOIP,"))
        ]
        path = root / "fixture.yaml"
        path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
        logfile = root / "mihomo.log"
        process = None
        try:
            with logfile.open("w", encoding="utf-8") as output:
                process = subprocess.Popen(
                    [str(core), "-d", str(root), "-f", str(path)],
                    stdout=output, stderr=subprocess.STDOUT,
                )
                time.sleep(.75)
                if process.poll() is not None:
                    raise RuntimeError("Mihomo failed to start")
                outcomes = {}
                for domain in domains:
                    cmd = [
                        "curl", "-4", "--noproxy", "",
                        "--proxy", "http://127.0.0.1:" + str(config["mixed-port"]),
                        "--connect-timeout", "2", "--max-time", "4",
                        "-sS", "-o", "-", "-w", " HTTP=%{http_code}",
                        "http://" + domain + ":" + str(httpd.server_port) + "/",
                    ]
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
                    outcomes[domain] = (res.returncode, res.stdout.strip())
                traces = sockd.requests[:]
            events = logfile.read_text(encoding="utf-8", errors="replace")
            bank_ok = "GARASU_DIRECT_OR_PROXY_OK HTTP=200" in outcomes["sberbank.ru"][1]
            foreign_ok = ("GARASU_DIRECT_OR_PROXY_OK HTTP=200"
                          in outcomes["unlisted-garasu-test.net"][1])
            ad_blocked = "GARASU_DIRECT_OR_PROXY_OK" not in outcomes[ads_domain][1]
            used_proxy = any(port == httpd.server_port for _, port in traces)
            if not (bank_ok and foreign_ok and ad_blocked and used_proxy):
                raise AssertionError("Offline route behavior failed: " + repr(outcomes))
            if "sberbank.ru" not in events or "using DIRECT" not in events:
                raise AssertionError("Bank was not routed directly")
            if "unlisted-garasu-test.net" not in events or "using Garasu" not in events:
                raise AssertionError("Unknown .ru was not routed through Garasu")
            if ads_domain not in events or "using REJECT" not in events:
                raise AssertionError("Ad domain was not rejected")
            routed = [item for item in traces if item[1] == httpd.server_port]
            if len(routed) != 2:
                raise AssertionError("Expected two routed requests; got " + repr(traces))
            if "003.su" not in events:
                raise AssertionError("Blocked Russian domain not seen in native trace")
            print("PASS native offline bank DIRECT / foreign PROXY / blocked RU PROXY / ads REJECT")
            print("PASS offline fixture from verified remote assets, one subscriber group")
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            sockd.shutdown()
            httpd.shutdown()


if __name__ == "__main__":
    main()
