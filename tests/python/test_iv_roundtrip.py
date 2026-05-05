"""Extended IV round-trip coverage on the Python binding (Issue #5).

The basic round-trip on the 20 reference scenarios already lives in
``test_accuracy.py::TestIVAccuracy``. This file adds breadth:

- moneyness sweep (0.8 × S → 1.2 × S) at a fixed expiry
- volatility sweep (0.05 → 1.0) at a fixed strike
- NaN propagation for inputs with no time value

Total assertions added: ~80, all going through the C++ binding so any
regression in `_implied_vol_scalar` / `_implied_vol_batch` will surface
here even if the C++ unit tests still pass.
"""

from __future__ import annotations

import numpy as np
import opticore as oc
import pytest

# ── moneyness sweep ─────────────────────────────────────────────────────────

MONEYNESS_LEVELS = np.linspace(0.80, 1.20, 9)  # 9 strikes around ATM


@pytest.mark.parametrize("moneyness", MONEYNESS_LEVELS, ids=lambda m: f"K/S={m:.2f}")
@pytest.mark.parametrize("kind", ["call", "put"])
def test_iv_roundtrip_moneyness_sweep(moneyness, kind):
    """price(σ) → iv() recovers σ across the moneyness curve."""
    S, T, r, q, sigma = 100.0, 0.5, 0.05, 0.0, 0.20
    K = float(S * moneyness)
    price = oc.price(spot=S, strike=K, expiry=T, rate=r, vol=sigma, kind=kind, div_yield=q)
    solved = oc.iv(price=price, spot=S, strike=K, expiry=T, rate=r, kind=kind, div_yield=q)
    np.testing.assert_allclose(solved, sigma, rtol=1e-9)


# ── vol sweep ───────────────────────────────────────────────────────────────

VOL_LEVELS = [0.05, 0.10, 0.20, 0.40, 0.60, 0.80, 1.00]


@pytest.mark.parametrize("sigma", VOL_LEVELS, ids=lambda s: f"σ={s:.2f}")
@pytest.mark.parametrize("kind", ["call", "put"])
def test_iv_roundtrip_vol_sweep(sigma, kind):
    """price(σ) → iv() recovers σ from very low to very high vol."""
    S, K, T, r, q = 100.0, 100.0, 1.0, 0.05, 0.0
    price = oc.price(spot=S, strike=K, expiry=T, rate=r, vol=sigma, kind=kind, div_yield=q)
    solved = oc.iv(price=price, spot=S, strike=K, expiry=T, rate=r, kind=kind, div_yield=q)
    # Above 0.02 vol the solver hits machine precision; below that, a few
    # ULP of slack matters because the price is in the noise regime.
    if sigma >= 0.02:
        np.testing.assert_allclose(solved, sigma, rtol=1e-9)
    else:
        np.testing.assert_allclose(solved, sigma, atol=1e-9)


# ── moneyness × vol cross sweep ─────────────────────────────────────────────


@pytest.mark.parametrize("moneyness", [0.85, 1.0, 1.15], ids=["OTM", "ATM", "ITM"])
@pytest.mark.parametrize("sigma", [0.10, 0.30, 0.60], ids=["low", "mid", "high"])
@pytest.mark.parametrize("kind", ["call", "put"])
def test_iv_roundtrip_2d_grid(moneyness, sigma, kind):
    """Round-trip on the (moneyness × vol × kind) Cartesian grid."""
    S, T, r, q = 100.0, 1.0, 0.05, 0.02
    K = float(S * moneyness)
    price = oc.price(spot=S, strike=K, expiry=T, rate=r, vol=sigma, kind=kind, div_yield=q)
    solved = oc.iv(price=price, spot=S, strike=K, expiry=T, rate=r, kind=kind, div_yield=q)
    np.testing.assert_allclose(solved, sigma, rtol=1e-9)


# ── NaN propagation ─────────────────────────────────────────────────────────


class TestIVNaNPropagation:
    """No-time-value, arbitrage-violating, and degenerate inputs return NaN."""

    def test_zero_expiry_nan(self):
        """T = 0 has no time value — IV is undefined."""
        result = oc.iv(price=5.0, spot=100, strike=100, expiry=0.0, rate=0.05, kind="call")
        assert np.isnan(result)

    def test_negative_price_nan(self):
        result = oc.iv(price=-1.0, spot=100, strike=100, expiry=0.5, rate=0.05, kind="call")
        assert np.isnan(result)

    def test_below_intrinsic_nan(self):
        """A call quoted below max(S - K*exp(-rT), 0) is arbitrage — no IV solves."""
        # Deep ITM call worth nearly S - K — quoting at $1 is unsolvable
        result = oc.iv(price=1.0, spot=100, strike=50, expiry=0.5, rate=0.05, kind="call")
        assert np.isnan(result)

    def test_above_upper_bound_nan(self):
        """Call > S or put > K is arbitrage — no IV solves."""
        result = oc.iv(price=200.0, spot=100, strike=100, expiry=0.5, rate=0.05, kind="call")
        assert np.isnan(result)

    def test_vectorized_nan_mixed_with_valid(self):
        """A bad row inside an otherwise valid array yields NaN only for that row."""
        S, T, r = 100.0, 0.5, 0.05
        sigma = 0.20
        # Build prices for 5 valid options + 1 bad (negative price)
        strikes = np.array([90.0, 95.0, 100.0, 105.0, 110.0, 100.0])
        good_prices = np.array(
            [
                oc.price(spot=S, strike=float(k), expiry=T, rate=r, vol=sigma, kind="call")
                for k in strikes[:-1]
            ]
        )
        prices = np.concatenate([good_prices, [-1.0]])
        spots = np.full(len(prices), S)
        expiries = np.full(len(prices), T)
        solved = oc.iv(
            price=prices, spot=spots, strike=strikes, expiry=expiries, rate=r, kind="call"
        )
        # First 5 should recover sigma; last is NaN
        np.testing.assert_allclose(solved[:5], sigma, rtol=1e-9)
        assert np.isnan(solved[5])
