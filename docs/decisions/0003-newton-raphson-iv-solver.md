# 0003 — Newton-Raphson for IV in Phase 1, defer real Jaeckel to Phase 2

**Status:** Accepted
**Date:** 2026-04-07

## Context

Our marketing pitch mentions "Jaeckel's Let's Be Rational" IV solver — the current state of the art, guaranteed to reach 64-bit machine precision in ≤ 2 iterations. However, implementing the real algorithm is non-trivial:

- Reference implementation (Peter Jäckel, 2015) is ~2,000 lines of dense C with rational approximations of cumulative Black functions and carefully tuned rational pivots.
- Correctness testing requires reproducing his published reference values to the last bit.
- The algorithm relies on transforming to normalized Black price space, which adds conceptual complexity.

Meanwhile, Phase 1's real requirement is: **produce correct IVs on a 10k-option chain in a reasonable time**. Newton-Raphson with a well-chosen bracket and bisection fallback easily meets that bar.

## Decision

**Phase 1 ships Newton-Raphson + bisection fallback.** The file is named `jaeckel.cpp` to reserve the namespace for when the real algorithm lands in Phase 2+.

The Newton-Raphson implementation:
- Inverts our own `bsm_price()` → guarantees self-consistency (round-trip IV → price → IV is exact).
- Validates the initial bracket and exponentially expands `hi` until the root is enclosed.
- Switches to bisection after 2 consecutive non-progressing Newton steps (flat-vega region).
- Pre-check: if `price - intrinsic < 1e-10 × max(price, 1)`, return NaN (no time value, IV undefined).

## Consequences

**Gains:**
- Shipped on time, fully tested (round-trip to 1e-12 for vol ≥ 0.02, 1e-9 for vol < 0.02).
- Self-consistent: inverting our own pricer means we can't drift from it.
- ~25 lines of code instead of ~2,000.
- Plenty fast for Phase 1: 10k-option IV solve in ~5 ms on an M-series Mac.

**Give up:**
- Iteration count is 3–8 typically, vs ≤ 2 for real Jaeckel. Phase 2 will recover this.
- Filename `jaeckel.cpp` is temporarily misleading. Documented prominently in `AGENT.md` and the file header comment; do not rename until/unless the real algorithm lands.
- Marketing copy must not claim "Jaeckel" in Phase 1 materials — use "Newton-Raphson" honestly. README says "Jaeckel's Let's Be Rational" currently; update before Phase 1 release announcement.

## Alternatives considered

- **Implement real Jaeckel in Phase 1** — rejected on delivery risk. ~2 weeks of focused numerical work for marginal user-facing benefit given Phase 1 speeds are already sufficient.
- **Port Peter Jäckel's C reference directly** — licensing is murky (published in Wilmott magazine, no explicit license), so we'd need a clean-room rewrite anyway.
- **Use Brent's method** — robust, but slower in practice than Newton-Raphson with a bisection fallback when vega is well-behaved (which is the common case).
- **Use SciPy `brentq` via Python** — kills the vectorized path; unacceptable for batch IV.
