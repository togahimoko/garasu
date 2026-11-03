# Garasu Unified v1 — candidate design and acceptance

Status: **candidate only**. Nothing in this branch changes the live Remnawave/eGames panel, subscriber node credentials or existing production routing templates. Source: the Astra design shared by the user on 2026-11-03.

## Selected policy

- One machine-readable contract: policy/unified-v1.json.
- Foreign/public Internet defaults to PROXY. There are no blanket Apple, Microsoft, Steam or IP-check DIRECT exceptions.
- Private LAN and local names have narrowly defined DIRECT routes. A public hostname resolving to a private address does not automatically become a LAN domain in the reference oracle.
- Blocked domains and blocked IPs have priority over broad Russian routing; service PROXY categories precede advertising REJECT.
- All proxy hosts are injected from each subscriber's Remnawave allocation. No country-specific hostnames or node-count cap.
- Exhausted node pool must not silently become DIRECT.
- **General RU bypass stays disabled in ordinary subscription templates.** A separate optional self-contained Mihomo RU-TLD profile is generated only after the complete pinned blocker snapshot passes integrity checks. It embeds 75,306 blocked domains and 25,391 IP ranges, so those two required registries cannot be missing from its cold-start YAML. This has passed Mihomo 1.19.32 parsing, but **runtime DNS rule selection, IPv6 and Russian ISP acceptance remain unverified**. RU IP-literal and Russian-owned foreign-TLD bypass are not enabled.

## Full registry provenance

Upstream DigneZzZ/routing revision: dc2387651714c1a127e4794802ef780634bc4f6e.

- 75,306 full blocked domains; original Git blob 37ab7037219132da59a945f1b53bf910e082461d.
- 25,391 full blocked IPs; original Git blob e0cc864228853f7c6da6334a20519cbfbb5d6c39.
- Exact canonical files: rules/unified/refilter-domain-full.list and rules/unified/refilter-ip-full.cidr.
- Derived sing-box source JSON and Shadowrocket IP RULE-SET are generated from the same rows and checked for exact parity.
- Independent test checks original upstream Git blob SHA-1, content order, row counts and lack of duplicates.

The candidate now uses **policy/unified-release-lock.json** to pin all 22 rule and GeoIP/GeoSite files to exact Git commits, including former mutable main assets. Both immutable source commits derive from the identified DigneZzZ upstream revision. The profile URL and native cache update process are **not yet an atomic release**; promotion must bind the profile to this lock and retain last-known-good assets.

## Candidate generation and formats

Run in a Git checkout:

    python3 scripts/unified_policy.py --verify-assets
    python3 scripts/unified_policy.py --write
    python3 -m unittest discover -s tests -p 'test_unified*.py' -v

The generator writes only under clients/unified/ (not clients/ production files). It provides:

1. Mihomo / Clash Verge: automatic Remnawave injected node group, full blocked registry. Real Mihomo 1.19.32 parser and HTTP/HTTPS CONNECT mock-node runtime passed.
2. Stash: own Remnawave injection marker, parsed with Mihomo for compatibility. Native closed-source Stash import unverified.
3. sing-box 1.14: full blocked registry, real sing-box 1.14.2 parser passed. Remnawave injection emulated.
4. Xray advanced: real Xray 26.10.21 parser passed. Existing GeoIP/GeoSite categories are **not** equivalent to a recompiled full unified registry; broad RU bypass disabled.
5. INCY and Happ JSON: wide foreign DIRECT removed, and optional ad blocking disabled because proprietary block-proxy-direct ordering cannot establish service priority. Native imports and routing headers remain unverified.
6. Shadowrocket: generator output is included as a native .conf **inside the offline ZIP artifact**, but is not tracked as a standalone .conf in the Git branch; import and automatic updating unverified.
7. Mihomo RU TLD snapshot: optional mihomo-ru-tld-verified.yaml included in the offline ZIP. Both full blocker providers are embedded as inline payloads (no network refetch for those lists); general RU DIRECT is limited to Russian domain suffixes and remains absent from ordinary Remnawave templates.

The strict command 'python3 scripts/unified_policy.py --check' requires the seven base candidate outputs to be present and byte-identical. Shadowrocket .conf is intentionally packaged by the offline release builder instead of committed as a standalone file. The optional RU TLD profile is a separate eighth variant generated after pinned-registry validation.

## Reproducible local release, recovery and limits

