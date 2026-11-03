#!/usr/bin/env python3
"""Guard the public Garasu distribution from accidentally exposing VPN nodes.

Checks only public client assets and install metadata, not private subscription
responses. Findings intentionally exclude secret values from CI output.
This is defense-in-depth, NOT a replacement for GitHub Secret Scanning.
"""
import base64
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit, parse_qsl

ROOT = Path(__file__).resolve().parents[1]
SECRET_URI = re.compile(r"\b(?:vless|vmess|trojan|ss|hysteria2|hy2)://", re.I)
KEY_PEM = re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")
AUTH = re.compile(r"\bAuthorization\s*:\s*(?:Bearer|Basic)\s+\S+", re.I)
SUBSCRIPTION = re.compile(
    r"https?://[^\s\"'<>]+/(?:sub|subscribe|subscription|api/v1/client/subscribe)/"
    r"[A-Za-z0-9_-]{12,}", re.I,
)
URL = re.compile(r"https?://[^\s\"'<>]+", re.I)
SENSITIVE_QUERY = {"token", "access_token", "apikey", "api_key", "auth", "password", "secret"}
FORBIDDEN_HAPP_FIELDS = {
    "server", "servers", "address", "privatekey", "uuid", "password",
    "token", "apikey", "api_key", "inbounds", "outbounds", "proxies",
}


def find_exposures(path, content):
    """Return safe finding labels only; never echo secret material in logs."""
    if not isinstance(path, str) or not isinstance(content, str):
        raise ValueError("Expected text file and path")
    findings = set()
    if SECRET_URI.search(content):
        findings.add("embedded VPN node URI")
    if KEY_PEM.search(content):
        findings.add("private key")
    if AUTH.search(content):
        findings.add("HTTP Authorization credential")
    if SUBSCRIPTION.search(content):
        findings.add("personal subscription URL")
    for match in URL.finditer(content):
        url = match.group(0).rstrip("),.;]")
        query = urlsplit(url).query
        for key, value in parse_qsl(query):
            if key.lower() in SENSITIVE_QUERY and value and len(value) >= 8:
                findings.add("credential in URL query")
    if path.startswith("clients/"):
        if path.endswith((".yaml", ".yml")):
            if re.search(r"(?m)^\s*server\s*:\s*\S+", content):
                findings.add("static proxy server in YAML template")
        if path.endswith(".json"):
            try:
                payload = json.loads(content)
                if isinstance(payload, dict):
                    # DNS resolvers and loopback inbound listeners are not
                    # personal VPN exit nodes. Only inspect published outbounds.
                    node_lists = [payload.get(key, []) for key in
                                  ("outbounds", "proxies", "nodes")]
                    if any(_has_sensitive_node_config(nodes) for nodes in node_lists):
                        findings.add("static proxy server in JSON template")
            except json.JSONDecodeError:
                findings.add("malformed JSON client template")
        if path.endswith(".conf") and re.search(
            r"(?mi)^\s*\[Proxy\]\s*$", content
        ):
            findings.add("embedded Shadowrocket proxy section")
    return sorted(findings)


def _has_sensitive_node_config(node):
    """Detect actual endpoint data, not ordinary rule-provider URLs or DNS."""
    if isinstance(node, dict):
        typ = str(node.get("type", node.get("protocol", ""))).lower()
        if typ in {"vless", "vmess", "trojan", "shadowsocks", "socks", "http", "hysteria2"}:
            if node.get("server") or node.get("address"):
                return True
        if node.get("server") and any(key in node for key in
                                      ("server_port", "port", "uuid", "password")):
            return True
        return any(_has_sensitive_node_config(v) for v in node.values())
    return isinstance(node, list) and any(_has_sensitive_node_config(v) for v in node)


def check_happ_link(value):
    if not isinstance(value, str) or not value.startswith("happ://routing/onadd/"):
        return ["invalid Happ import URL"]
    encoded = value.split("/onadd/", 1)[1]
    try:
        profile = json.loads(base64.b64decode(encoded, validate=True))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return ["malformed Happ payload"]
    findings = set()
    def inspect(item):
        if isinstance(item, dict):
            for key, val in item.items():
                if key.lower() in FORBIDDEN_HAPP_FIELDS:
                    findings.add("embedded sensitive Happ profile field")
                inspect(val)
        elif isinstance(item, list):
            for val in item:
                inspect(val)
        elif isinstance(item, str):
            for result in find_exposures("embedded/happ.json", item):
                findings.add(result)
    inspect(profile)
    return sorted(findings)


def scan_release(root=ROOT):
    """Scan only artifacts distributed publicly (not test fixtures)."""
    root = Path(root)
    items = list((root / "clients").rglob("*")) if (root / "clients").exists() else []
    items += list((root / "install").rglob("*")) if (root / "install").exists() else []
    findings = []
    for file in sorted(items):
        if not file.is_file():
            continue
        if file.stat().st_size > 1_000_000:
            findings.append(file.relative_to(root).as_posix() + ": oversized public asset")
            continue
        path = file.relative_to(root).as_posix()
        try:
            content = file.read_text(encoding="utf-8")
        except UnicodeError:
            findings.append(path + ": unexpected binary public asset")
            continue
        for label in find_exposures(path, content):
            findings.append(path + ": " + label)
        if file.name == "links.json":
            try:
                links = json.loads(content)
            except json.JSONDecodeError:
                findings.append(path + ": malformed install links")
                continue
            if "happ" in links:
                for label in check_happ_link(links["happ"]):
                    findings.append(path + ": " + label)
    return findings


def main():
    results = scan_release()
    if results:
        for item in results:
            print("FAIL", item)
        raise SystemExit(1)
    print("PASS: Public Garasu client assets contain no detected node credentials or personal subscriptions")


if __name__ == "__main__":
    main()
