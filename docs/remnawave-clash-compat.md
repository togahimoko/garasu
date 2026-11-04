# Generic Clash User-Agent compatibility in Remnawave

## Finding (2026-11-04)

Under the previous SRR, `clash/1.0` selected `responseType: CLASH` with no custom template. A live check reported HTTP 200 with **zero** proxies and rule providers, one group, and one rule. Remnawave has separate response generators for `CLASH` and `MIHOMO`. The former targets the discontinued Clash core; it does not support the subscriber's modern VLESS/REALITY transport. A YAML file alone cannot make a legacy Clash binary support that transport.

**Use the already verified Mihomo template**, not a new `CLASH`-type template. `clients/mihomo-remnawave.yaml` is the Remnawave **MIHOMO template** named exactly `Garasu Mihomo`, with live subscriber injection anchors and thirteen six-hour rule providers. The rule for generic `clash/1.0` now selects that existing template.

## Single-rule change

The exact `Clash Core Clients` rule in [the full SRR example](remnawave-six-rule-full.json) must be placed **after** specific Mihomo clients and **before** the unconditional BASE64 fallback. The only intentional change compared with the preceding live export is this rule's generator, match expression, description and template reference:

```json
{
  "name": "Clash Core Clients",
  "enabled": true,
  "operator": "AND",
  "conditions": [{
    "headerName": "user-agent",
    "operator": "REGEX",
    "value": "^clash(?:/|$)",
    "caseSensitive": false
  }],
  "responseType": "MIHOMO",
  "responseModifications": {
    "subscriptionTemplate": "Garasu Mihomo"
  }
}
```

Do not create a `CLASH`-type template with these contents. Keep the browser first, dedicated Happ/INCY `XRAY_BASE64` with their `routing` / `autorouting` headers, explicit Xray JSON opt-in, and the unconditional `XRAY_BASE64` fallback last. `garasu-test-*` still receives fallback BASE64 under full SRR. An existing external squad or a different SRR ordering may override the desired result; inspect the current panel before replacing anything.

## Tests and acceptance

The panel is **not** updated by a GitHub commit. In Remnawave verify that the MIHOMO template `Garasu Mihomo` is present, then update only the `Clash Core Clients` rule (or import a current, reconciled full SRR export). Keep a backup of live SRR and template before applying.

Use the private URL only as a local environment variable; do not paste or store it in this public repository. Run from a network with your authenticated subscription access:

```sh
read -rs GARASU_SUBSCRIPTION_URL
export GARASU_SUBSCRIPTION_URL
python3 scripts/probe_subscription_delivery.py \
  --clients clash mihomo stash singbox happ incy browser xray_json \
  --require-clash-ready
unset GARASU_SUBSCRIPTION_URL
```

If your environment exposes `HTTPS_PROXY`, the probe uses it. `GARASU_HTTP_PROXY` takes precedence, if set. Output is restricted to format/status, counts, and non-sensitive validation flags. Do not log or export the raw subscription body.

For `clash` expect HTTP 200, YAML, **at least 2** populated proxy objects, **2** proxy groups, **13** remote rule providers, and Garasu routes with RKN exceptions before generic RU DIRECT. `proxy-providers: 0` is normal here: subscriber nodes are injected directly into `proxies`. Other clients must preserve their previously verified output shape; Happ/INCY must remain BASE64 with their headers. Real client import and route/TUN checks are separate acceptance steps.

**Limits:** This produces a modern Mihomo-compatible YAML response even when the User-Agent says `clash/1.0`. The original legacy Clash core will still fail to use unsupported node protocols. If the client is actually legacy Clash, migrate it to a maintained Mihomo core.

**Rollback:** Restore the original `Clash Core Clients` rule's `responseType: CLASH` and original `^clash` condition, and remove its custom `subscriptionTemplate`. The rest of SRR is untouched.
