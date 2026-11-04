# Mihomo MRS

Thirteen compiled binary rule sets for Mihomo-compatible `domain` and `ipcidr` providers.

- `manifest.json` records the source Git revision, file sizes and SHA-256.
- `*.mrs` files are native binaries, not renamed text lists.
- Build with `python3 ../build.py --core /path/to/mihomo --source-root ../../.. --output /tmp/garasu-mrs --source-commit SHA` from this directory, or run the same script from the repository root with absolute paths.
- Validate all SHA-256 values and load every provider in an isolated Mihomo instance before publication.
- Updating `rules/*.list` or `rules/*.cidr` does not automatically regenerate MRS. Publish matching sources and binaries together.

See [operations](../../../docs/operations.md).
