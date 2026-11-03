# Garasu Unified v1 — candidate design and acceptance

Status: **candidate only**. Nothing in this branch changes the live Remnawave/eGames panel, subscriber node credentials or existing production routing templates. Source: the Astra design shared by the user on 2026-11-03.

## Selected policy

- One machine-readable contract: policy/unified-v1.json.
- Foreign/public Internet defaults to PROXY. There are no blanket Apple, Microsoft, Steam or IP-check DIRECT exceptions.
- Private LAN and local names have narrowly defined DIRECT routes. A public hostname resolving to a private address does not automatically become a LAN domain in the reference oracle.
- Blocked domains and blocked IPs have priority over broad Russian routing; service PROXY categories precede advertising REJECT.
- All proxy hosts are injected from each subscriber's Remnawave allocation. No country-specific hostnames or node-count cap.
- Exhausted node pool must not silently become DIRECT.
- **General RU TLD/IP DIRECT is deliberately disabled in current candidates.** The full registry is now pinned, but a native cold-start proof that it is loaded before broad RU DIRECT is not yet implemented. The reference oracle shows desired RU behavior only when full exceptions are verified.

## Full registry provenance

Upstream DigneZzZ/routing revision: dc2387651714c1a127e4794802ef780634bc4f6e.

- 75,306 full blocked domains; original Git blob 37ab7037219132da59a945f1b53bf910e082461d.
- 25,391 full blocked IPs; original Git blob e0cc864228853f7c6da6334a20519cbfbb5d6c39.
- Exact canonical files: rules/unified/refilter-domain-full.list and rules/unified/refilter-ip-full.cidr.
- Derived sing-box source JSON and Shadowrocket IP RULE-SET are generated from the same rows and checked for exact parity.
- Independent test checks original upstream Git blob SHA-1, content order, row counts and lack of duplicates.

The original 58-asset Garasu production manifest is **moving** with scheduled refreshes. This candidate holds its own pinned snapshot and does not depend on current production manifest state. Other existing service categories still use their published main files: fully atomic profile-plus-data versioning is not yet finished.

## Candidate generation and formats

Run in a Git checkout:

    python3 scripts/unified_policy.py --write
    python3 -m unittest discover -s tests -p 'test_unified*.py' -v

The generator writes only under clients/unified/ (not clients/ production files). It provides:

1. Mihomo / Clash Verge: automatic Remnawave injected node group, full blocked registry. Real Mihomo 1.19.32 parser and HTTP/HTTPS CONNECT mock-node runtime passed.
2. Stash: own Remnawave injection marker, parsed with Mihomo for compatibility. Native closed-source Stash import unverified.
3. sing-box 1.14: full blocked registry, real sing-box 1.14.2 parser passed. Remnawave injection emulated.
4. Xray advanced: real Xray 26.10.21 parser passed. Existing GeoIP/GeoSite categories are **not** equivalent to a recompiled full unified registry; broad RU bypass disabled.
5. INCY and Happ JSON: wide foreign DIRECT removed. Native imports, routing headers and block/proxy ordering unverified.
6. Shadowrocket: generator present, but the candidate .conf is not yet checked in; import and automatic updating unverified.

The strict command 'python3 scripts/unified_policy.py --check' requires ALL seven committed candidates to match their generated content. The tests explicitly report missing outputs rather than declaring a complete build.

## DNS/TUN/subscriptions

Mihomo uses system DNS for node bootstrap; remote rule providers use the injected proxy group, which still needs cold-network testing. TUN, DNS hijack, IPv6 and UDP cannot be certified solely by a template parser. GitHub Raw reachability from Russia is unverified: publication needs an independently reachable TLS delivery origin. No private subscription host, token or node endpoint may be embedded in public rules.

Remnawave Subscription Response Rules, Browser and XRAY_BASE64 fallback, eGames Reverse Proxy and live subscriber URLs have **not** been modified. Subscription-refresh faults require live sanitized SRR and native client checks, not mere GitHub parser tests.

## Promotion requirements

- [x] Unified contract and independent domain/IP route oracle.
- [x] Full source pinned, original Git SHA-1 verified, derived outputs checked for parity.
- [x] Mihomo 1.19.32, sing-box 1.14.2 and Xray 26.10.21 parsers.
- [x] Mihomo HTTP / TLS CONNECT through a credential-free synthetic node.
- [ ] Full atomic versioned rule/profile delivery with rollback.
- [ ] Cold start verifies full registry **before** general RU DIRECT; blocked-IP and multi-A/AAAA behavior tested.
- [ ] Native INCY, Happ, Shadowrocket, Stash, Surge, Loon and Quantumult X route behavior and subscription updates.
- [ ] Single-policy GeoSite/GeoIP protobuf compilation and equivalent native Xray routing.
- [ ] Real eGames/Remnawave sanitized SRR response and update tests.
- [ ] Native TUN, IPv6, UDP, DNS hijack and Russian residential/mobile validation.
- [ ] End-to-end YouTube 4K throughput and previously failing sites.

Do not merge as production-ready or migrate subscribers while these gates remain open.
