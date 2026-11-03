# Garasu Data Quality Observatory — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checklist tracking.

**Goal:** Create a deterministic, trustworthy report on published Garasu rule-set quality and cross-category routing conflicts, regenerated and tested with every data refresh.

**Architecture:** Analyze canonical `rules/*.list` and `rules/*.cidr` already in the GitHub repository; compute category statistics and precedence-sensitive parent/child domain exceptions without changing routing. Publish a concise human-readable and machine-readable report, always from the same dataset snapshot as the released rules.

**Tech Stack:** Python 3.12 stdlib, existing GitHub Actions and unittest.

**Spec:** User request to improve Garasu data correctness, provenance and release hygiene. This is a non-invasive first phase; existing client templates are unchanged.

## Decisions and tradeoffs

- Implement **observability first** rather than immediately suppressing overlapping rules: a blocked subdomain under a broad DIRECT suffix can be an intentional exception.
- Use one deterministic script with no network access and no credentials.
- Block CI only on malformed input or inconsistent source inventory, not on expected precedence overrides.
- Commit reports only with verified rule data; no wall-clock timestamps that generate useless six-hour diffs.
- Do not alter Remnawave, subscriptions, VPN node addresses or traffic flows.

## Tasks

- [ ] Add failing tests for conflict reporting, deterministic output, category/priority consistency, and manifest hashes.
- [ ] Verify tests fail for missing quality-report implementation.
- [ ] Implement `scripts/audit_rules.py` with `analyze(root)` and report formatting functions.
- [ ] Verify offline tests, then run complete existing suite.
- [ ] Integrate reports into `scripts/refresh.py` using the current staged generated files so quality reports match source checksums.
- [ ] Add final tests and workflow output checks to ensure reports are present before publishing.
- [ ] Run full GitHub Actions and compare reports against the actual 58 published data assets.
- [ ] Request review and leave as a distinct unmerged PR; live customers remain unchanged.

## Follow-on independent phases

1. Compile Mihomo `.mrs` and sing-box `.srs` with core binaries and run benchmarked size/memory tests.
2. Preserve stable releases with signed provenance and atomic mirroring.
3. Implement multi-region read-only availability probes without putting user secrets into CI.
4. Add manual source trust approval for unusual changes and explicit policy regression fixtures for banking, AI, media and gaming.
