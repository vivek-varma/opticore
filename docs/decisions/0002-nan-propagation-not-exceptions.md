# 0002 — Numerical edge cases return NaN, never raise

**Status:** Accepted
**Date:** 2026-04-06

## Context

Option pricing routines hit pathological inputs constantly in real chains:

- Deep ITM puts where price ≈ intrinsic value (time value < 1e-10) — IV is mathematically undefined.
- Zero time-to-expiry or zero volatility degenerate cases.
- Bid/ask quotes outside the arbitrage-free bounds (especially in low-volume chains).
- Implied vol solves that hit the flat-vega region far from ATM.

Two choices for how the C++ / Python layer responds:

1. **Raise exceptions** (Python `ValueError`, C++ `std::domain_error`).
2. **Return NaN** (or ±INF where mathematically appropriate) and let callers filter.

## Decision

Numerical edge cases return **NaN** (or ±INF where appropriate). They never throw.

Explicit throws remain only for *programmer errors* — not for input-data pathology. Example: passing `kind="banana"` to `oc.price()` raises `ValueError`; passing `price=0.01, strike=500, spot=100` (deep OTM with no time value) returns NaN.

## Consequences

**Gains:**
- **Vectorized code stays fast.** A single bad row in a 10k-option chain does not abort the whole batch. Users filter with `df[df['iv'].notna()]`.
- **No try/except scaffolding** inside hot loops. Throwing and catching across a nanobind boundary is expensive (~1µs per throw on modern x86); unacceptable in batch paths.
- **Matches NumPy / pandas idioms.** Users are already used to NaN meaning "not computable for this row".
- **IEEE-754 propagation is free.** NaN flows through arithmetic without extra checks.

**Give up:**
- Users don't get a reason for the NaN, just the NaN itself. Mitigation: all NaN conditions are documented per-function, and `docs/decisions/` + docstrings list them.
- Tests must explicitly assert NaN for each documented edge case (`test_accuracy.py::TestNaNPropagation` already does this).
- `math.isnan()` checks are easy to forget in user code. Accepted cost — the alternative (exceptions) is worse.

## Specific NaN-producing cases (as of Phase 1)

| Input | Output | Reason |
|---|---|---|
| `price < intrinsic` (arb violation) | `iv` = NaN | No real solution |
| `price - intrinsic < 1e-10 × max(price, 1)` | `iv` = NaN | No-time-value, vega ≈ 0 |
| `vol < 0` | `price` = NaN | Invalid input (negative vol) |
| `expiry <= 0` | handled per-function (usually NaN or intrinsic) | Expired / at-expiry |

## Alternatives considered

- **Raise exceptions for everything invalid** — rejected on performance grounds (batch path) and ergonomics (try/except in notebooks is painful).
- **Return `(value, status_code)` tuples** — clunky, forces users to unpack on every call, breaks vectorization.
- **Silent zero instead of NaN** — worst of both worlds: hides the error AND corrupts downstream math.
