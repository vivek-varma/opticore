# OptiCore Roadmap

> **Status legend:** ✅ done · 🟡 in progress · ⬜ planned · ❌ explicitly out of scope

This roadmap reflects *intent*, not a promise. Scope for each phase is locked when that phase starts — additions require an ADR in [`docs/decisions/`](docs/decisions/).

---

## Phase 1 — Core pricing + IV + Greeks + IBKR + plots (current)

**Goal:** A usable, well-tested, pip-installable library that a quant can drop into a notebook and get IV + Greeks on a real option chain in a efficient manner

**Target:** 4 weeks from project start.

### Numerical core (C++20) — ✅ done
- ✅ Black-Scholes-Merton pricing (calls, puts, dividends)
- ✅ Implied volatility solver (Newton-Raphson + bisection fallback, see [ADR-0003](docs/decisions/0003-newton-raphson-iv-solver.md))
- ✅ Analytic Greeks: delta, gamma, theta, vega, rho (single-pass)
- ✅ NaN propagation for invalid / no-time-value inputs ([ADR-0002](docs/decisions/0002-nan-propagation-not-exceptions.md))
- ✅ 96 test cases / 1653 assertions, stable across 5 random seeds

### Python API — ✅ done
- ✅ `oc.price()` — scalar & vectorized
- ✅ `oc.iv()` — scalar & vectorized
- ✅ `oc.greeks()` → `GreeksResult` named tuple
- ✅ `oc.greeks_table()` → `pandas.DataFrame`
- ✅ `oc.fetch_chain(symbol, provider)` — dispatcher
- ✅ `oc.enrich(chain, rate)` — adds IV + Greeks columns
- ✅ `oc.check_connection()` — IBKR connectivity test

### IBKR adapter — ✅ done (pending live validation)
- ✅ `fetch_ibkr_chain()` via `ib_async`
- ✅ Jupyter event-loop patch via `nest_asyncio`
- ✅ Ephemeral connection lifecycle ([ADR-0004](docs/decisions/0004-ephemeral-ibkr-connection.md))
- ⬜ Live smoke test on paper account (GH issue)

### Plotting — ✅ done
- ✅ `oc.plot.smile()` — IV smile by expiry
- ✅ `oc.plot.payoff(legs)` — multi-leg payoff diagram
- ✅ `oc.plot.greek(name, ...)` — Greek profile vs spot

### Testing — 🟡 in progress
- ✅ C++ reference-value tests to 1e-12
- ✅ Python accuracy tests mirroring C++ (133 assertions)
- ✅ Python chain + plot tests
- ⬜ Mock IBKR adapter for offline CI
- ⬜ Hypothesis property-based tests
- ⬜ `pytest-benchmark` suite for perf tracking
- ⬜ Coverage gate ≥ 85%

### Packaging / infrastructure — ⬜ planned
- ⬜ GitHub Actions CI (matrix: 3.10–3.13 × linux/macos/windows)
- ⬜ Wheel building via `cibuildwheel`
- ⬜ `.pyi` type stubs + `py.typed` marker
- ⬜ PyPI release (after wheels work)
- ⬜ GitHub Pages docs (mkdocs-material or pdoc)

### Documentation — 🟡 in progress
- ✅ `AGENT.md`, `ROADMAP.md`, ADRs
- ✅ `notebooks/01_quickstart.ipynb`
- ✅ `notebooks/02_ibkr_setup.ipynb`
- ⬜ `notebooks/03_iv_analysis.ipynb`
- ⬜ `notebooks/04_strategies.ipynb`
- ⬜ README polish (badges, honest perf table, install matrix)
- ⬜ Sample chain shipped with the package

### Out of scope for Phase 1 — ❌
- American options (early exercise)
- Bachelier (normal) / Black-76 (futures) models
- Vol surface fitting (SVI, SABR, SSVI)
- Monte Carlo pricing
- Exotics: barriers, Asians, lookbacks
- Non-IBKR data providers
- Portfolio / strategy optimizer
- Web UI / hosted service

### Phase 1 acceptance criteria

Phase 1 is "done" when:
1. `pip install opticore` works from PyPI wheels on py3.10–3.13 × linux/macos.
2. CI green on every push.
3. Coverage ≥ 85% on the Python layer.
4. Live IBKR paper-account smoke test passes end-to-end.
5. README has honest benchmark numbers and renders cleanly on GitHub.
6. All 4 notebooks run offline without an IBKR account.

---

## Phase 2 — Volatility surface & better IV

**Goal:** Move from per-option IV to arbitrage-free surfaces. This is where OptiCore starts to matter for serious users.

### Core
- ⬜ **Real Jaeckel "Let's Be Rational" IV solver** (supersedes Newton-Raphson; ≤ 2 iterations to machine precision)
- ⬜ **SVI** parametric smile fit per expiry
- ⬜ **SSVI** surface fit across expiries
- ⬜ **SABR** (optional — fixed-strike hedgers care)
- ⬜ **Arbitrage detection** (calendar, butterfly) with explicit violation reports
- ⬜ **Forward curve / dividend curve** inference from put-call parity

### API
- ⬜ `oc.fit_surface(chain, model="svi")` → `Surface` object
- ⬜ `surface.iv(K, T)`, `surface.local_vol(K, T)`
- ⬜ `surface.check_arbitrage()` → list of violations

### Visualization
- ⬜ 3D surface plotter
- ⬜ Smile slices by expiry, skew slices by moneyness

### Out of scope — ❌
- Stochastic vol models (Heston — Phase 3)
- Jump diffusion

---

## Phase 3 — Models beyond BSM

**Goal:** Price things BSM can't.

- ⬜ **Heston** stochastic volatility (semi-analytic via characteristic function)
- ⬜ **American options** — Longstaff-Schwartz / CRR binomial
- ⬜ **Barriers** (knock-in / knock-out, continuous & discrete)
- ⬜ **Asians** (arithmetic via Monte Carlo; geometric closed-form)
- ⬜ **Monte Carlo engine** with Sobol + antithetic variates
- ⬜ **Greeks via AAD** (algorithmic differentiation) — if compile time allows

---

## Phase 4 — Ecosystem

**Goal:** Make OptiCore the default glue between data and pricing.

- ⬜ More data providers: Yahoo Finance, Polygon, Deribit (crypto), CBOE DataShop
- ⬜ Historical chain storage (parquet cache)
- ⬜ Strategy builder API (`Spread`, `Butterfly`, `IronCondor` as first-class objects)
- ⬜ Position P&L attribution (decompose into delta, gamma, theta, vega contributions)
- ⬜ Example strategy backtests (covered call, wheel, volatility arb)

---

## Revisions

If scope changes mid-phase, open an ADR in [`docs/decisions/`](docs/decisions/) explaining the trade-off. The roadmap should match reality, not aspiration — if something slips, move it to the next phase here.
