#!/usr/bin/env python3
"""Atomic MIT Geosite + official Telegram CIDR snapshot for expanded Garasu.

Fetch sources pinned to a single upstream commit, normalize safe suffixes and
fail if sources suddenly shrink, contain invalid syntax or lose critical data.
No GitHub Actions, proxy credentials, private nodes, or live-client modifications.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE_REPO="https://github.com/hydraponique/roscomvpn-geosite.git"
SOURCE_RAW="https://raw.githubusercontent.com/hydraponique/roscomvpn-geosite/"
# MIT licensed, immutable snapshot resolved at each refresh.
DOMAINS={
    "ru-services":"category-ru","ru-whitelist":"whitelist",
    "microsoft":"microsoft","apple":"apple","google-play":"google-play",
    "epicgames":"epicgames","origin":"origin","riot":"riot",
    "escapefromtarkov":"escapefromtarkov","steam":"steam",
    "twitch":"twitch","pinterest":"pinterest","faceit":"faceit",
    "github":"github","twitch-ads":"twitch-ads","telegram":"telegram",
    "win-spy":"win-spy","torrent-domains":"torrent",
    "category-ads":"category-ads","ru-geoblock":"category-geoblock-ru",
    "google-deepmind":"google-deepmind","push":"push",
    "youtube-global":"youtube",
}
# Direct routing of these IP-check sites leaks home IP instead of VPN exit.
EXCLUDE_DIRECT={
    "ipify.org","checkip.amazonaws.com","ifconfig.me",
    "ipapi.is","iplocate.io","ip.sb",
}
TELEGRAM_CIDRS="https://core.telegram.org/resources/cidr.txt"
TELEGRAM_MIRROR="https://raw.githubusercontent.com/disposable/cloud-ip-ranges/master/txt/telegram.txt"


def retrieve(url: str) -> bytes:
    if not (url.startswith(SOURCE_RAW) or url in (TELEGRAM_CIDRS,TELEGRAM_MIRROR)):
        raise ValueError("Unapproved upstream source")
    command=["curl","--noproxy","*","--retry","2","--fail","--silent","--show-error",
             "--location","--connect-timeout","8","--max-time","40",url]
    result=subprocess.run(command,capture_output=True,timeout=90,check=True)
    if not result.stdout or len(result.stdout)>5_000_000:
        raise ValueError("Missing or excessive upstream size")
    return result.stdout


def revision() -> str:
    result=subprocess.run(["git","ls-remote",SOURCE_REPO,"refs/heads/master"],
                          capture_output=True,timeout=30,check=True)
    match=re.fullmatch(rb"([0-9a-f]{40})\trefs/heads/master\n?",result.stdout)
    if not match:raise ValueError("Invalid MIT upstream commit")
    return match.group(1).decode()


def normalize(name: str, raw: bytes) -> tuple[bytes,dict]:
    from collections import Counter
    sections=Counter()
    out=set()
    for row in raw.decode("utf-8-sig").splitlines():
        value=row.strip()
        if not value or value.startswith("#"):continue
        if value.startswith("domain:"):
            host=value[7:].lower()
            sections["domain"]+=1
        elif value.startswith("full:"):
            # Exact matches cannot be represented in domain MRS without widening;
            # skip and report them rather than silently weakening specificity.
            sections["full_omitted"]+=1
            continue
        elif value.startswith(("regexp:","keyword:")):
            sections[value.split(":",1)[0]+"_omitted"]+=1
            continue
        else:
            sections["bare_omitted"]+=1
            continue
        parts=host.split(".")
        if len(parts)<2 or len(host)>253 or any(
            len(part)>63 or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?",part)
            for part in parts
        ):
            sections["invalid_omitted"]+=1
            continue
        if name in ("ru-services","ru-whitelist") and host in EXCLUDE_DIRECT:
            sections["ipcheck_excluded"]+=1
            continue
        out.add("+."+host)
    if not out:raise ValueError(name+" lost all domain entries")
    if name in ("ru-services","ru-whitelist") and len(out)<40:
        raise ValueError(name+" direct category source unexpectedly shrank")
    blob=("# Garasu extra domain set | MIT source hydraponique/roscomvpn-geosite\n" +
          "\n".join(sorted(out)) + "\n").encode()
    return blob,dict(sections)


def normalize_patterns(raw: bytes, *, source: str) -> tuple[bytes, int]:
    """Preserve GeoSite keywords and regex as typed classical rule lines."""
    rules=set()
    for line in raw.decode("utf-8-sig").splitlines():
        row=line.strip()
        if not row or row.startswith("#"):
            continue
        if row.startswith("keyword:"):
            pattern=row[len("keyword:"):]
            kind="DOMAIN-KEYWORD"
        elif row.startswith("regexp:"):
            pattern=row[len("regexp:"):]
            kind="DOMAIN-REGEX"
        else:
            continue
        if not pattern or len(pattern)>350 or "\\n" in pattern or "\\r" in pattern or "," in pattern:
            raise ValueError("Unsupported upstream classical rule syntax: "+source)
        rules.add(kind+","+pattern)
    if not rules:
        raise ValueError("Missing upstream classical patterns: "+source)
    data=("# Garasu typed classical patterns | RoscomVPN GeoSite MIT source\n"+
          "\n".join(sorted(rules))+"\n").encode("utf-8")
    return data,len(rules)


def telegram(raw: bytes) -> bytes:
    cidrs=set()
    for line in raw.decode("utf-8-sig").splitlines():
        row=line.strip()
        if not row or row.startswith("#"):continue
        cidrs.add(str(ipaddress.ip_network(row,strict=False)))
    if len(cidrs)<10 or not any('91.108.' in c for c in cidrs):
        raise ValueError("Telegram official IP data incomplete")
    return ("# Telegram CIDR snapshot | origin recorded in provenance.json\n" +
            "\n".join(sorted(cidrs)) + "\n").encode()


def assemble(*, root: Path=ROOT, source_dir: Path|None=None) -> dict[str,bytes]:
    upstream_revision=(source_dir/"revision").read_text().strip() if source_dir else revision()
    if not re.fullmatch("[0-9a-f]{40}",upstream_revision):
        raise ValueError("Unpinned upstream revision")
    output={}
    records={}
    for name,upstream_name in DOMAINS.items():
        raw=((source_dir/upstream_name).read_bytes() if source_dir else
             retrieve(SOURCE_RAW+upstream_revision+"/data/"+upstream_name))
        data,sections=normalize(name,raw)
        output["rules/extra/"+name+".list"]=data
        records[name]={"source":"data/"+upstream_name,
                       "source_sha256":hashlib.sha256(raw).hexdigest(),
                       "domains":data.count(b"\n")-1,
                       "skipped":sections}
    for name,upstream_name in (
        ("ru-geoblock-patterns","category-geoblock-ru"),
        ("github-patterns","github")
    ):
        raw=((source_dir/upstream_name).read_bytes() if source_dir else
             retrieve(SOURCE_RAW+upstream_revision+"/data/"+upstream_name))
        source,count=normalize_patterns(raw,source=upstream_name)
        output["rules/extra/"+name+".list"]=source
        records[name]={"source":"data/"+upstream_name,
                       "source_sha256":hashlib.sha256(raw).hexdigest(),
                       "typed_classical_rules":count}
    if source_dir and (source_dir/"telegram-ips").exists():
        source=(source_dir/"telegram-ips").read_bytes()
        origin=(source_dir/"telegram-source").read_text().strip() if (source_dir/"telegram-source").exists() else "provided-snapshot"
    else:
        try:
            source=retrieve(TELEGRAM_CIDRS)
            origin=TELEGRAM_CIDRS
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            # Unofficial mirror is an explicit failover, not an official source.
            # Provenance marks which origin supplied the exact accepted bytes.
            source=retrieve(TELEGRAM_MIRROR)
            origin=TELEGRAM_MIRROR
    output["rules/extra/telegram-ips.cidr"]=telegram(source)
    provenance={"geosite_origin":"hydraponique/roscomvpn-geosite",
                "geosite_revision":upstream_revision,
                "geosite_license":"MIT (docs/licenses/roscomvpn-geosite-MIT.txt)",
                "telegram_source":TELEGRAM_CIDRS,
                "telegram_mirror":TELEGRAM_MIRROR,
                "telegram_source_used":origin,
                "telegram_source_sha256":hashlib.sha256(source).hexdigest(),
                "categories":records}
    output["rules/extra/provenance.json"]=(json.dumps(provenance,indent=2,sort_keys=True)+"\n").encode()
    return output


def main():
    cli=argparse.ArgumentParser()
    mode=cli.add_mutually_exclusive_group(required=True)
    mode.add_argument("--refresh",action="store_true")
    mode.add_argument("--check",action="store_true")
    cli.add_argument("--source-dir",type=Path,help="Pinned fixture snapshot, no network")
    args=cli.parse_args()
    if args.check and args.source_dir is None:
        # Offline check must never need the current Mac network or live proxy.
        provenance=json.loads((ROOT/"rules/extra/provenance.json").read_text())
        if not re.fullmatch(r"[0-9a-f]{40}",provenance["geosite_revision"]):
            raise ValueError("Unpinned geosite snapshot")
        for name in list(DOMAINS)+["ru-geoblock-patterns","github-patterns"]:
            file=ROOT/"rules/extra"/(name+".list")
            if not file.exists() or len(file.read_text().splitlines())<2:
                raise ValueError("Missing/empty extra source: "+name)
        if len(telegram((ROOT/"rules/extra/telegram-ips.cidr").read_bytes()).splitlines())<11:
            raise ValueError("Telegram source incomplete")
        print("PASS offline extra snapshot",len(DOMAINS),"at",provenance["geosite_revision"])
        return
    output=assemble(source_dir=args.source_dir)
    stale=[path for path,blob in output.items()
           if not (ROOT/path).exists() or (ROOT/path).read_bytes()!=blob]
    if args.check and stale:raise SystemExit("STALE extra categories: "+",".join(stale))
    if args.refresh:
        for rel,blob in output.items():
            path=ROOT/rel
            path.parent.mkdir(parents=True,exist_ok=True)
            temporary=path.with_suffix(path.suffix+".tmp")
            temporary.write_bytes(blob)
            temporary.replace(path)
    print("PASS MIT source categories",len(DOMAINS),
          "Telegram CIDRs",output["rules/extra/telegram-ips.cidr"].count(b"\n")-1,
          "changed",len(stale))


if __name__=="__main__":
    main()
