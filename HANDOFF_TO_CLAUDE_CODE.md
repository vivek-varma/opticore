# OptiCore — handoff to Claude Code

## Project
**OptiCore** — open-source options pricing library targeting GitHub stars. C++20 core + Python via nanobind. Audience: students, retail traders. Goal: beat QuantLib on usability and py_vollib on features. License: Apache-2.0.

## Location
`~/Code/opticore` on local Mac (user is `vivekn`).

## Current status: Phase 1 C++ accuracy is locked ✅

**96 test cases / 1653 assertions passing** across 5 stable runs with different random seeds. The C++ math core is verified correct via three independent strategies (reference values, mathematical identities, self-consistency). Ready to move to Python bindings.

## Architecture (3 layers)

```
User Python  →  oc.price(), oc.iv(), oc.greeks()
     ↓
Python API layer  (python/opticore/)
  - __init__.py    : type dispatch (scalar vs vectorized), parses "call"/"put"
  - chain.py       : fetch_chain(), enrich() — adds IV+Greeks to DataFrames
  - plot.py        : smile, payoff, greek profile
  - data/ibkr.py   : IBKR adapter via ib_async (ephemeral connection)
     ↓
nanobind layer  (src/bindings.cpp)
  - Zero-copy NumPy ↔ std::span bridge
  - Underscored internal functions: _bsm_price_scalar, _bsm_price_batch, etc.
     ↓
C++20 core  (src/, include/opticore/)
  - math.hpp    : norm_cdf via std::erfc, norm_pdf, norm_inv (Acklam+Halley)
  - bsm.cpp     : Black-Scholes-Merton pricing, BSMParams shared d1/d2 struct
  - jaeckel.cpp : IV solver — Newton-Raphson + bisection fallback (NOT actual Jaeckel)
  - greeks.cpp  : analytic Greeks, single-pass shared intermediates
```

## Phase 1 lean scope (decided, do not expand)

6 functions only: `oc.price()`, `oc.iv()`, `oc.greeks()`, `oc.greeks_table()`, `oc.fetch_chain()`, `oc.enrich()` + 3 plot functions (smile, payoff, greek profile). Black-Scholes-Merton only. European options only. No American, no Bachelier, no Black-76. 4-week delivery target.

## Key technical decisions

- **nanobind over pybind11** — 4× faster compile, 5× smaller binary, stable ABI
- **ib_async over ib_insync** — original ib_insync maintainer deceased 2024
- **Apache-2.0 license** — friendlier than FinancePy's GPL, more permissive than QuantLib's BSD
- **Newton-Raphson IV solver instead of actual Jaeckel** — guarantees self-consistency by inverting our own bsm_price; full Jaeckel is Phase 2 if needed
- **Single-pass Greeks** — compute d1/d2 once, derive all 6 outputs
- **Edge cases return NaN/INF, never throw** — numerical code, exceptions are too expensive
- **Vectorized batch API as core differentiator** — one call prices entire chain
- **Ephemeral IBKR connection** — no persistent state, simpler for retail users
- **Filename note** — `jaeckel.cpp` is named for the planned algorithm but currently implements Newton-Raphson. Don't rename until/unless real Jaeckel is implemented.

## Bugs found and fixed during accuracy testing

1. **`is_valid()` rejected INF.** Edge cases set d1 = ±INF deliberately so N(d1) → 0 or 1. Was using `isfinite()`, fixed to `!isnan()`.

2. **Zero-vol division by zero.** Guard `vol < 0.0` passed `vol == 0.0` to main formula. Split into strict negative check + dedicated `vol == 0.0` handler.

3. **IV solver bracket never validated.** Newton started with hardcoded `[1e-6, 10.0]` without checking the root was inside. Bisection would jump to 5.0 when initial guess overshot. Fixed by evaluating both endpoints first and exponentially expanding `hi` until bracketed.

4. **IV solver stuck in flat-vega regions.** Added stuck-step counter that forces bisection after 2 consecutive non-progressing iterations.

