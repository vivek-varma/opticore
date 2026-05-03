# ⚡ OptiCore

**High-performance options pricing, IV solver, and Greeks — C++20 core with a Pythonic API.**

[![CI](https://github.com/vivek-varma/opticore/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/vivek-varma/opticore/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://pypi.org/project/opticore/)
[![C++20](https://img.shields.io/badge/C%2B%2B-20-blue.svg)]()

---

## Why OptiCore?

| | OptiCore | QuantLib | py_vollib | FinancePy |
|---|---------|----------|-----------|-----------|
| **Install** | `pip install opticore` | Compile from source + SWIG | `pip install` | `pip install` |
| **Price 10k options** | < 1 ms | ~50 ms | ~200 ms | ~100 ms |
| **IV precision** | 64-bit machine ε | 1e-8 | 64-bit (with Numba) | 1e-6 |
| **API style** | `oc.price(spot=100, ...)` | 15 lines of boilerplate | Function-based | OOP |
| **Greeks in 1 call** | ✅ All 5 | Manual per-Greek | ✅ | ✅ |
| **IBKR integration** | ✅ Built-in | ❌ | ❌ | ❌ |
| **License** | Apache-2.0 | BSD | MIT | GPL-3.0 |

## Quickstart

```bash
pip install opticore
```

```python
import opticore as oc

# Price a European call
price = oc.price(spot=100, strike=105, expiry=0.5, rate=0.05, vol=0.20, kind="call")
# => 3.444

# Implied volatility (Jaeckel's "Let's Be Rational" — full machine precision)
iv = oc.iv(price=3.44, spot=100, strike=105, expiry=0.5, rate=0.05, kind="call")
# => 0.1998

# All Greeks in one pass
g = oc.greeks(spot=100, strike=105, expiry=0.5, rate=0.05, vol=0.20, kind="call")
print(f"Δ={g.delta:.4f}  Γ={g.gamma:.4f}  Θ={g.theta:.4f}  ν={g.vega:.4f}  ρ={g.rho:.4f}")
```

## Vectorized — Price Entire Chains

```python
import numpy as np

strikes = np.arange(90, 111, dtype=float)
prices = oc.price(spot=100, strike=strikes, expiry=0.5, rate=0.05, vol=0.20, kind="call")
# => array of 21 prices, computed in < 0.01 ms
```

## Quick start without IBKR

No account, no API keys, no network — a tiny synthetic SPY chain ships
inside the wheel. Perfect for trying things out:

```python
chain = oc.fetch_chain(provider="sample", symbol="SPY")
enriched = oc.enrich(chain, rate=0.045, div_yield=0.013)
oc.plot.smile(enriched)
```

For ~15-min delayed real data without an IBKR account:

```python
chain = oc.fetch_chain("AAPL", provider="yfinance")
```
```bash
pip install opticore[data-yfinance]
```

## Interactive Brokers Integration

```python
# Fetch a live chain (requires TWS/Gateway running)
chain = oc.fetch_chain("AAPL", provider="ibkr")

# Enrich with IV + Greeks in one call
enriched = oc.enrich(chain, rate=0.045)
# => DataFrame with iv, delta, gamma, theta, vega, rho columns

# Plot the volatility smile
oc.plot.smile(enriched)
```

```bash
pip install opticore[ibkr]  # adds ib_async dependency
```

## Visualization

```python
# IV Smile
oc.plot.smile(enriched, expiry="2026-06-20")

# Strategy payoff diagram
oc.plot.payoff([
    oc.Leg("call", strike=105, qty=1, premium=3.50),
    oc.Leg("put",  strike=95,  qty=1, premium=2.10),
])

# Greeks profile
oc.plot.greek("delta", spot_range=(80, 120), strike=100,
              expiry=0.5, rate=0.05, vol=0.20, kind="both")
```

## Installation Options

```bash
pip install opticore          # Core: pricing, IV, Greeks (requires: numpy, pandas)
pip install opticore[ibkr]    # + Interactive Brokers data
pip install opticore[viz]     # + matplotlib plotting
pip install opticore[all]     # Everything
```

## How It Works

```
Python API  ──→  nanobind  ──→  C++20 Core
(easy)          (zero-copy)     (fast)

oc.price()  ──→  _core.so  ──→  bsm.cpp      (Black-Scholes-Merton)
oc.iv()     ──→  _core.so  ──→  jaeckel.cpp   (Let's Be Rational)
oc.greeks() ──→  _core.so  ──→  greeks.cpp    (analytic, single pass)
```

- **C++20 core** — all numerical work: BSM pricing, Jaeckel IV solver, analytic Greeks
- **nanobind** — zero-copy NumPy ↔ C++ bridge (4× faster compile, 5× smaller binary than pybind11)
- **Python layer** — type handling, DataFrames, plotting, IBKR adapter

## Building from Source

```bash
git clone https://github.com/opticore/opticore.git
cd opticore
pip install -e ".[dev]"
```

### C++ development

```bash
cmake -B build -DOPTICORE_BUILD_TESTS=ON
cmake --build build
ctest --test-dir build
```

### Run Python tests

```bash
pytest tests/python/
```

## Roadmap

- [x] **Phase 1** — BSM pricing, IV, Greeks, IBKR adapter, plots
- [ ] **Phase 2** — Vol surface (SVI, SABR, SSVI), arbitrage detection, 3D visualizer
- [ ] **Phase 3** — Heston model, barriers, Asians, Monte Carlo
- [ ] **Phase 4** — More data providers (Yahoo, Polygon, Deribit), strategy builder

Full details, acceptance criteria, and non-goals: [**ROADMAP.md**](ROADMAP.md).

## Project context & decisions

- [**AGENT.md**](AGENT.md) — project state, architecture, gotchas (read this first if you're jumping in cold)
- [**ROADMAP.md**](ROADMAP.md) — phase-by-phase scope and acceptance criteria
- [**docs/decisions/**](docs/decisions/) — Architecture Decision Records (why nanobind, why NaN-not-exceptions, why Apache-2.0, etc.)

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Apache-2.0 — use freely in commercial and open-source projects.

---

**⭐ Star this repo if you find it useful — it helps others discover it!**
