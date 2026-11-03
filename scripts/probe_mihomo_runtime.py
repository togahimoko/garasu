#!/usr/bin/env python3
"""Credential-free Mihomo runtime test: listener -> selected group -> mock node.

No real servers, no personal subscriptions and no public VPN credentials.
Requires Docker with Linux host networking (GitHub Ubuntu runner).
This is an HTTP smoke test, NOT a VLESS/Reality or Russian ISP test.
"""
import argparse
import http.client
import json
from pathlib import Path
import socket
import socketserver
import ssl
import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import urllib.error

import yaml
from smoke_cores import prepare_mihomo

ROOT = Path(__file__).resolve().parents[1]
API_PORT = 19091
MOCK_PORT = 1080
LISTENER_PORT = 7897
TEST_NODE = "garasu-ci-node"


class MockProxy(socketserver.BaseRequestHandler):
    """Minimal CONNECT-capable keep-alive HTTP forwarder for synthetic CI."""
    def handle(self):
        self.request.settimeout(6)
        reader = self.request.makefile("rb")
        try:
            for _ in range(12):
                try:
                    first = reader.readline(16384)
                except (OSError, TimeoutError):
                    return
                if not first:
                    return
                headers = []
                while True:
                    line = reader.readline(16384)
                    if not line or line in (b"\r\n", b"\n"):
                        break
                    headers.append(line)
                request = first.decode("ascii", errors="replace").strip()
                self.server.seen.append(request)
                if request.startswith("CONNECT "):
                    self.request.sendall(
                        b"HTTP/1.1 200 Connection Established\r\n"
                        b"Proxy-Agent: Garasu-Mock\r\n\r\n"
                    )
                    # Mihomo also CONNECT-tunnels HTTP destinations on port 80.
                    # Preserve plaintext handling for latency/HTTP probes; only
                    # perform a TLS handshake for the dedicated HTTPS test.
                    target = request.split(" ", 2)[1]
                    if not target.endswith(":443"):
                        continue
                    # Terminate a genuine TLS session at the synthetic node:
                    # this tests CONNECT + TLS, not only a plaintext GET.
                    with self.server.ssl_context.wrap_socket(
                            self.request, server_side=True) as secure:
                        secure.settimeout(6)
                        tls_reader = secure.makefile("rb")
                        try:
                            tls_request = tls_reader.readline(16384)
                            if not tls_request:
                                return
                            while True:
                                line = tls_reader.readline(16384)
                                if not line or line in (b"\r\n", b"\n"):
                                    break
                            self.server.seen.append(
                                "TLS " + tls_request.decode("ascii", "replace").strip()
                            )
                            body = b"GARASU_TLS_CONNECT_OK"
                            secure.sendall(
                                b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n"
                                b"Content-Length: " + str(len(body)).encode()
                                + b"\r\nConnection: close\r\n\r\n" + body
                            )
                        finally:
                            tls_reader.close()
                    return
                if "/generate_204" in request:
                    # Older Mihomo rounds sub-millisecond loopback checks to
                    # zero and reports 503 even when the proxy succeeded.
                    # Use a measurable delay for this *synthetic* test only.
                    time.sleep(getattr(self.server, "health_delay", 0.040))
                    self.request.sendall(
                        b"HTTP/1.1 204 No Content\r\n"
                        b"Content-Length: 0\r\nConnection: keep-alive\r\n\r\n"
                    )
                else:
                    body = getattr(self.server, "ok_body", b"GARASU_CORE_PROXY_PATH_OK")
                    self.request.sendall(
                        b"HTTP/1.1 200 OK\r\n"
                        b"Content-Type: text/plain\r\nContent-Length: "
                        + str(len(body)).encode()
                        + b"\r\nConnection: keep-alive\r\n\r\n" + body
                    )
                if any(line.lower().startswith(b"connection: close") for line in headers):
                    return
        except (OSError, TimeoutError):
            return
        finally:
            reader.close()

class ThreadedTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def local_json(url, timeout=4):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url, timeout=timeout) as response:
            return json.loads(response.read(300000))
    except urllib.error.HTTPError as err:
        raise AssertionError("Mihomo API status " + str(err.code) + " body="
                             + err.read(1500).decode("utf-8", "replace")) from err


def assert_port(port):
    with socket.create_connection(("127.0.0.1", port), timeout=2):
        return True


