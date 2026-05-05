"""Performance benchmarks (Issue #7).

These benchmarks back the README's "X faster than Y" claims and catch
performance regressions before they ship. They're slow, so they're
skipped by default (see ``addopts = "-m 'not benchmark'"`` in pyproject).

Run them explicitly with::

    pytest tests/python/test_benchmarks.py -m benchmark --benchmark-only

Or to compare against py_vollib (install with ``pip install py_vollib``)::

    pytest tests/python/test_benchmarks.py -m benchmark \\
           --benchmark-only --benchmark-compare

Each benchmark uses ``pytest-benchmark`` so output is reproducible across
machines and trackable via ``--benchmark-save``.
"""

from __future__ import annotations

import numpy as np
import opticore as oc
import pytest

pytestmark = pytest.mark.benchmark


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def chain_10k():
    """Realistic 10k-option chain (50 strikes × 100 expiries × 2 kinds)."""
    rng = np.random.default_rng(42)
    n = 10_000
    spots = np.full(n, 100.0)
    strikes = rng.uniform(70, 130, n)
    expiries = rng.uniform(0.05, 2.0, n)
    vols = rng.uniform(0.10, 0.50, n)
    return {"spot": spots, "strike": strikes, "expiry": expiries, "vol": vols}


# Optional comparison vs py_vollib if it's installed.
# We only need scalar pricing for the head-to-head — IV solving against
# py_vollib is intentionally omitted because it has different convergence
# semantics that make the comparison apples-to-oranges.
try:
    from py_vollib.black_scholes import black_scholes as pv_price

    HAS_PY_VOLLIB = True
except ImportError:
    HAS_PY_VOLLIB = False
    pv_price = None  # for type-checkers


# ── Bench 1: scalar pricing ─────────────────────────────────────────────────


def test_bench_scalar_price(benchmark):
    """Single BSM price — should be in single-digit microseconds."""
    benchmark(oc.price, spot=100, strike=105, expiry=0.5, rate=0.05, vol=0.20, kind="call")


@pytest.mark.skipif(not HAS_PY_VOLLIB, reason="py_vollib not installed")
def test_bench_scalar_price_pyvollib(benchmark):
    """Reference: py_vollib equivalent."""
    benchmark(pv_price, "c", 100, 105, 0.5, 0.05, 0.20)


# ── Bench 2: 10k batch pricing ──────────────────────────────────────────────


def test_bench_batch_price_10k(benchmark, chain_10k):
    """Vectorized 10k pricing — should be sub-millisecond."""
    benchmark(
        oc.price,
        spot=chain_10k["spot"],
        strike=chain_10k["strike"],
        expiry=chain_10k["expiry"],
        rate=0.05,
        vol=chain_10k["vol"],
        kind="call",
    )


# ── Bench 3: 10k IV solve ───────────────────────────────────────────────────


@pytest.fixture(scope="module")
def chain_10k_with_prices(chain_10k):
    prices = oc.price(
        spot=chain_10k["spot"],
        strike=chain_10k["strike"],
        expiry=chain_10k["expiry"],
        rate=0.05,
        vol=chain_10k["vol"],
        kind="call",
    )
    return {**chain_10k, "price": prices}


def test_bench_batch_iv_10k(benchmark, chain_10k_with_prices):
    """Vectorized IV solve on 10k options."""
    benchmark(
        oc.iv,
        price=chain_10k_with_prices["price"],
        spot=chain_10k_with_prices["spot"],
        strike=chain_10k_with_prices["strike"],
        expiry=chain_10k_with_prices["expiry"],
        rate=0.05,
        kind="call",
    )


# ── Bench 4: 10k Greeks ─────────────────────────────────────────────────────


def test_bench_greeks_table_10k(benchmark, chain_10k):
    """Full price + 5 Greeks on 10k options in one pass."""
    benchmark(
        oc.greeks_table,
        spot=chain_10k["spot"],
        strike=chain_10k["strike"],
        expiry=chain_10k["expiry"],
        rate=0.05,
        vol=chain_10k["vol"],
        kind="call",
    )
