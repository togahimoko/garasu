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
    "browser": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36",
    "xray": "v2rayN/7.0",
}
DEFAULT_AGENTS = ("mihomo", "clash", "stash", "singbox", "happ", "incy", "browser")
MAX_BYTES = 2_000_000  # Bounded diagnostics; large rule sets must not be inline.


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
    while sample.startswith(b"#"):
        sample = sample.partition(b"\n")[2].lstrip()
    if sample[:1] in (b"{", b"["):
        return "json"
    if sample.startswith((b"proxies:", b"proxy-groups:", b"mixed-port:",
                          b"port:", b"rules:", b"mode:", b"dns:",
                          b"rule-providers:")):
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



def _yaml_counts(body):
    """Count YAML sections without exposing subscription nodes or rule names.

    Remnawave emits normal two-space-indented YAML; no third-party parser or
    user-provided scalar evaluation is required. Truncated bodies are not
    accepted by --require-clash-ready.
    """
    counts = {"proxies": 0, "proxy_providers": 0,
              "proxy_groups": 0, "rule_providers": 0, "rules": 0}
    section = None
    for line in body.decode("utf-8", errors="replace").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        header = re.match(r"^([a-z][a-z0-9-]*):", line)
        if header:
            section = header.group(1)
            continue
        if section in ("proxies", "proxy-groups", "rules"):
            key = {"proxies": "proxies", "proxy-groups": "proxy_groups",
                   "rules": "rules"}[section]
            if re.match(r"^  -\s+", line):
                counts[key] += 1
        elif section in ("proxy-providers", "rule-providers"):
            key = "proxy_providers" if section == "proxy-providers" else "rule_providers"
            if re.match(r"^  [A-Za-z0-9_-]+:\s*", line):
                counts[key] += 1
    return counts


EXPECTED_GARASU_PROVIDERS = frozenset((
    "rkn-domains", "youtube", "discord", "ai", "crypto", "proxy",
    "ads", "rkn-ips", "proxy-ips", "ru-ips",
))


def _yaml_checks(body):
    """Only non-sensitive booleans leave this function; never return node data."""
    providers, groups, rule_lines, blocks = set(), set(), [], []
    provider_types = {}
    provider_urls = {}
    provider_formats = {}
    provider_intervals = {}
    section, fields = None, None
    current_provider = None
    for line in body.decode("utf-8", errors="replace").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        root = re.match(r"^([a-z][a-z0-9-]*):", line)
        if root:
            section = root.group(1)
            if section != "proxies" and fields is not None:
                blocks.append(fields)
                fields = None
            continue
        if section == "proxies":
            if re.match(r"^  -\s+", line):
                if fields is not None:
                    blocks.append(fields)
                fields = set()
                if re.match(r"^  -\s+name\s*:", line):
                    fields.add("name")
            elif fields is not None:
                key = re.match(r"^    ([a-z][a-z0-9-]*):", line)
                if key:
                    fields.add(key.group(1))
        elif section in ("proxy-groups", "rule-providers"):
            if section == "proxy-groups":
                name = re.match(r"^  -\s+name:\s*(.+)\s*$", line)
                if name:
                    groups.add(name.group(1).strip().strip("'\""))
            else:
                name = re.match(r"^  ([a-z][a-z0-9-]*):", line)
                if name:
                    providers.add(name.group(1))
                    current_provider = name.group(1)
                else:
                    kind = re.match(r"^    type:\s*(\S+)", line)
                    url = re.match(r"^    url:\s*(\S+)", line)
                    fmt = re.match(r"^    format:\s*(\S+)", line)
                    interval = re.match(r"^    interval:\s*(\d+)", line)
                    if kind and current_provider in providers:
                        provider_types[current_provider] = kind.group(1)
                    if url and current_provider in providers:
                        provider_urls[current_provider] = url.group(1)
                    if fmt and current_provider in providers:
                        provider_formats[current_provider] = fmt.group(1)
                    if interval and current_provider in providers:
                        provider_intervals[current_provider] = int(interval.group(1))
        elif section == "rules" and re.match(r"^  -\s+", line):
            rule_lines.append(line.split("- ", 1)[1].strip().strip("'\""))
    if fields is not None:
        blocks.append(fields)
    required = {"name", "type", "server", "port"}
    def pos(prefix):
        return next((i for i, rule in enumerate(rule_lines)
                     if rule.startswith(prefix)), -1)
    rkn_domain = pos("RULE-SET,rkn-domains,Garasu")
    rkn_ip = pos("RULE-SET,rkn-ips,Garasu")
    ru = pos("DOMAIN-SUFFIX,ru,DIRECT")
    final = pos("MATCH,Garasu")
    return {
        "personal_node_shapes_valid": len(blocks) >= 2 and all(required <= b for b in blocks),
        "garasu_provider_set_valid": providers == EXPECTED_GARASU_PROVIDERS,
        "garasu_providers_remote": (
            providers == EXPECTED_GARASU_PROVIDERS
            and all(provider_types.get(name) == "http"
                    and provider_urls.get(name) ==
                    "https://raw.githubusercontent.com/togahimoko/garasu/main/release/mihomo/.mrs/"
                    + name + ".mrs"
                    and provider_formats.get(name) == "mrs"
                    and provider_intervals.get(name) == 21600 for name in providers)
        ),
        "garasu_route_order_valid": (
            groups == {"Garasu"}
            and 0 <= rkn_domain < ru and 0 <= rkn_ip < ru
            and final == len(rule_lines) - 1
            and pos("RULE-SET,ads,REJECT") >= 0
            and pos("RULE-SET,ru-ips,DIRECT") >= 0
        ),
    }


