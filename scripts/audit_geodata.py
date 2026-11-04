#!/usr/bin/env python3
"""Decode V2Ray GeoSite/GeoIP protobuf wire data and verify canonical Garasu sets.

Standard library only, no third-party protobuf dependency and no network access.
Validates actual category membership, not only the hashes of .dat files.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def varint(buf: bytes, offset: int) -> tuple[int, int]:
    result = 0
    for i in range(10):
        if offset >= len(buf):
            raise ValueError("Truncated protobuf varint")
        b = buf[offset]
        offset += 1
        result |= (b & 127) << (7 * i)
        if b < 128:
            return result, offset
    raise ValueError("Malformed protobuf varint")


def fields(buf: bytes):
    offset = 0
    while offset < len(buf):
        tag, offset = varint(buf, offset)
        number, wire = tag >> 3, tag & 7
        if number == 0:
            raise ValueError("Invalid protobuf field zero")
        if wire == 0:
            value, offset = varint(buf, offset)
        elif wire == 2:
            size, offset = varint(buf, offset)
            if size > len(buf) - offset:
                raise ValueError("Truncated protobuf field")
            value = buf[offset:offset + size]
            offset += size
        elif wire == 1:
            if len(buf) - offset < 8:
                raise ValueError("Truncated 64-bit protobuf field")
            value = buf[offset:offset + 8]
            offset += 8
        elif wire == 5:
            if len(buf) - offset < 4:
                raise ValueError("Truncated 32-bit protobuf field")
            value = buf[offset:offset + 4]
            offset += 4
        else:
            raise ValueError("Unsupported protobuf wire type " + str(wire))
        yield number, wire, value


def categories(blob: bytes) -> dict[str, list[bytes]]:
    result = {}
    for number, wire, group in fields(blob):
        if (number, wire) != (1, 2):
            raise ValueError("Unexpected Geo data top-level field")
        entries = list(fields(group))
        names = [value.decode("utf-8") for key, typ, value in entries
                 if key == 1 and typ == 2]
        if len(names) != 1:
            raise ValueError("Geo category has missing or duplicate name")
        name = names[0].upper()
        if name in result:
            raise ValueError("Duplicate Geo category " + name)
        result[name] = [value for key, typ, value in entries
                        if key == 2 and typ == 2]
    return result


def geosite_values(messages: list[bytes]) -> set[str]:
    result = set()
    for raw in messages:
        attrs = list(fields(raw))
        types = [value for key, typ, value in attrs if key == 1 and typ == 0]
        names = [value.decode("utf-8").lower() for key, typ, value in attrs
                 if key == 2 and typ == 2]
        if len(types) != 1 or len(names) != 1:
            raise ValueError("Malformed GeoSite domain entry")
        # Domain type=2 (suffix), used for canonical +.domain Garasu data.
        if types[0] != 2:
            raise ValueError("Unexpected GeoSite domain type for pinned data")
        if names[0] in result:
            raise ValueError("Duplicate GeoSite domain")
        result.add(names[0])
    return result


def geoip_values(messages: list[bytes]) -> set[str]:
    result = set()
    for raw in messages:
        attrs = dict((key, value) for key, typ, value in fields(raw))
        if not isinstance(attrs.get(1), bytes) or not isinstance(attrs.get(2), int):
            raise ValueError("Malformed GeoIP CIDR entry")
        addr = ipaddress.ip_address(attrs[1])
        cidr = str(ipaddress.ip_network((addr, attrs[2]), strict=False))
        if cidr in result:
            raise ValueError("Duplicate GeoIP CIDR")
        result.add(cidr)
    return result


def source_values(root: Path, category: str, extension: str) -> set[str]:
    values = []
    for line in (root / "rules" / (category + extension)).read_text(
            encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        values.append(line.strip().lower().removeprefix("+."))
    result = set(values)
    if len(result) != len(values):
        raise ValueError("Duplicate canonical source entries " + category)
    return result


def required_category_names(root: Path) -> tuple[set[str], set[str]]:
    sites, ips = set(), set()
    for name in ("release/incy/config.json", "release/happ/config.json",
                 "release/xray/config.json", "clients/incy.json",
                 "clients/happ.json", "clients/xray-advanced-remnawave.json"):
        obj = (root / name).read_text(encoding="utf-8")
        sites.update(s.upper() for s in re.findall(r"geosite:([a-z0-9_-]+)", obj, re.I))
        ips.update(s.upper() for s in re.findall(r"geoip:([a-z0-9_-]+)", obj, re.I))
    return sites, ips


def audit(root: Path) -> dict:
    sites = categories((root / "geo/geosite.dat").read_bytes())
    ips = categories((root / "geo/geoip.dat").read_bytes())
    required_sites, required_ips = required_category_names(root)
    absent = sorted((required_sites - set(sites)) | (required_ips - set(ips)))
    if absent:
        raise ValueError("Referenced Geo categories missing: " + ", ".join(absent))

    blocked_domains = geosite_values(sites["BANNED-RU"])
    expected_domains = source_values(root, "rkn-domains", ".list")
    if blocked_domains != expected_domains:
        raise ValueError("BANNED-RU differs from canonical blocked domains")
    match_ip = {}
    for category, source in (("BLOCKED-RU", "rkn-ips"), ("RU", "ru-ips")):
        values = geoip_values(ips[category])
        target = source_values(root, source, ".cidr")
        if values != target:
            raise ValueError("GeoIP " + category + " differs from canonical " + source)
        match_ip[category] = len(values)
    ads = geosite_values(sites["GARASU-ADS"])
    ad_source = source_values(root, "ads", ".list")
    policy = json.loads((root / "policy/universal.json").read_text())
    exempt = set(policy["ad_exempt_domains"])
    if ads != ad_source - exempt:
        raise ValueError("GARASU-ADS differs from curated source")
    extras = sorted(ads - ad_source)
    omitted = sorted(ad_source - ads)
    ru_suffixes = geosite_values(sites["GARASU-RU"])
    if not {"ru", "su", "moscow", "xn--p1ai"}.issubset(ru_suffixes):
        raise ValueError("GARASU-RU is missing protected RU suffixes")
    return {
        "schema_version": 1,
        "geosite_categories": len(sites),
        "geoip_categories": len(ips),
        "referenced_geosite": sorted(required_sites),
        "referenced_geoip": sorted(required_ips),
        "banned_ru_exact_match": len(blocked_domains),
        "blocked_ru_ip_exact_match": match_ip["BLOCKED-RU"],
        "ru_ip_exact_match": match_ip["RU"],
        "category_geoblock_ru": len(sites["CATEGORY-GEOBLOCK-RU"]),
        "garasu_ru_suffixes": sorted(ru_suffixes),
        "garasu_ads": len(ads),
        "canonical_ads": len(ad_source),
        "ads_only_in_binary": len(extras),
        "ads_only_in_text": len(omitted),
        "ads_binary_only_examples": extras[:12],
        "ads_text_only_examples": omitted[:12],
        "geosite_bytes": (root / "geo/geosite.dat").stat().st_size,
        "geoip_bytes": (root / "geo/geoip.dat").stat().st_size,
    }


def markdown(result: dict) -> str:
    out = [
        "# Garasu — проверка бинарных GeoSite и GeoIP",
        "",
        "Бинарные форматы V2Ray декодированы, сравнение категорий выполняется",
        "**с содержимым исходных списков**, не только с SHA-256.",
        "",
        "| Проверка | Результат |",
        "| --- | ---: |",
        "| GeoSite категорий | " + str(result["geosite_categories"]) + " |",
        "| GeoIP категорий | " + str(result["geoip_categories"]) + " |",
        "| BANNED-RU полностью совпадает с rules/rkn-domains.list | " +
        str(result["banned_ru_exact_match"]) + " |",
        "| BLOCKED-RU совпадает с rules/rkn-ips.cidr | " +
        str(result["blocked_ru_ip_exact_match"]) + " |",
        "| RU совпадает с rules/ru-ips.cidr | " +
        str(result["ru_ip_exact_match"]) + " |",
        "| CATEGORY-GEOBLOCK-RU | " +
        str(result["category_geoblock_ru"]) + " |",
        "| GARASU-ADS | " + str(result["garasu_ads"]) + " |",
        "| Текстовый ads | " + str(result["canonical_ads"]) + " |",
        "| В бинарном, отсутствуют в текстовом ads | " +
        str(result["ads_only_in_binary"]) + " |",
        "| В текстовом, отсутствуют в бинарном ads | " +
        str(result["ads_only_in_text"]) + " |",
        "",
        "Все категории, на которые ссылаются INCY, Happ и Xray-шаблоны,",
        "**физически присутствуют** в соответствующих .dat.",
        "",
        "GARASU-ADS строго совпадает с основным ads.list за исключением",
        "четырёх явных API-исключений из policy/universal.json.",
        "",
        "Бинарный GeoSite " + str(result["geosite_bytes"]) + " байт, GeoIP " +
        str(result["geoip_bytes"]) + " байт. Размер на диске не равен памяти",
        "клиентского сетевого расширения; для iOS необходим нативный тест.",
        "",
        "Машинный отчёт: [geodata-integrity.json](geodata-integrity.json).",
        "",
    ]
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true")
    group.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    record = audit(root)
    files = {
        "reports/geodata-integrity.json": json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        "reports/geodata-integrity.md": markdown(record),
    }
    for name, contents in files.items():
        path = root / name
        if args.write:
            path.write_text(contents, encoding="utf-8")
            print("CREATED", name)
        elif args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != contents:
                raise ValueError("Stale binary Geo audit: " + name)
            print("VERIFIED", name)
        else:
            print("PREVIEW", name, len(contents))
    print("BINARY_GEO_INTEGRITY=PASS")


if __name__ == "__main__":
    main()
