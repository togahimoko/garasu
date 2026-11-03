# Garasu rule delivery checks

Use `scripts/check_delivery.py` from the network you want to evaluate. This is a read-only diagnostic; it does **not** contact Remnawave, import node subscriptions, change device DNS or install VPN profiles.

It verifies TLS HTTPS retrieval, bytes, SHA-256 against the locally checked-out release manifest, and elapsed time for selected public native profiles, rules, and GeoIP/GeoSite assets.

## Run

From a fresh checkout of the corresponding Garasu branch:

```bash
python3 scripts/check_delivery.py --direct
python3 scripts/check_delivery.py --links install/links.json --direct
python3 scripts/check_delivery.py --proxy http://127.0.0.1:7890
python3 scripts/check_delivery.py --proxy http://127.0.0.1:7890 --json-output result.json
```

On a mirror with a trusted TLS certificate:

```bash
python3 scripts/check_delivery.py --base-url https://YOUR-OWN-RULES-HOST/garasu --direct
```

The `--direct` flag deliberately ignores system proxy environment settings. The `--proxy` flag only accepts a loopback HTTP proxy; it does **not** support embedding proxy credentials in output.
`--links` verifies that the checked-out manifest has the SHA-256 recorded in
`install/links.json` and uses its advertised GitHub Raw base. It checks local
release consistency before probing the selected public assets. This does not
make native app rule updates atomic.

A mismatch can indicate a stale checkout, wrong mirror cache, incomplete publication, tampering, or source version skew. If the remote source is intentionally newer, update the local Git checkout and retry before treating it as an attack.

## Operational design

- Keep customer subscription links and panel credentials out of public mirrors, GitHub Actions, diagnostic logs and issue reports.
- Serve Garasu rules from an **independent** HTTPS endpoint if GitHub Raw is unreliable on target Russian ISPs. Use a different provider/failure domain rather than a second hostname on the same underlying service.
- Store static rules read-only. Disallow directory listing, content uploads and script execution in the rules vhost. Enable TLS validation, sensible cache headers and ETags.
- Publish a complete verified artifact set to a versioned directory; change the public `current` pointer atomically after all hashes match. Keep the previous verified release for rollback.
- Test at least: Russian mobile network without VPN; Russian residential ISP without VPN; through Garasu node; an exit node abroad. A GitHub-hosted runner alone is not evidence of availability in Russia.
- On an initial client install, a remote rule provider can be unavailable before the VPN proxy works. Always test fresh-install/bootstrap behaviour rather than relying on warmed provider caches.
- No non-HTTPS fallback or disabled certificate verification is permitted.

## What this test does not cover

- VLESS/REALITY transport and private host reachability
- Remnawave token delivery, HWID and subscription response matching
- Shadowrocket, Happ and INCY mobile app behaviour
- Service throughput, UDP handling, or private DNS leakage

These require a canary device and authorized access to the actual node / network.
