#!/usr/bin/env python3
"""Garasu: deterministic data-quality audit for a validated rules snapshot."""
import argparse
import hashlib
import ipaddress
import json
from pathlib import Path

DOMAINS = ("rkn-domains", "youtube", "discord", "ai", "crypto",
           "proxy", "ads", "games", "direct")
IPS = ("rkn-ips", "proxy-ips", "direct-ips", "ru-ips")
PRIORITY = ("rkn-domains", "rkn-ips", "youtube", "discord", "ai",
            "crypto", "proxy", "proxy-ips", "ads", "games",
            "direct", "direct-ips", "ru-ips")
ACTIONS = {name: ("REJECT" if name == "ads" else "DIRECT" if name in
                  ("games", "direct", "direct-ips", "ru-ips") else "PROXY")
           for name in PRIORITY}


def _entries(blob):
    if not isinstance(blob, bytes):
        raise ValueError("Snapshot values must be bytes")
    return [line.strip().lower()
            for line in blob.decode("utf-8-sig").splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def _domains(blob):
    found = set()
    for item in _entries(blob):
        if not item.startswith("+.") or item.count(".") < 2:
            raise ValueError("Invalid Garasu domain suffix " + item[:100])
        found.add(item[2:])
    return found


def _cidrs(blob):
    result = set()
    for item in _entries(blob):
        try:
            result.add(ipaddress.ip_network(item, strict=False))
        except ValueError as exc:
            raise ValueError("Invalid Garasu CIDR " + item[:100]) from exc
    return result


def _parent_suffix(domain, suffixes):
    parts = domain.split(".")
    for i in range(len(parts) - 1):
        candidate = ".".join(parts[i:])
        if candidate in suffixes:
            return candidate
    return None


def _parent_network(net, candidate_set):
    for prefix in range(net.prefixlen, -1, -1):
        candidate = net if prefix == net.prefixlen else net.supernet(new_prefix=prefix)
        if candidate in candidate_set:
            return candidate
    return None


def analyze(snapshot, records):
    """Compute provenance fingerprint and policy exceptions from one rules snapshot."""
    if not isinstance(snapshot, dict) or not isinstance(records, dict):
        raise ValueError("Invalid Garasu snapshot / manifest")
    paths = {"rules/" + n + ".list" for n in DOMAINS}
    paths.update("rules/" + n + ".cidr" for n in IPS)
    missing = paths.difference(snapshot).union(paths.difference(records))
    if missing:
        raise ValueError("Missing canonical rule sets: " + ", ".join(sorted(missing)))
    for path in sorted(paths):
        content, metadata = snapshot[path], records[path]
        if (len(content) != metadata.get("bytes") or
                hashlib.sha256(content).hexdigest() != metadata.get("sha256")):
            raise ValueError("Manifest integrity mismatch: " + path)
    domains = {name: _domains(snapshot["rules/" + name + ".list"])
               for name in DOMAINS}
    ip_sets = {name: _cidrs(snapshot["rules/" + name + ".cidr"])
               for name in IPS}
    override = []
    for high in DOMAINS:
        if ACTIONS[high] != "PROXY":
            continue
        for low in ("games", "direct"):
            matches = []
            for domain in domains[high]:
                parent = _parent_suffix(domain, domains[low])
                if parent:
                    matches.append({"proxied": domain, "direct_suffix": parent})
            if matches:
                matches.sort(key=lambda item: (item["proxied"], item["direct_suffix"]))
                override.append({"higher_priority": high, "lower_priority": low,
                                 "examples": matches[:10], "count": len(matches)})
    exact = []
    for i, first in enumerate(DOMAINS):
        for second in DOMAINS[i + 1:]:
            if ACTIONS[first] == ACTIONS[second]:
                continue
            matches = sorted(domains[first].intersection(domains[second]))
            if matches:
                exact.append({"first": first, "second": second,
                              "count": len(matches), "examples": matches[:10]})
    ip_override = {}
    for high in ("rkn-ips", "proxy-ips"):
        for low in ("direct-ips", "ru-ips"):
            conflicts = []
            for network in ip_sets[high]:
                parent = _parent_network(network, ip_sets[low])
                if parent:
                    conflicts.append({"proxied": str(network),
                                      "direct_range": str(parent)})
            conflicts.sort(key=lambda item: (item["proxied"], item["direct_range"]))
            ip_override[high + " -> " + low] = {
                "count": len(conflicts), "examples": conflicts[:10]}
    fingerprint = hashlib.sha256("".join(
        path + "\0" + str(meta["sha256"]) + "\n"
        for path, meta in sorted(records.items())
    ).encode("utf-8")).hexdigest()
    return {
        "schema_version": 1,
        "product": "Garasu MAX",
        "snapshot_sha256": fingerprint,
        "manifest_asset_count": len(records),
        "domain_counts": {n: len(domains[n]) for n in DOMAINS},
        "ip_counts": {n: {"total": len(ip_sets[n]),
                          "ipv4": sum(net.version == 4 for net in ip_sets[n]),
                          "ipv6": sum(net.version == 6 for net in ip_sets[n])}
                      for n in IPS},
        "policy_order": list(PRIORITY),
        "policy_overrides": override,
        "exact_policy_conflicts": exact,
        "ip_overrides": ip_override,
    }


def to_json(report):
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def to_markdown(report):
    out = [
        "# Garasu MAX — качество наборов правил",
        "",
        "Отчёт формируется из одной проверенной версии данных.",
        "Пересечения не удаляются: конкретные PROXY-правила имеют приоритет",
        "перед общими DIRECT-суффиксами. Это диагностические показатели.",
        "",
        "Идентификатор снимка: " + report["snapshot_sha256"],
        "",
        "| Доменные категории | Записей |",
        "|---|---:|",
    ]
    for name, n in report["domain_counts"].items():
        out.append("| " + name + " | " + str(n) + " |")
    out.extend(["", "| IP-категории | Всего | IPv4 | IPv6 |", "|---|---:|---:|---:|"])
    for name, info in report["ip_counts"].items():
        out.append("| " + name + " | " + str(info["total"]) + " | "
                   + str(info["ipv4"]) + " | " + str(info["ipv6"]) + " |")
    out.extend(["", "## Правила с разными действиями", "",
                "| PROXY | Общий DIRECT | Количество | Примеры |",
                "|---|---|---:|---|"])
    for item in report["policy_overrides"]:
        examples = ", ".join(x["proxied"] + " / " + x["direct_suffix"]
                             for x in item["examples"][:3])
        out.append("| " + item["higher_priority"] + " | " + item["lower_priority"]
                   + " | " + str(item["count"]) + " | " + examples + " |")
    if not report["policy_overrides"]:
        out.append("| — | — | 0 | — |")
    out.extend(["", "## IP-исключения", "", "| Приоритет | Количество |",
                "|---|---:|"])
    for name, item in report["ip_overrides"].items():
        out.append("| " + name + " | " + str(item["count"]) + " |")
    out.extend(["", "## Точные конфликты доменов", ""])
    if report["exact_policy_conflicts"]:
        for item in report["exact_policy_conflicts"]:
            out.append("- " + item["first"] + " / " + item["second"] + ": "
                       + str(item["count"]))
    else:
        out.append("Точных совпадений между категориями с разными действиями нет.")
    out.extend(["", "Расширенный машинный отчёт: quality.json.", ""])
    return "\n".join(out)


def read_snapshot(root):
    manifest = json.loads((root / "install/manifest.json").read_text(encoding="utf-8"))
    records = manifest["files"]
    names = ["rules/" + n + ".list" for n in DOMAINS]
    names += ["rules/" + n + ".cidr" for n in IPS]
    return {n: (root / n).read_bytes() for n in names}, records


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    exclusive = p.add_mutually_exclusive_group()
    exclusive.add_argument("--write", action="store_true")
    exclusive.add_argument("--check", action="store_true")
    args = p.parse_args()
    root = args.root.resolve()
    data, metadata = read_snapshot(root)
    report = analyze(data, metadata)
    products = {"reports/quality.json": to_json(report),
                "reports/quality.md": to_markdown(report)}
    for relative, result in products.items():
        dest = root / relative
        if args.write:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(result, encoding="utf-8")
            print("GENERATED", relative)
        elif args.check:
            if not dest.is_file() or dest.read_text(encoding="utf-8") != result:
                raise ValueError("Stale or absent report: " + relative)
            print("VERIFIED", relative)
        else:
            print("PREVIEW", relative, len(result), "bytes")


if __name__ == "__main__":
    main()
