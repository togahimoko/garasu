#!/usr/bin/env python3
"""Read-only Remnawave subscription delivery diagnostic.

Private links are read only from GARASU_SUBSCRIPTION_URL. No URL, query
string, response body, node address, UUID or error message is printed.
This checks HTTP reachability and response *shape*, not VPN tunnel speed.
"""
import argparse
import base64
import binascii
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

AGENTS = {
    "mihomo": "mihomo/1.19.32",
    "clash": "clash/1.0",
    "stash": "stash/2.0",
    "singbox": "singbox/1.14.2",
    "happ": "happ/1.0",
    "incy": "incy/1.0",
    "browser": "browser/1.0",
    "preview_incy": "garasu-test-incy",
    "preview_happ": "garasu-test-happ",
    "preview_mihomo": "garasu-test-mihomo",
    "preview_stash": "garasu-test-stash",
    "preview_singbox": "garasu-test-singbox",
    "preview_xray": "garasu-test-xray",
    "xray_json": "garasu-xray-json",
}
DEFAULT_AGENTS = ("mihomo", "clash", "stash", "singbox", "happ", "incy", "browser")
MAX_BYTES = 65536


class RejectRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        # Never forward a bearer-link query string across a redirect.
        return None


def _mime(headers):
    original = headers.get("Content-Type", "")
    value = original.split(";", 1)[0].lower().strip()
    return value if re.fullmatch(r"[a-z0-9.+/-]{1,80}", value) else "unknown"


def _format(body, mime):
    sample = body.lstrip()
    if mime == "text/html" or sample[:1] == b"<":
        return "html"
    if sample[:1] in (b"{", b"["):
        return "json"
    if sample.startswith((b"proxies:", b"proxy-groups:", b"mixed-port:",
                          b"port:", b"rules:")):
        return "yaml"
    compact = b"".join(sample.split())
    if compact and len(compact) % 4 == 0 and len(compact) < MAX_BYTES + 1:
        try:
            decoded = base64.b64decode(compact, validate=True)
            if decoded:
                return "base64"
        except (binascii.Error, ValueError):
            pass
    return "unknown"


def _opener(transport):
    if transport == "direct":
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({}), RejectRedirect)
    proxy = os.environ.get("GARASU_HTTP_PROXY", "")
    parsed = urllib.parse.urlsplit(proxy)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("GARASU_HTTP_PROXY must be an HTTP(S) proxy URL")
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({"https": proxy}), RejectRedirect)


def request_once(url, client, transport, *, opener=None, timeout=8):
    if client not in AGENTS:
        raise ValueError("Unsupported client")
    if transport not in ("direct", "proxy"):
        raise ValueError("Unsupported transport")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username:
        raise ValueError("Subscription URL must be HTTPS")
    req = urllib.request.Request(
        url, headers={"User-Agent": AGENTS[client],
                      "Accept": "text/html" if client == "browser"
                      else "*/*"}, method="GET")
    opener = opener if opener is not None else _opener(transport)
    result = {
        "client": client,
        "transport": transport,
        "status": None,
        "mime": "unknown",
        "format": "unknown",
        "read_bytes": 0,
        "truncated": False,
        "error": None,
    }
    try:
        with opener.open(req, timeout=timeout) as response:
            result["status"] = response.status
            result["mime"] = _mime(response.headers)
            data = response.read(MAX_BYTES + 1)
            result["truncated"] = len(data) > MAX_BYTES
            data = data[:MAX_BYTES]
            result["read_bytes"] = len(data)
            result["format"] = _format(data, result["mime"])
    except urllib.error.HTTPError as exc:
        result["status"] = exc.code
        result["error"] = "HTTPError"
        # Never expose Location or server response body.
    except (OSError, ValueError, TimeoutError) as exc:
        result["error"] = type(exc).__name__
        # Never include exc: its message may contain the private URL.
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Read-only status probe for private Remnawave subscriptions.")
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--clients", nargs="+", choices=list(AGENTS),
                        default=list(DEFAULT_AGENTS))
    args = parser.parse_args()
    url = os.environ.get("GARASU_SUBSCRIPTION_URL", "")
    if not url:
        parser.error("Set GARASU_SUBSCRIPTION_URL privately; never paste it into reports")
    if not 1 <= args.timeout <= 30:
        parser.error("timeout must be between 1 and 30 seconds")
    transports = ["direct"] + (["proxy"] if os.environ.get("GARASU_HTTP_PROXY") else [])
    reports = [request_once(url, client, transport, timeout=args.timeout)
               for transport in transports for client in args.clients]
    print(json.dumps({"diagnostics_only": True, "results": reports},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