def test_runtime(template_path):
    with tempfile.TemporaryDirectory(prefix="garasu-mihomo-runtime-") as folder:
        out = Path(folder)
        fixture = prepare_mihomo(template_path, out)
        doc = yaml.safe_load(fixture.read_text(encoding="utf-8"))
        if doc.get("mixed-port") != LISTENER_PORT:
            raise AssertionError("Canary mixed-port does not match system proxy listener")
        if any(p.get("name") == "DIRECT" for p in doc["proxies"]):
            raise AssertionError("Synthetic subscriber proxy was not isolated")
        if not doc.get("proxy-groups"):
            raise AssertionError("No proxy groups")
        auto = next(g for g in doc["proxy-groups"] if g.get("name") == "Garasu Auto")
        if auto.get("type") != "url-test" or not auto.get("include-all"):
            raise AssertionError("Garasu Auto does not use actual inserted nodes")
        auto["url"] = "http://garasu-probe.invalid/generate_204"
        auto["lazy"] = False
        doc["external-controller"] = "127.0.0.1:" + str(API_PORT)
        config = out / "runtime.yaml"
        config.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
                          encoding="utf-8")
        cert = out / "garasu-probe.crt"
        key = out / "garasu-probe.key"
        subprocess.run(
            ["openssl", "req", "-x509", "-newkey", "rsa:2048",
             "-sha256", "-nodes", "-days", "1", "-keyout", str(key),
             "-out", str(cert), "-subj", "/CN=garasu-probe.invalid",
             "-addext", "subjectAltName=DNS:garasu-probe.invalid"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls_context.load_cert_chain(certfile=str(cert), keyfile=str(key))
        with ThreadedTCPServer(("127.0.0.1", MOCK_PORT), MockProxy) as mock:
            mock.seen = []
            mock.ssl_context = tls_context
            worker = threading.Thread(target=mock.serve_forever, daemon=True)
            worker.start()
            command = [
                "docker", "run", "--rm", "--network", "host", "--name",
                "garasu-mihomo-ci-runtime",
                "-v", str(out) + ":" + str(out),
                "metacubex/mihomo:v1.19.32",
                "-f", str(config), "-d", str(out),
            ]
            proc = subprocess.Popen(command, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True)
            try:
                last = None
                for _ in range(60):
                    if proc.poll() is not None:
                        raise AssertionError("Mihomo exited unexpectedly")
                    try:
                        assert_port(LISTENER_PORT)
                        status = local_json("http://127.0.0.1:" + str(API_PORT) + "/proxies")
                        break
                    except (OSError, ValueError) as exc:
                        last = exc
                        time.sleep(0.25)
                else:
                    raise AssertionError("Mihomo listener/API did not start: " + repr(last))

                nodes = status.get("proxies", {})
                if "Garasu" not in nodes or "Garasu Auto" not in nodes:
                    raise AssertionError("Missing Garasu proxy groups in live core API")
                selected = nodes["Garasu"].get("now")
                if selected != "Garasu Auto":
                    raise AssertionError("Garasu is not selecting Auto: " + repr(selected))
                members = nodes["Garasu Auto"].get("all", [])
                if TEST_NODE not in members:
                    raise AssertionError("Injected node missing from Auto group: " + repr(members))
                print("PASS: runtime proxy groups", selected, "nodes", len(members), flush=True)

                health = "http://garasu-probe.invalid/generate_204"
                url = ("http://127.0.0.1:" + str(API_PORT) + "/proxies/"
                       + urllib.parse.quote(TEST_NODE, safe="") + "/delay?url="
                       + urllib.parse.quote(health, safe="") + "&timeout=4000")
                delay = local_json(url, timeout=9)
                if not isinstance(delay.get("delay"), int):
                    raise AssertionError("No real HTTP health probe delay: " + repr(delay))
                print("PASS: real mock node delay", delay["delay"], "ms", flush=True)

                client = http.client.HTTPConnection("127.0.0.1", LISTENER_PORT, timeout=8)
                try:
                    client.request("GET", "http://garasu-probe.invalid/proxy-path",
                                   headers={"Host": "garasu-probe.invalid"})
                    answer = client.getresponse()
                    body = answer.read()
                finally:
                    client.close()
                if answer.status != 200 or body != b"GARASU_CORE_PROXY_PATH_OK":
                    raise AssertionError("HTTP system proxy did not forward through mock node "
                                         + str(answer.status) + " " + repr(body[:200]))
                if not any("/proxy-path" in x for x in mock.seen):
                    raise AssertionError("Mock outbound node never received request")
                print("PASS: HTTP listener -> Garasu group -> synthetic node", flush=True)

                # Verify actual TLS certificate validation after HTTP CONNECT.
                # A simple 200 CONNECT response is NOT proof TLS functions.
                https_context = ssl.create_default_context(cafile=str(cert))
                https_client = http.client.HTTPSConnection(
                    "127.0.0.1", LISTENER_PORT, timeout=12,
                    context=https_context,
                )
                https_client.set_tunnel("garasu-probe.invalid", 443)
                try:
                    https_client.request("GET", "/tls-probe",
                                         headers={"Host": "garasu-probe.invalid"})
                    https_response = https_client.getresponse()
                    https_body = https_response.read()
                finally:
                    https_client.close()
                if https_response.status != 200 or https_body != b"GARASU_TLS_CONNECT_OK":
                    raise AssertionError("HTTPS CONNECT + TLS path failed")
                if not any(x.startswith("TLS GET /tls-probe") for x in mock.seen):
                    raise AssertionError("The synthetic proxy never observed TLS HTTP request")
                print("PASS: HTTPS CONNECT -> TLS -> synthetic node", flush=True)
            finally:
                proc.terminate()
                try:
                    stdout, _ = proc.communicate(timeout=9)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout, _ = proc.communicate(timeout=5)
                print("Mock outbound requests:", mock.seen[-10:], flush=True)
                print("Mihomo runtime output:", stdout[-5500:], flush=True)
                mock.shutdown()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", default="clients/canary/mihomo-remnawave.yaml")
    args = parser.parse_args()
    test_runtime(args.template)


if __name__ == "__main__":
    main()
