# Garasu Routing — sources and attribution

Garasu MAX is a set of configurations, rule ordering, validation and distribution scripts. The source data is not original Garasu work.

- [DigneZzZ/routing](https://github.com/DigneZzZ/routing): domain/IP and Xray GeoIP/GeoSite datasets; upstream build is [DigneZzZ/routing-build](https://github.com/DigneZzZ/routing-build).
- Original source datasets include Re:filter, MetaCubeX, legiz-ru and other public lists as described by the upstream project.

The scheduled build downloads, normalizes and republishes data. A source URL, SHA-256 digest and entry count / byte length are recorded in `install/manifest.json`. An update is rejected if a file is empty, malformed or unexpectedly small.

**Provenance and licensing:** Naming a Garasu profile does not make Garasu the author of upstream datasets. Upstream repositories and individual sources may have distinct licenses, database rights and redistribution requirements. Before commercial distribution of the full mirrored datasets, verify those terms. Remove any source that does not permit redistribution.

No subscriber links, node credentials, access tokens or Remnawave secrets are included in this repository.