def _clash_ready(report):
    counts = report.get("yaml_counts") or {}
    return (report["client"] == "clash" and report["status"] == 200
            and report["format"] == "yaml" and not report["truncated"]
            and counts.get("proxies", 0) >= 1
            and counts.get("proxy_groups", 0) == 1
            and counts.get("rule_providers", 0) == len(EXPECTED_GARASU_PROVIDERS)
            and counts.get("rules", 0) >= 15
            and all(report.get("yaml_checks", {}).values())
            and len(report.get("yaml_checks", {})) == 4)


def _opener(transport):
    if transport == "direct":
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({}), RejectRedirect)
    proxy = os.environ.get("GARASU_HTTP_PROXY") or urllib.request.getproxies().get("https", "")
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
        "has_routing_header": False,
        "has_autorouting_header": False,
        "yaml_counts": None,
        "yaml_checks": None,
        "error": None,
    }
    try:
        with opener.open(req, timeout=timeout) as response:
            result["status"] = response.status
            result["mime"] = _mime(response.headers)
            result["has_routing_header"] = bool(response.headers.get("routing"))
            result["has_autorouting_header"] = bool(response.headers.get("autorouting"))
            data = response.read(MAX_BYTES + 1)
            result["truncated"] = len(data) > MAX_BYTES
            data = data[:MAX_BYTES]
            result["read_bytes"] = len(data)
            result["format"] = _format(data, result["mime"])
            if result["format"] == "yaml":
                result["yaml_counts"] = _yaml_counts(data)
                result["yaml_checks"] = _yaml_checks(data)
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
    parser.add_argument("--require-clash-ready", action="store_true",
                        help="exit 2 unless clash/1.0 returns two nodes and all ten offline Garasu providers")
    args = parser.parse_args()
    url = os.environ.get("GARASU_SUBSCRIPTION_URL", "")
    if not url:
        parser.error("Set GARASU_SUBSCRIPTION_URL privately; never paste it into reports")
    if not 1 <= args.timeout <= 30:
        parser.error("timeout must be between 1 and 30 seconds")
    transports = ["direct"] + (["proxy"] if (os.environ.get("GARASU_HTTP_PROXY")
                                            or urllib.request.getproxies().get("https")) else [])
    reports = [request_once(url, client, transport, timeout=args.timeout)
               for transport in transports for client in args.clients]
    print(json.dumps({"diagnostics_only": True, "results": reports},
                     ensure_ascii=False, indent=2))
    if args.require_clash_ready and not any(_clash_ready(r) for r in reports):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