5. **No-time-value cases reported as solver failures.** Cases like `S=368, K=460, T=0.27, q=7.5%` produce a deep ITM put with time value of 3e-11 — vega is 2.6e-8 and IV is mathematically undefined. Added explicit pre-check: if `price - intrinsic < 1e-10 × max(price, 1)`, return NaN.

6. **5-year theta reference value rounded.** Was `0.000334461235` (12 places), true value is `0.000334461234554`. Regenerated at full precision in `tests/cpp/reference_values.hpp`.

7. **Catch2 INFO macro can't take ternary.** `INFO(is_call ? "Call" : "Put")` fails to compile. Wrap in `std::string(...)`.

## Test suite layout (96 cases / 1653 assertions)

```
tests/cpp/
├── reference_values.hpp       # 20 hand-verified scenarios, ATM/ITM/OTM, 1M-5Y
├── test_bsm.cpp               # 20 original tests (Hull, parity, edge cases)
├── test_accuracy.cpp          # 41 cases / 672 assertions, 8 categories
├── test_pricing_accuracy.cpp  # call/put against reference table to 1e-10
├── test_iv_accuracy.cpp       # round-trip + 1000-case fuzz + sweeps
└── test_greeks_accuracy.cpp   # all 6 Greeks vs reference, calls + puts
```

### Three independent verification strategies (every formula tested by ≥2)

1. **Reference values** — 20 cases × (price + 6 Greeks) × (call + put) verified against Python `math.erfc` to 1e-12
2. **Mathematical identities** — put-call parity (1000 random cases), Greek symmetries (gamma_call==gamma_put, etc.), monotonicity sweeps
3. **Self-consistency** — IV round-trip (1000 random + moneyness/vol sweeps), analytic Greeks vs central finite differences, vectorized batch == scalar exactly

### Tolerance ladder (documented in code)

| Test | Tolerance | Why |
|---|---|---|
| BSM prices vs reference | 1e-10 relative | Machine epsilon for erfc |
| Greeks vs reference | 1e-12 relative | Shared d1/d2 arithmetic |
| Put-call parity | 1e-10 absolute | Same as price |
| Greek symmetries | 1e-15 | Identical code path |
| IV round-trip vol≥0.02 | 1e-12 relative | Newton converges to machine precision |
| IV round-trip vol<0.02 | 1e-9 absolute | Vega tiny, d sigma/d price large |
| Numerical Greeks | 1e-6 to 1e-8 | FD approximation error dominates |

## Files NOT to touch unless asked

- `tests/cpp/reference_values.hpp` — values are hand-verified at full precision; regenerate via Python `math.erfc`, never round
- Tolerance ladder above — already calibrated, don't tighten without understanding the regime
- License headers / Apache-2.0 — locked decision
- Phase 1 scope (6 functions) — locked decision, do not add features

## How to verify the C++ core works

```bash
cd ~/Code/opticore
./build_and_test.sh
```

Expected last line: `All tests passed (1653 assertions in 96 test cases)`.

First build takes 1-2 min while CMake fetches Catch2 v3.5.4. Requires cmake ≥ 3.20 and a C++20 compiler.

## Next phase: Python bindings

The C++ core is verified. Next steps in priority order:

1. **Install build deps** — `pip install nanobind scikit-build-core numpy pandas`
2. **Build the Python module** — `pip install -e .` from project root. This invokes scikit-build-core which calls CMake with `OPTICORE_BUILD_PYTHON=ON`, compiles `src/bindings.cpp` against the static `opticore_core` library, and produces `_core.so` inside the package.
3. **Run existing Python tests** — `pytest tests/python/test_pricing.py -v`
4. **Add a Python-side accuracy test** that mirrors the C++ `reference_values.hpp` table. This catches issues in the binding layer specifically (type conversions, NumPy contiguity, NaN propagation, scalar/array dispatch in `__init__.py`).
5. **Verify vectorized path matches scalar** — call `oc.price()` with both float and ndarray inputs of the same values, results must be identical.
6. **Once Python is verified end-to-end**, move to the IBKR adapter (Phase 1 item 5) and plotting (Phase 1 item 6).

