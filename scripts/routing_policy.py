"""Canonical route oracle used to check Garasu client adapters.

``categories`` contains sets named ``lan``, ``blocked``, ``ads``, ``direct``
and ``ru``. Domain entries are exact names unless prefixed with ``+.`` or
``.`` for suffix matching. IP entries are addresses or CIDRs. ``direct`` is
reserved for individually reviewed exceptions, including foreign ones.

This oracle classifies a domain and an IP independently. A caller deciding a
connection must check a resolved blocked IP before using a domain DIRECT
decision. It must not treat a public hostname as LAN merely because DNS
returned a private address. A valid source snapshot is a prerequisite for
enabling broad RU fallback in deployed profiles; this pure oracle assumes
its caller has already enforced that gate.
"""

import ipaddress
import re


_LAN_NETWORKS = tuple(ipaddress.ip_network(value) for value in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
    "127.0.0.0/8", "169.254.0.0/16", "::1/128",
    "fc00::/7", "fe80::/10",
))
_LAN_SUFFIXES = ("localhost", "local", "lan", "home.arpa")
_RU_SUFFIXES = ("ru", "su", "xn--p1ai")
_BLOCKED_DATASETS = {
    "blocked_domains": "refilter-domain-full",
    "blocked_ips": "refilter-ip-full",
}


def _domain_name(value: str) -> str:
    name = value.rstrip(".").lower()
    if not name or any(not label for label in name.split(".")):
        raise ValueError("Invalid domain name")
    try:
        return name.encode("idna").decode("ascii")
    except UnicodeError as error:
        raise ValueError("Invalid domain name") from error


def _domain_matches(name: str, entries: set[str]) -> bool:
    for entry in entries:
        suffix = entry.startswith(("+.", "."))
        target = _domain_name(entry.lstrip("+.") if suffix else entry)
        if name == target or (suffix and name.endswith("." + target)):
            return True
    return False


def _ip_matches(address: ipaddress.IPv4Address | ipaddress.IPv6Address,
                entries: set[str]) -> bool:
    return any(address in ipaddress.ip_network(entry, strict=False) for entry in entries)


def _has_suffix(name: str, suffixes: tuple[str, ...]) -> bool:
    return any(name == suffix or name.endswith("." + suffix) for suffix in suffixes)


def classify_domain(domain: str, categories: dict[str, set[str]]) -> str:
    """Return DIRECT, PROXY or REJECT under the ordered domain policy."""
    name = _domain_name(domain)
    if _has_suffix(name, _LAN_SUFFIXES) or "." not in name or _domain_matches(name, categories.get("lan", set())):
        return "DIRECT"
    if _domain_matches(name, categories.get("blocked", set())):
        return "PROXY"
    if _domain_matches(name, categories.get("ads", set())):
        return "REJECT"
    if _domain_matches(name, categories.get("direct", set())):
        return "DIRECT"
    if _domain_matches(name, categories.get("ru", set())) or _has_suffix(name, _RU_SUFFIXES):
        return "DIRECT"
    return "PROXY"


def classify_ip(address: str, categories: dict[str, set[str]]) -> str:
    """Return DIRECT, PROXY or REJECT under the ordered IP policy."""
    parsed = ipaddress.ip_address(address)
    if any(parsed in network for network in _LAN_NETWORKS) or _ip_matches(parsed, categories.get("lan", set())):
        return "DIRECT"
    if _ip_matches(parsed, categories.get("blocked", set())):
        return "PROXY"
    if _ip_matches(parsed, categories.get("ads", set())):
        return "REJECT"
    if _ip_matches(parsed, categories.get("direct", set())):
        return "DIRECT"
    if _ip_matches(parsed, categories.get("ru", set())):
        return "DIRECT"
    return "PROXY"


def validate_source_metadata(metadata: dict[str, dict[str, object]]) -> None:
    """Require pinned, complete blocked inputs before broad RU bypass.

    Validating metadata does not validate the downloaded bytes or establish
    current reachability. The builder must verify each digest and input size.
    """
    revisions = set()
    for key, dataset in _BLOCKED_DATASETS.items():
        record = metadata.get(key)
        if not isinstance(record, dict) or record.get("dataset") != dataset:
            raise ValueError("Missing complete blocked source: " + key)
        url = record.get("url")
        revision = record.get("revision")
        sha256 = record.get("sha256")
        entries = record.get("entries")
        if (not isinstance(revision, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", revision)
                or not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", sha256)
                or type(entries) is not int or entries <= 0):
            raise ValueError("Invalid blocked source metadata: " + key)
        if not isinstance(url, str):
            raise ValueError("Invalid blocked source URL: " + key)
        expected_url = ("https://raw.githubusercontent.com/DigneZzZ/routing/"
                        + revision + "/release/" + dataset + ".list")
        if url != expected_url:
            raise ValueError("Blocked source URL is not pinned: " + key)
        revisions.add(revision.lower())
    if len(revisions) != 1:
        raise ValueError("Blocked sources must use one immutable revision")
