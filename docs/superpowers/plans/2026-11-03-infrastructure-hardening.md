# Garasu | Infrastructure hardening design — 2026-11-03

## Intent
Improve resilience and integrity of the routing publication pipeline for subscribers on constrained networks, without changing live Remnawave settings or breaking existing imported profiles.

## Constraints
- Main subscription continues to carry user-specific VLESS / Shadowsocks credentials only via Remnawave.
- No user credentials, server IPs, secrets, or purchase information in the public repository.
- Current transport is predominantly TCP due to UDP filtering; do not introduce UDP-only dependencies.
- Existing app family templates are distinct; no claim that an engine parser proves device interoperability.
- Network behaviour for people in Russia is not measurable solely from a US-based GitHub runner.

## Approaches considered
1. **GitHub-only raw origin** (current): simplest, but blocked-domain availability and third-party drift are single points of failure.
2. **Controlled release source + optional independent HTTPS mirror** (selected for incremental design): preserve GitHub as build origin, provide integrity-checked artifacts and a documented read-only mirror plan; mirrors can be added only after a verified hostname and authentication/access policy are supplied.
3. **Move all client subscriptions through a custom gateway**: more control but introduces an additional live dependency and risk to customer subscriptions; not part of this patch.

## Implementation phases
1. **Supply-chain controls**: immutable SHA pins for Actions; content-only build permissions where needed; document immutable container image approach and manual upgrade policy. Tests fail for movable Action tags.
2. **Source validation**: reject poisoned or malformed rule suffixes and pathologically broad proxy IPs before conversion; fail closed and leave last release intact; strict, inspectable validation tests.
3. **Routing correctness**: verify effective policy ordering for overlapping rules; check DNS bootstrap, LOCAL bypass and initial provider access, without relying on global UDP filtering.
4. **Build provenance**: deterministic content hashes, manifest with source provenance, resource limits and offline check against artifact mutations; CI real-core checks remain mandatory.
5. **Operations readiness**: external network observation matrix, read-only mirror guidance, last-good rollback procedure, canary rollout in Remnawave with exact response checks.

## Acceptance
- Red-green regression checks on every altered behavior.
- GitHub CI produces zero failures, including real Mihomo/sing-box parser checks.
- No changes to live Remnawave, old subscription responses or credentials.
- Record limitations: mobile apps, РФ ISP routes and real transport/TLS need an authorized live-device test.