## Things to watch out for during Python bindings phase

- **NaN propagation** — C++ returns NaN for arbitrage/no-time-value/invalid inputs. Python wrapper must NOT convert these to exceptions or zeros. The `oc.iv()` API specifically must return NaN for undefined cases so users can filter chains.
- **Array contiguity** — nanobind requires `nb::c_contig` arrays. If a user passes a sliced/strided NumPy array, we should `np.ascontiguousarray()` it in the Python wrapper, not error out.
- **Scalar vs 0-d array** — `np.float64(5.0)` is technically an ndarray with `ndim==0`. The dispatch in `__init__.py` uses `np.ndim(a) == 0` which handles this correctly, but verify in tests.
- **The `kind` parameter** — accepts strings `"call"/"put"/"c"/"p"` (any case) and bools. Normalize via `_parse_kind()` helper.
- **Default `div_yield=0.0`** must propagate through all 6 functions consistently.
- **Compile errors are noisy** — nanobind error messages are long because of templates. The actual error is usually near the bottom of the spew, not the top.

## Questions to ask the user before doing anything destructive

- Before changing tolerances in any test
- Before renaming `jaeckel.cpp` (it's intentionally named for the planned algorithm)
- Before adding any feature outside Phase 1's 6-function scope
- Before changing the license or Apache-2.0 headers

## Useful one-liners for the C++ core

```bash
# Run only IV tests
./build/opticore_tests "[iv]"

# Run only reference value tests
./build/opticore_tests "[reference]"

# Run with random seed for reproducibility
./build/opticore_tests --rng-seed 42

# Verbose output
./build/opticore_tests -v high

# List all test cases
./build/opticore_tests --list-tests
```

## Project file inventory (after handoff)

```
opticore/
├── .github/workflows/ci.yml
├── CMakeLists.txt              # builds C++ core, nanobind module, tests
├── CMakePresets.json
├── pyproject.toml              # scikit-build-core + nanobind
├── README.md                   # landing page with comparison table
├── LICENSE                     # Apache-2.0
├── CHANGELOG.md
├── CONTRIBUTING.md
├── TEST_RESULTS.md             # accuracy verification documentation
├── build_and_test.sh           # one-command build+test
│
├── include/opticore/
│   ├── math.hpp                # constants, norm_cdf, norm_pdf, norm_inv
│   ├── bsm.hpp                 # BSMParams struct, scalar+batch pricing API
│   ├── jaeckel.hpp             # IV solver API (Newton-Raphson currently)
│   └── greeks.hpp              # GreeksResult struct, single-pass API
│
├── src/
│   ├── bsm.cpp                 # BSM impl with edge cases
│   ├── jaeckel.cpp             # Newton-Raphson + bisection IV solver
│   ├── greeks.cpp              # analytic Greeks single-pass
│   └── bindings.cpp            # nanobind module
│
├── python/opticore/
│   ├── __init__.py             # price, iv, greeks, greeks_table, GreeksResult, Leg
│   ├── chain.py                # fetch_chain dispatcher, enrich
│   ├── plot.py                 # smile, payoff, greek
│   └── data/
│       ├── __init__.py
│       └── ibkr.py             # IBKR adapter via ib_async
│
├── tests/
│   ├── cpp/
│   │   ├── reference_values.hpp
│   │   ├── test_bsm.cpp
│   │   ├── test_accuracy.cpp
│   │   ├── test_pricing_accuracy.cpp
│   │   ├── test_iv_accuracy.cpp
│   │   └── test_greeks_accuracy.cpp
│   └── python/
│       ├── conftest.py
│       └── test_pricing.py
│
└── notebooks/
    └── 01_quickstart.ipynb
```

Total ~2,600 LOC: C++ ~1,400 + Python ~1,100 + config ~280.
