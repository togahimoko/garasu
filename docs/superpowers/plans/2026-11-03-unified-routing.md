# Unified Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver one reviewed routing policy across existing Garasu clients, with Russian DIRECT exceptions, foreign PROXY, and clear VPN/TUN integration.

**Architecture:** Keep the current source snapshot and format adapters. Add a small canonical policy contract and tests, align each client template with it, and make release generation preserve those decisions. Native app and live-panel verification remain separate acceptance gates.

**Tech Stack:** Python 3.12, unittest, PyYAML 6.0.2, Mihomo 1.19.32, sing-box 1.14.2, Xray 26.10.21.

**Spec:** `docs/superpowers/specs/2026-11-03-unified-routing-design.md`

## Global Constraints

- No personal node secrets, subscriptions, or panel credentials in Git.
- Russian DIRECT only after blocked-domain/IP exceptions; foreign default PROXY; extra foreign DIRECT only by explicit reviewed entries.
- Preserve Remnawave node injection and Browser/XRAY_BASE64 fallbacks.
- Never silently fall back from PROXY to DIRECT when all nodes fail.
- Validate available engines, clearly label untested native apps.

## Review Focus

- Domain on RU IP versus blocked IP: test controlled hostname and literal-IP routes.
- Cold rule cache and missing provider: test behavior or mark client unverified.
- LAN and DNS bootstrap with TUN: test local resolver and node hostname.
- 0/1/many nodes and failed pool: ensure no hidden DIRECT.
- IPv6 and UDP: test on supported runtime, document native-device gate.

---

### Task 1: Define routing oracle and source contract

**Files:** Create `scripts/routing_policy.py`; create `tests/test_unified_policy.py`; modify `SOURCES.md`.

**Interfaces:** `classify_domain(domain: str, categories: dict[str, set[str]]) -> str`; `classify_ip(address: str, categories: dict[str, set[str]]) -> str`. Actions: `DIRECT`, `PROXY`, `REJECT`. Explicitly separate LAN, blocked, reviewed direct, RU fallback, foreign fallback. Source metadata records complete blocked inputs.

- [ ] Write tests for overlapping blocked/direct, ordinary RU, unknown foreign, private IP, blocked RU IP, overseas direct exclusions.
- [ ] Run `python -m unittest tests.test_unified_policy -v` and confirm expected failure.
- [ ] Implement minimal policy logic and source validation.
- [ ] Run focused and full unittest suite.
- [ ] Commit.

### Task 2: Align generated data and release builder

**Files:** Modify `scripts/refresh.py`, generated `rules/**`, `geo/**`, `reports/**`, `install/**`, `clients/happ.json`, `clients/incy.json`; add focused builder tests.

**Interfaces:** Use Task 1 policy and source contract. Build from one immutable upstream revision. Include full blocked-domain/IP sources when RU suffix fallback is present; keep integrity and churn gates. No live publication.

- [ ] Write failing tests for complete exception inclusion, deterministic output, rollback on invalid source, and client category consistency.
- [ ] Run focused test and confirm red.
- [ ] Implement builder changes; generate into staging before promotion.
- [ ] Run focused/full tests and audit report check.
- [ ] Commit.

### Task 3: Align proxy-core templates

**Files:** Modify `clients/{mihomo-remnawave.yaml,stash-remnawave.yaml,singbox-remnawave.json,singbox-remnawave-1.14.json,xray-advanced-remnawave.json}`, corresponding canary/experimental templates and tests.

**Interfaces:** Use generated categories from Task 2. No implicit foreign DIRECT; proxy exceptions first; local DNS supported; TUN defined only where engine or UI supports it; Xray DNS/IP classification proven by runtime behavior.

- [ ] Add failing route-matrix and DNS/TUN tests, including overlap and all-down.
- [ ] Run focused tests and confirm red.
- [ ] Align templates without breaking Remnawave markers.
- [ ] Run unit suite and real Mihomo, sing-box, Xray parser/runtime checks.
- [ ] Commit.

### Task 4: Align native-client adapters and delivery

**Files:** Modify `clients/{shadowrocket.conf,happ.json,incy.json}`, `rules/{surge,quantumultx}/**`, `scripts/{refresh.py,build_srr.py}`, `install/links.json`, docs and focused tests. Add integration templates for Surge/Loon/QX if syntax can be validated.

**Interfaces:** Same policy and priorities. Preserve personal subscription delivery and separate app-managed VPN activation.

- [ ] Add failing cross-client parity tests on canonical routing examples and delivery URL/header contracts.
- [ ] Run focused tests and confirm red.
- [ ] Update adapters, installation instructions and offline SRR candidate generation.
- [ ] Run full tests and available validators; document native-only gates.
- [ ] Commit.

### Task 5: Final acceptance and cloud workflow

**Files:** Modify docs and environment draft scripts as necessary.

- [ ] Run complete unittest suite, audit report, available engine parsers and controlled runtime probes.
- [ ] Check Git diff, source provenance, generated artifacts and manifest.
- [ ] Confirm no real subscriptions/secrets or accidental publish.
- [ ] Record per-client result and outstanding native-device/Remnawave acceptance gates.
- [ ] Commit documentation and configuration changes.
