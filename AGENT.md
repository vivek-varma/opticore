# AGENT.md — Project context for AI assistants

> **Purpose:** This file is read at the start of every AI-assistant session (Claude Code, Cursor, Windsurf, Aider, etc.) to restore project context. Keep it accurate. Update the "Where we left off" section at the end of each working session.
>
> **Using Claude Code?** Run `ln -s AGENT.md CLAUDE.md` once in the repo root so Claude Code auto-loads this file. The symlink is gitignored (per-user).

---

## TL;DR

**OptiCore** is an open-source options pricing library. C++20 numerical core + Python API via nanobind. Targets retail traders and students. Competes with QuantLib (on ergonomics) and py_vollib (on features). License: Apache-2.0.

**Current phase:** Phase 1 — locked scope, polish & ship.

---

## Phase 1 locked scope

**Exactly 6 public functions + 3 plot helpers. Do not expand without an ADR.**

| Function | Status | Location |
|---|---|---|
| `oc.price(spot, strike, expiry, rate, vol, kind, div_yield)` | ✅ | `python/opticore/__init__.py` |
| `oc.iv(price, spot, strike, expiry, rate, kind, div_yield)` | ✅ | `python/opticore/__init__.py` |
| `oc.greeks(...)` → `GreeksResult` | ✅ | `python/opticore/__init__.py` |
| `oc.greeks_table(...)` → `DataFrame` | ✅ | `python/opticore/__init__.py` |
| `oc.fetch_chain(symbol, provider)` | ✅ | `python/opticore/chain.py` |
| `oc.enrich(chain, rate)` | ✅ | `python/opticore/chain.py` |
| `oc.plot.smile(...)` | ✅ | `python/opticore/plot.py` |
| `oc.plot.payoff(legs)` | ✅ | `python/opticore/plot.py` |
| `oc.plot.greek(name, ...)` | ✅ | `python/opticore/plot.py` |

**Non-goals for Phase 1:** American options, Bachelier/Black-76, vol surfaces (SVI/SABR), Monte Carlo, barriers, Asians, strategy optimizer, non-IBKR data providers.

See [`ROADMAP.md`](ROADMAP.md) for Phase 2+ scope.

---

## Architecture (3 layers)

```
User Python  →  oc.price(), oc.iv(), oc.greeks()
     ↓
Python API    python/opticore/
  __init__.py    — scalar/vectorized dispatch, "call"/"put" parsing
  chain.py       — fetch_chain(), enrich()
  plot.py        — smile, payoff, greek profile
  data/ibkr.py   — IBKR adapter via ib_async (ephemeral)
     ↓
nanobind      src/bindings.cpp
  Zero-copy NumPy ↔ std::span. Internal funcs prefixed with underscore.
     ↓
C++20 core    src/, include/opticore/
  math.hpp    — norm_cdf (std::erfc), norm_pdf, norm_inv (Acklam + Halley)
  bsm.cpp     — BSM pricing, BSMParams shared d1/d2
  jaeckel.cpp — IV solver (Newton-Raphson + bisection — NOT actual Jaeckel yet)
  greeks.cpp  — analytic Greeks, single-pass shared intermediates
```

---

## Locked technical decisions

All major decisions live in [`docs/decisions/`](docs/decisions/) as ADRs. Summary:

- **ADR-0001** — nanobind over pybind11 (faster compile, smaller binary, stable ABI)
- **ADR-0002** — NaN propagation instead of exceptions for numerical edge cases
- **ADR-0003** — Newton-Raphson IV solver now, real Jaeckel "Let's Be Rational" deferred to Phase 2+
- **ADR-0004** — Ephemeral IBKR connections (connect → fetch → disconnect)
- **ADR-0005** — Apache-2.0 license

Do not revisit these without a new ADR.

---

## Testing accuracy (locked)

C++ core: **96 test cases, 1653 assertions passing** on 5 runs with different RNG seeds. Verified by three independent strategies:

1. Reference values (20 hand-verified cases, Python `math.erfc` to 1e-12)
2. Mathematical identities (put-call parity 1000×, Greek symmetries, monotonicity)
3. Self-consistency (IV round-trip, analytic vs finite-difference Greeks, vectorized == scalar)

**Tolerance ladder — do not tighten without understanding the regime:**

| Test | Tolerance |
|---|---|
| BSM prices vs reference | 1e-10 rel |
| Greeks vs reference (C++) | 1e-12 rel |
| Greeks vs reference (Python) | 1e-9 rel (binding layer FP overhead) |
| Put-call parity | 1e-10 abs |
| Greek symmetries | 1e-15 |
| IV round-trip, vol ≥ 0.02 | 1e-12 rel |
| IV round-trip, vol < 0.02 | 1e-9 abs |

Files not to touch without asking:
- `tests/cpp/reference_values.hpp` (hand-verified at full precision)
- The tolerance ladder

---

## Build & test

```bash
# Full C++ build + test
./build_and_test.sh
# Expected: "All tests passed (1653 assertions in 96 test cases)"

# Python install (editable)
pip install -e ".[dev]"

# Python tests
pytest tests/python/ -v

# Run only IV-related C++ tests
./build/opticore_tests "[iv]"
```

Requires: CMake ≥ 3.20, C++20 compiler, Python ≥ 3.10.

---

## Tracking progress

- **GitHub Issues** — all work items tagged `phase-1`. See `https://github.com/vivek-varma/opticore/issues`
- **Milestones** — Phase 1, Phase 2, Phase 3
- **Labels** — `type:feature`, `type:test`, `type:docs`, `type:infra`, `type:bug`, `needs-ibkr`, `good-first-issue`

Script to create the Phase 1 issue set: `scripts/create_issues.sh`.

---

## Questions to ask before doing anything destructive

- Tolerance changes in any test → ask
- Renaming `jaeckel.cpp` → ask (named for the planned algorithm)
- Any feature outside Phase 1's 6-function scope → ask, likely file as Phase 2
- License / Apache-2.0 headers → ask

---

## Gotchas (bitten us before)

- **nanobind ndarray returns** need the `nb::numpy` framework tag, otherwise Python receives DLTensor capsules (`TypeError` on arithmetic). Lines 62, 100, 150 of `src/bindings.cpp`.
- **ib_async in Jupyter** — calls `asyncio.run()` internally, conflicts with the already-running loop. Patched via `_patch_event_loop()` in `python/opticore/data/ibkr.py` which auto-installs `nest_asyncio`.
- **`is_valid()` must accept INF**, not reject it. Edge cases set d1 = ±INF deliberately.
- **Zero-vol branch** must be a dedicated handler, not fall through to the main formula.
- **nanobind error messages** are noisy (template spew). The real error is at the bottom of the output, not the top.

---

## Where we left off

<!-- Update this section at the end of each working session. Keep to 5-10 lines. -->

**2026-04-19** — GitHub repo created and pushed (`vivek-varma/opticore`). Scaffolded 15 Phase 1 issues via `scripts/create_issues.sh` (not yet executed — needs `gh` CLI installed and auth'd first). Now writing project context docs: `AGENT.md`, `ROADMAP.md`, and the first 5 ADRs in `docs/decisions/`. Next: pick one of the Phase 1 issues to work (recommend: mock IBKR adapter or sample chain fixture — both unblock more work).
