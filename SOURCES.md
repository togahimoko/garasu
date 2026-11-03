# Garasu Routing — sources and attribution

Garasu MAX is a set of configurations, rule ordering, validation and distribution scripts. The source data is not original Garasu work.

- [DigneZzZ/routing](https://github.com/DigneZzZ/routing): domain/IP and Xray GeoIP/GeoSite datasets; upstream build is [DigneZzZ/routing-build](https://github.com/DigneZzZ/routing-build).
- Original source datasets include Re:filter, MetaCubeX, legiz-ru and other public lists as described by the upstream project.

## Unified routing source contract

Broad Russian domain and IP DIRECT fallback requires a complete, validated blocked-input snapshot. The reduced `release/refilter-domain.list` and `release/refilter-ip.list` were built for the old, narrower DIRECT scope; they cannot establish safe exceptions for all `.ru`/`.su` domains and RU IPs. The required inputs are DigneZzZ/routing `refilter-domain-full` and `refilter-ip-full`, both from **one immutable commit**. The builder must record and verify each input's URL, dataset name, commit SHA, SHA-256 digest, and entry count. `scripts.routing_policy.validate_source_metadata` checks those metadata fields; the builder must also hash the downloaded bytes, validate format and size, and reject a partial or inconsistent snapshot before enabling broad RU DIRECT. A cold start without the validated complete set must fail explicitly or use a conservative profile without broad RU fallback; a warm update must retain the last complete valid set.

Metadata records for the policy use keys `blocked_domains` and `blocked_ips`, each containing `dataset`, `url`, `revision` (40 hex characters), `sha256` (64 hex characters), and positive `entries`. Dataset values are `refilter-domain-full` and `refilter-ip-full` respectively. Both records must have the same revision. Each URL must be exactly `https://raw.githubusercontent.com/DigneZzZ/routing/<revision>/release/<dataset>.list`; another host, repository, path, or revision is rejected. The `direct` category is for individually reviewed exceptions with a recorded reason; there is no automatic foreign DIRECT category. Re:filter community geo restrictions and itdoginfo GeoBlock are separate candidate sources that require provenance, overlap review, and route tests before inclusion. Their service restrictions, provider filtering, and the official block registry are different signals.

These fields establish provenance and integrity of the repository snapshot. They do not prove current blocking status at any Russian provider, service availability, or the reachability of a VPN node. The policy oracle's RU fallback presumes the builder has passed the complete-source gate; it does not perform a live RKN lookup.

The scheduled build downloads, normalizes and republishes data. A source URL, SHA-256 digest and entry count / byte length are recorded in `install/manifest.json`. An update is rejected if a file is empty, malformed or unexpectedly small.

**Provenance and licensing:** Naming a Garasu profile does not make Garasu the author of upstream datasets. Upstream repositories and individual sources may have distinct licenses, database rights and redistribution requirements. Before commercial distribution of the full mirrored datasets, verify those terms. Remove any source that does not permit redistribution.

No subscriber links, node credentials, access tokens or Remnawave secrets are included in this repository.
