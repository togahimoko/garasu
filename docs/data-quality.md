# Garasu Data Quality

Garasu publishes different rule-set formats from one upstream snapshot. Every scheduled build resolves the upstream Git branch to a **single immutable 40-character commit SHA** before downloading any input files. The release manifest records this exact revision and per-file SHA-256 digests.

## Automated checks

- Required domain and IP categories are present and parse correctly.
- Counts and checksums match the release manifest.
- More-specific PROXY exceptions that overlap with broader DIRECT rules are reported.
- Exact duplicates with conflicting actions are reported.
- RKN IP exceptions under broad regional ranges are reported, with precedence preserved.
- JSON and Markdown summaries are deterministic: no volatile timestamps or user-specific values.
- The entire report is generated from the same staged snapshot as the published rule sets. A failed report blocks publication.

## Reading overlaps

A blocked host can belong under a generally allowed domain suffix. For example, a specific blocked hostname may sit under an otherwise DIRECT service domain. Keeping the more-specific PROXY rule earlier in the routing order is intentional; deleting either entry blindly can reduce accuracy. Therefore an overlap is **not automatically an error**.

Review newly introduced overlaps and large changes before rolling out a source revision. The automated report gives counts, a limited set of examples and a fingerprint tying it to the source release.

## Locations

- Machine-readable report: reports/quality.json
- Human-readable report: reports/quality.md
- Rebuild locally: python3 scripts/audit_rules.py --root . --write
- Verify local published report: python3 scripts/audit_rules.py --root . --check

Reports appear in the repository after a validated scheduled publication. On pull requests, the CI workflow also uploads the report as a build artifact.

## Future improvements

- Delta analysis for added/removed domains and CIDR ranges between releases
- Explicitly reviewed exceptions for high-impact websites
- Compact core-specific binary assets and performance measurements
- Signed build provenance for immutable release bundles
- Independent geographic availability monitoring for published static files

See SOURCES.md for third-party data attribution.