Run on a clean checkout with the pinned source assets:

    python3 -m scripts.package_unified_release --publish --output-dir ./dist/unified
    python3 -m scripts.package_unified_release --verify --output-dir ./dist/unified
    python3 -m scripts.package_unified_release --rollback --output-dir ./dist/unified

The content-addressed ZIP includes the pinned policy, release lock, 22 rule
and geodata files, the seven base candidate profiles, and one optional
Mihomo Russian-TLD DIRECT profile. bundle-manifest.json indexes the exact
contents. CURRENT.json is the atomic same-filesystem pointer; the
previous verified ZIP is retained for rollback. File tampering, corrupted
archives or missing previous releases block promotion/rollback.

The ZIP reads the 22 pinned rule and geodata assets from their verified
historical Git blobs. Scheduled updates to the ordinary production files
therefore do not change the candidate release or break local packaging.
The candidate profiles are generated from the current client templates and
must pass the candidate drift tests before publication.

This makes local candidate packaging reproducible; it does **not** provide
a remotely atomic HTTP cache, live Remnawave subscription update, or an
installer for proprietary mobile clients. The CI workflow publishes the
candidate as a downloadable action artifact, not as a public subscription.
Never upload personal Remnawave keys/subscription content to the artifact.

## DNS/TUN/subscriptions

Mihomo uses system DNS for node bootstrap; remote rule providers use the injected proxy group, which still needs cold-network testing. TUN, DNS hijack, IPv6 and UDP cannot be certified solely by a template parser. GitHub Raw reachability from Russia is unverified: publication needs an independently reachable TLS delivery origin. No private subscription host, token or node endpoint may be embedded in public rules.

Remnawave Subscription Response Rules, Browser and XRAY_BASE64 fallback, eGames Reverse Proxy and live subscriber URLs have **not** been modified. Subscription-refresh faults require live sanitized SRR and native client checks, not mere GitHub parser tests.

## Read-only subscription refresh diagnosis

The CLI tool scripts/probe_subscription_delivery.py compares subscription
delivery formats for Mihomo, Clash, Stash, sing-box, Happ, INCY and browser.
It does not modify Remnawave, does not log the subscription URL or response
body and deliberately blocks redirects.

Use an interactive masked entry rather than embedding the private URL
in a terminal command or sharing it in GitHub:

    read -rs GARASU_SUBSCRIPTION_URL
    export GARASU_SUBSCRIPTION_URL
    python3 scripts/probe_subscription_delivery.py
    unset GARASU_SUBSCRIPTION_URL

For an additional local HTTP proxy path, set GARASU_HTTP_PROXY to the
already-running local proxy URL, and run the same command. The report
contains only status code, detected response format, bounded response
size and sanitized error class. It cannot certify certificate provenance,
node health, VPN throughput or a native client's actual User-Agent.
A passing generic UA probe does not prove real SRR delivery until a
matching real client and the panel's SRR are inspected.

## Promotion requirements

- [x] Unified contract and independent domain/IP route oracle.
- [x] Full source pinned, original Git SHA-1 verified, derived outputs checked for parity.
- [x] 22 release assets locked to immutable Git revisions; CI verifies every actual blob and byte length on clean checkout.
- [x] Reference oracle checks all A/AAAA answers: blocked-IP override, malformed/missing DNS conservative PROXY.
- [x] Mihomo 1.19.32, sing-box 1.14.2 and Xray 26.10.21 parsers.
- [x] Mihomo HTTP / TLS CONNECT through a credential-free synthetic node.
- [x] Offline deterministic ZIP includes seven base profiles plus optional RU TLD Mihomo candidate; same-filesystem CURRENT.json pointer and verified local rollback tested.
- [x] Real Mihomo 1.19.32 parser accepts full inlined 75,306-domain / 25,391-IP RU TLD variant (syntax/load test only).
- [ ] Full atomic versioned **profile and native cache** publication with rollback (immutable source-asset delivery itself is implemented).
- [ ] Cold start verifies full registry **before** general RU DIRECT; blocked-IP and multi-A/AAAA behavior tested.
- [ ] Native INCY, Happ, Shadowrocket, Stash, Surge, Loon and Quantumult X route behavior and subscription updates.
- [ ] Single-policy GeoSite/GeoIP protobuf compilation and equivalent native Xray routing.
- [ ] Real eGames/Remnawave sanitized SRR response and update tests.
- [ ] Native TUN, IPv6, UDP, DNS hijack and Russian residential/mobile validation.
- [ ] End-to-end YouTube 4K throughput and previously failing sites.

Do not merge as production-ready or migrate subscribers while these gates remain open.
