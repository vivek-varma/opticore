"""Tests for opticore Python API."""

import numpy as np
import pytest


@pytest.fixture
def oc():
    """Import opticore."""
    import opticore
    return opticore


class TestPrice:
    """Test oc.price() function."""

    def test_atm_call(self, oc):
        """ATM call: S=K=100, T=1, r=5%, vol=20%."""
        p = oc.price(spot=100, strike=100, expiry=1.0, rate=0.05, vol=0.20, kind="call")
        assert abs(p - 10.4506) < 0.01

    def test_put_call_parity(self, oc):
        """Call - Put = S*exp(-qT) - K*exp(-rT)."""
        S, K, T, r, vol, q = 100, 105, 1.0, 0.05, 0.25, 0.02
        call = oc.price(spot=S, strike=K, expiry=T, rate=r, vol=vol, kind="call", div_yield=q)
        put = oc.price(spot=S, strike=K, expiry=T, rate=r, vol=vol, kind="put", div_yield=q)
        lhs = call - put
        rhs = S * np.exp(-q * T) - K * np.exp(-r * T)
        assert abs(lhs - rhs) < 1e-10

    def test_vectorized_strikes(self, oc):
        """Vectorized pricing with array of strikes."""
        strikes = np.arange(90.0, 111.0)
        prices = oc.price(spot=100, strike=strikes, expiry=0.5, rate=0.05, vol=0.20, kind="call")
        assert isinstance(prices, np.ndarray)
        assert len(prices) == len(strikes)
        assert all(np.isfinite(prices))
        # Prices should decrease as strike increases (for calls)
        assert all(np.diff(prices) < 0)

    def test_zero_expiry(self, oc):
        """At expiry: call = max(S-K, 0)."""
        assert oc.price(spot=105, strike=100, expiry=0.0, rate=0.05, vol=0.20, kind="call") == pytest.approx(5.0)
        assert oc.price(spot=95, strike=100, expiry=0.0, rate=0.05, vol=0.20, kind="call") == pytest.approx(0.0)

    def test_put_positive(self, oc):
        """OTM put has positive value."""
        p = oc.price(spot=100, strike=95, expiry=0.5, rate=0.05, vol=0.20, kind="put")
        assert p > 0


class TestIV:
    """Test oc.iv() function."""

    def test_round_trip_atm(self, oc):
        """Price → IV → should recover original vol."""
        vol = 0.25
        p = oc.price(spot=100, strike=100, expiry=1.0, rate=0.05, vol=vol, kind="call")
        solved = oc.iv(price_val=p, spot=100, strike=100, expiry=1.0, rate=0.05, kind="call")
        assert abs(solved - vol) < 1e-8

    def test_round_trip_otm_put(self, oc):
        """Round-trip for OTM put."""
        vol = 0.30
        p = oc.price(spot=100, strike=85, expiry=0.5, rate=0.05, vol=vol, kind="put")
        solved = oc.iv(price_val=p, spot=100, strike=85, expiry=0.5, rate=0.05, kind="put")
        assert abs(solved - vol) < 1e-6

    def test_negative_price_returns_nan(self, oc):
        """Negative price should return NaN."""
        result = oc.iv(price_val=-1.0, spot=100, strike=100, expiry=1.0, rate=0.05, kind="call")
        assert np.isnan(result)

    def test_vectorized(self, oc):
        """Vectorized IV solve."""
        vols = np.array([0.15, 0.20, 0.25, 0.30, 0.35])
        prices = np.array([
            oc.price(spot=100, strike=100, expiry=1.0, rate=0.05, vol=v, kind="call")
            for v in vols
        ])
        solved = oc.iv(
            price_val=prices, spot=np.full(5, 100.0),
            strike=np.full(5, 100.0), expiry=np.full(5, 1.0),
            rate=0.05, kind="call",
        )
        np.testing.assert_allclose(solved, vols, atol=1e-6)


class TestGreeks:
    """Test oc.greeks() function."""

    def test_returns_named_tuple(self, oc):
        """greeks() returns GreeksResult with all fields."""
        g = oc.greeks(spot=100, strike=100, expiry=1.0, rate=0.05, vol=0.20, kind="call")
        assert hasattr(g, "price")
        assert hasattr(g, "delta")
        assert hasattr(g, "gamma")
        assert hasattr(g, "theta")
        assert hasattr(g, "vega")
        assert hasattr(g, "rho")

    def test_call_delta_range(self, oc):
        """Call delta should be between 0 and 1."""
        g = oc.greeks(spot=100, strike=100, expiry=1.0, rate=0.05, vol=0.20, kind="call")
        assert 0 < g.delta < 1

    def test_put_delta_negative(self, oc):
        """Put delta should be negative."""
        g = oc.greeks(spot=100, strike=100, expiry=1.0, rate=0.05, vol=0.20, kind="put")
        assert -1 < g.delta < 0

    def test_gamma_positive(self, oc):
        """Gamma should always be positive."""
        g = oc.greeks(spot=100, strike=100, expiry=1.0, rate=0.05, vol=0.20, kind="call")
        assert g.gamma > 0

    def test_theta_negative(self, oc):
        """Theta should be negative (time decay)."""
        g = oc.greeks(spot=100, strike=100, expiry=1.0, rate=0.05, vol=0.20, kind="call")
        assert g.theta < 0

    def test_price_matches_bsm(self, oc):
        """Price from greeks() should match price()."""
        p1 = oc.price(spot=100, strike=105, expiry=0.5, rate=0.05, vol=0.25, kind="call")
        g = oc.greeks(spot=100, strike=105, expiry=0.5, rate=0.05, vol=0.25, kind="call")
        assert abs(p1 - g.price) < 1e-12


class TestGreeksTable:
    """Test oc.greeks_table() function."""

    def test_returns_dataframe(self, oc):
        """greeks_table() returns a pandas DataFrame."""
        import pandas as pd
        strikes = np.arange(90.0, 111.0)
        df = oc.greeks_table(spot=100, strike=strikes, expiry=0.5, rate=0.05, vol=0.20, kind="call")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == len(strikes)
        assert "delta" in df.columns
        assert "gamma" in df.columns

    def test_delta_decreases_with_strike(self, oc):
        """For calls, delta decreases as strike increases."""
        strikes = np.arange(80.0, 121.0)
        df = oc.greeks_table(spot=100, strike=strikes, expiry=0.5, rate=0.05, vol=0.20, kind="call")
        assert all(np.diff(df["delta"]) < 0)
