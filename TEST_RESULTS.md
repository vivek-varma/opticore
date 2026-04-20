# OptiCore — C++ accuracy verification results

**Status:** ✅ All 96 test cases / 1653 assertions passing
**Last verified:** Apr 2026
**Test framework:** Catch2 v3.5.4

## How to reproduce

```bash
./build_and_test.sh
```

Or manually:

```bash
cmake -B build -DOPTICORE_BUILD_TESTS=ON -DOPTICORE_BUILD_PYTHON=OFF -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
./build/opticore_tests
```

Expected output ends with:
```
All tests passed (1653 assertions in 96 test cases)
```

## Test categories

The suite spans 5 files and 96 test cases. Each test belongs to one of three independent verification strategies — every formula in the C++ core is checked by **at least two** of them.

### 1. Reference values (ground truth from outside the system)

`reference_values.hpp` defines 20 BSM scenarios spanning ATM/ITM/OTM at expirations from 1 month to 5 years, with and without dividends, in low-vol and high-vol regimes. Each case includes the call price, put price, and all 6 Greeks, hand-computed in Python with `math.erfc` to full double precision.

`test_pricing_accuracy.cpp` and `test_greeks_accuracy.cpp` compare every output of `bsm_call`, `bsm_put`, and `compute_greeks` against these references to a relative tolerance of `1e-10` (≈ machine epsilon for these formulas).

### 2. Mathematical identities (must hold by definition)

`test_accuracy.cpp` verifies properties that any correct BSM implementation must satisfy:

- **Put-call parity** — `C - P == S·exp(-qT) - K·exp(-rT)` — tested across **1000 random parameter sets** (varying spot, strike, rate, vol, dividend, expiry) to a tolerance of `1e-10`.
- **Greek symmetries** — `gamma_call == gamma_put`, `vega_call == vega_put`, `delta_call - delta_put == exp(-qT)` — tested across 100 random sets to machine precision (`1e-15`).
- **Monotonicity** — call price must decrease in strike, increase in spot/expiry/vol; put price the opposite. Tested by sweeping each parameter and asserting strictly monotone output.

### 3. Self-consistency (the system must agree with itself)

Two forms:

**IV round-trip** (`test_iv_accuracy.cpp`): for any sigma used to price an option, `implied_vol(price, ...)` must return that same sigma. Tested across:
- All 20 reference cases (call and put separately) — 40 round-trips
- A 1000-case random fuzz over spot 50–500, moneyness 0.5–2.0, expiry 0.01–5y, rate –2 to 15%, vol 5–150%, dividend 0–8%
- A moneyness sweep (K = 50 to 200) at fixed sigma
- A volatility sweep covering low (1%–20%) and high (20%–150%) regimes

The solver returns `NaN` for cases where IV is mathematically undefined (deep ITM with no remaining time value), and the test classifies those correctly rather than counting them as failures.

**Numerical Greeks** (`test_accuracy.cpp`): each analytic Greek is compared against its central finite-difference approximation. If the analytic formula has a sign error or wrong coefficient, the FD comparison catches it.

## Key bugs caught and fixed during accuracy testing

These were the bugs the test suite uncovered before reaching 100%:

1. **`is_valid()` rejecting infinity.** Edge cases set `d1 = ±INF` deliberately so that `N(d1)` evaluates to 0 or 1, but the validator used `std::isfinite()` which rejected those inputs. Changed to `!std::isnan()`.

2. **Zero-vol falling through to division by zero.** The guard `vol < 0.0` passed `vol == 0.0` to the main formula which divides by `vol·sqrt(T)`. Split into a strict negative check and a dedicated `vol == 0.0` handler.

3. **IV solver bracket never validated.** The original Newton-Raphson started with a hardcoded `[1e-6, 10.0]` bracket but never checked it actually contained the root. When the Brenner–Subrahmanyam initial guess overshot, bisection would jump to `(1e-6 + 10.0) / 2 = 5.0`. Fixed by evaluating both endpoints first and exponentially expanding `hi` until bracketed.

4. **IV solver getting stuck in flat-vega regions.** Even with a valid bracket, Newton steps could shrink to nothing without converging. Added a stuck-step counter that forces a bisection step after 2 consecutive non-progressing iterations.

5. **No-time-value cases reported as solver failures.** The fuzz test produced cases like `S=368, K=460, T=0.27, q=7.5%` where a deep ITM put on a high-dividend stock has time value of 3e-11 — vega is 2.6e-8, and the IV is mathematically undefined (any sigma in [0, ∞) yields the same price). Added an explicit pre-check: if `price - intrinsic < 1e-10 × max(price, 1)`, return `NaN`.

6. **5-year theta reference value rounded.** The original reference had `0.000334461235` (12 places), but the true value is `0.000334461234554`. Regenerated at full precision.

## Tolerance ladder

Different tests use different tolerances because different parameter regimes have different inherent precision limits. The choices below are documented in the test code, not pulled out of the air:

| Test | Tolerance | Reason |
|---|---|---|
| BSM prices vs reference | 1e-10 relative | Machine epsilon limit for `erfc`-based normal CDF |
| Greeks vs reference | 1e-12 relative | Single-precision arithmetic in shared d1/d2 |
| Put-call parity (random) | 1e-10 absolute | Same as price |
| Greek symmetries | 1e-15 | Should hold to machine precision (literally same code path) |
| IV round-trip (vol ≥ 0.02) | 1e-12 relative | Newton converges to machine precision |
| IV round-trip (vol < 0.02) | 1e-9 absolute | Vega very small; `d sigma / d price` is large |
| Numerical Greeks | 1e-6 to 1e-8 | FD approximation error dominates |

## What's NOT yet tested at this level

These are deliberately deferred to future phases:

- American option pricing (Phase 1 is European-only)
- Heston / SABR / SVI vol models (Phase 2)
- Parallel batch performance benchmarks (separate `benchmarks/` target)
- Python-side accuracy tests (require building the nanobind module first — next step)
