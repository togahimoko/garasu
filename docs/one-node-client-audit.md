# Garasu MAX — Czech-only reliability and client matrix (2026-11-03)

## Scope / non-negotiable architecture

There is **one subscriber node in Czechia**, injected into the client's
configuration by Remnawave. Garasu publishes routing rules, not another VPN
node. Do not introduce a Moscow server, multi-hop proxies, fabricated nodes,
or hand-selected geographical chains.

Desired effective routing:

1. Loopback, local/private networks, `.local`, `.lan`, `home.arpa` -> **DIRECT**.
2. RKN-listed/otherwise inaccessible Russian domains and IPs -> **CZ node**,
   *before* broad Russian DIRECT rules.
3. Advertising and malicious tracking categories -> **REJECT** (exceptions
   where the category interferes with a real application must be assessed).
4. Ordinary Russian websites, banks and public-sector resources -> **DIRECT**.
5. All other traffic -> **CZ node**, **except explicit, reviewed application
   exceptions**. A disconnected node is never permission to silently fall
   back to DIRECT for a PROXY-required destination.

**Known deviation:** existing source lists `rules/games.list` and
`rules/direct.list` route some *foreign* services DIRECT (e.g. Steam,
Epic Games, ArtStation, Twitch). These are inherited upstream rules, not
necessarily desired policy. Neither an indiscriminate rewrite nor an
unreviewed `MATCH,DIRECT` is appropriate. First document actual app
requirements (site vs gameplay endpoints, TCP/UDP), then approve explicit
exceptions and build matching cross-client fixtures.

## Client matrix

| Client | Published artifact | Current automation / limitations | Device-level evidence |
|---|---|---|---|
| Mihomo / Clash Verge | `clients/mihomo-remnawave.yaml` | Remnawave injects node; production still has optional DIRECT selection, saved selection and no explicit mixed-port. Fixed candidate: `clients/canary/mihomo-remnawave.yaml` | **Not proven** on actual Mac and CZ VLESS/Reality node |
| Stash | `clients/stash-remnawave.yaml` | Remnawave injects node; canary adds LAN rules and RU-IP fallback. Mihomo-parser check is not native Stash runtime | **Not proven** in Stash app |
| Shadowrocket | `clients/shadowrocket.conf` | Managed rule configuration is separate from personal server subscription. PROXY requires an actual active subscriber node; it is not guaranteed merely by importing rules | **Not proven** on iOS |
| sing-box 1.14+ | `clients/singbox-remnawave-1.14.json` | Remnawave selector injection; canary uses explicit remote-rule HTTP client via node. Prior system DNS dependency on UDP to 1.1.1.1; candidate uses `local` DNS on device | **Not proven** in target app/ISP |
| sing-box legacy-compatible | `clients/singbox-remnawave.json` | Separate compatibility template; remote rule fetching can depend on implicit defaults; not identical to 1.14 path | **Not proven** |
| INCY | `clients/incy.json` | Autorouting may be imported separately or through client-specific response header; geosite/geoip require correct delivery | **Not proven** in app |
| Happ | `clients/happ.json` | Routing import is embedded in URL/base64; server subscription remains separate | **Not proven** in app |
| Xray advanced | `clients/xray-advanced-remnawave.json` | Opt-in virtual host injection by Remnawave; not a universal Xray template | **Not proven** with subscriber node |
| Surge/Loon | `rules/surge/*.list` | Rule resources only, not a complete profile; requires mapping policies, app-level update/final handling | **Not proven** in app |
| Quantumult X | `rules/quantumultx/*.list` | Remote filter resources and import link; not proof that app's final policy and node selection are correct | **Not proven** in app |

## Structural safeguards added in audit branch

- Mihomo candidate: explicit loopback, private IPv4, CGNAT and local-domain
  DIRECT **before remote RKN rules**. Local-domain routes must not be
  accidentally proxied merely because their IP has not been resolved yet.
  Add `proxy-server-nameserver: system` as a canary bootstrapping route
  to the single node. This must be tested on Russian ISPs; local DNS may
  itself be censored or return a poisoned answer.
- Stash candidate: equivalent high-priority local-domain and CGNAT bypass.
- sing-box 1.14 candidate: explicit local-domain routing and `local`
  system DNS server instead of hard-coded UDP/53 to public 1.1.1.1.
- `tests/test_cross_client_contract.py`: validates injection markers,
  private-network priorities, RKN exceptions before RU DIRECT, fallback to
  proxy, provider coverage and published asset references across app
  formats; records mobile routing data parity without claiming real import.
- `scripts/probe_mihomo_runtime.py`: synthetic HTTP test extended to
  **HTTPS CONNECT with actual TLS certificate verification** through the
  Mihomo listener and proxy node. Still not a real VLESS/Reality test.

## Release gates — required before production promotion

1. **Remnawave response**: test subscriber receives exactly one expected CZ
   proxy in each native client format; subscriber keys never enter GitHub;
   normal subscriptions, expiration, headers and user-agent matching remain
   intact. Test does not modify customer rules.
2. **Mac Mihomo**: verify effective config, proxy listener and real node
   health; with TUN separately off test HTTPS via local proxy; then TUN on
   validate DNS, process routing, IPv4, IPv6, local LAN and no loops.
3. **Route decision + exit-IP matrix**: private domains/IP -> DIRECT;
   Russian ordinary bank/government -> DIRECT; blocked RU domain/IP -> CZ;
   YouTube/Discord/AI -> CZ; generic foreign -> CZ; ads -> REJECT;
   documented game exceptions -> their approved policy. Both the
   matched rule *and actual observed egress* must be verified.
4. **Cold start**: empty rule-provider cache, first install, disconnected
   node, unreachable GitHub Raw, blocked public UDP/53 and impaired DoH.
   Offline rules can preserve a cached prior release, but do not assume a
   previously filled cache on first boot.
5. **Failure tests**: with the single CZ node down, VPN-required traffic
   must fail, not silently go DIRECT. DIRECT destinations and local network
   should remain usable. Distinguish DNS failure, outbound failure,
   provider availability and GUI system-proxy mismatch.
6. **Native client acceptance**: Stash on iOS, Shadowrocket on iOS,
   sing-box in its actual wrapper, Happ and INCY with actual import,
   Xray virtual-host, and any actively offered Surge/Quantumult X
   instructions. Static parsing is insufficient.
7. **Delivery / rollback**: confirm URLs can be downloaded over distinct
   Russian residential and mobile networks, check published hashes against
   immutable manifest, preserve prior working client template, and
   roll back a bad candidate without replacing subscriptions.

## Important distinctions

- Github Actions can validate syntax, unit contracts, and local synthetic
  TLS, but cannot prove the Czech node's reachability from a Russian ISP.
- Rule providers downloaded over `Garasu Auto` cannot bootstrap if the
  only node cannot be reached and no cached rules exist. Test separately
  from local proxy-liveness.
- `no-resolve` on Mihomo target-IP rules can skip DNS on an unresolved
  domain; check actual matched rule before concluding RU-IP coverage.
- Source data are mirrored from `DigneZzZ/routing` and are versioned and
  checked against churn/size. A syntactically safe dataset can still be
  semantically inappropriate for a specific service.
- Never disable TLS verification, leak subscription URLs into CI, or
  reconfigure active subscriber traffic based on a synthetic test alone.

## Technical references

- https://docs.rw/guides/templates/mihomo/
- https://wiki.metacubex.one/en/config/dns/
- https://wiki.metacubex.one/en/config/rules/
- https://wiki.metacubex.one/en/config/rule-providers/
- https://sing-box.sagernet.org/configuration/rule-set/
