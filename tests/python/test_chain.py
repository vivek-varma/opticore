"""Tests for chain enrichment (oc.enrich) using synthetic data."""

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timedelta, timezone

import opticore as oc


def _make_chain(n_strikes=10, underlying=100.0, expiry_days=30):
    """Build a synthetic option chain DataFrame."""
    now = datetime.now(timezone.utc)
    expiry_dt = now + timedelta(days=expiry_days)
    expiry_str = expiry_dt.strftime("%Y%m%d")

    strikes = np.linspace(85, 115, n_strikes)
    rows = []
    for k in strikes:
        for kind in ("call", "put"):
            # Use BSM to generate realistic prices
            vol = 0.20
            tte = expiry_days / 365.25
            price = oc.price(
                spot=underlying, strike=k, expiry=tte,
                rate=0.05, vol=vol, kind=kind,
            )
            # Simulate bid/ask spread
            rows.append({
                "symbol": "TEST",
                "strike": k,
                "expiry": expiry_str,
                "kind": kind,
                "bid": max(price * 0.95, 0.01),
                "ask": price * 1.05,
                "last": price,
                "volume": 100,
                "open_interest": 500,
                "underlying_price": underlying,
            })

    return pd.DataFrame(rows)


class TestEnrich:
    """Test oc.enrich() with synthetic chain data."""

    def test_adds_expected_columns(self):
        chain = _make_chain()
        enriched = oc.enrich(chain, rate=0.05)

        expected_cols = {"mid", "tte", "moneyness", "intrinsic", "iv",
                         "model_price", "delta", "gamma", "theta", "vega", "rho"}
        assert expected_cols.issubset(set(enriched.columns))

    def test_preserves_original_columns(self):
        chain = _make_chain()
        orig_cols = set(chain.columns)
        enriched = oc.enrich(chain, rate=0.05)
        assert orig_cols.issubset(set(enriched.columns))

    def test_preserves_row_count(self):
        chain = _make_chain(n_strikes=5)
        enriched = oc.enrich(chain, rate=0.05)
        assert len(enriched) == len(chain)

    def test_mid_computed(self):
        chain = _make_chain()
        enriched = oc.enrich(chain, rate=0.05)
        expected_mid = (chain["bid"] + chain["ask"]) / 2.0
        np.testing.assert_allclose(enriched["mid"].values, expected_mid.values, rtol=1e-10)

    def test_tte_positive(self):
        chain = _make_chain(expiry_days=30)
        enriched = oc.enrich(chain, rate=0.05)
        assert (enriched["tte"] > 0).all()

    def test_moneyness(self):
        chain = _make_chain()
        enriched = oc.enrich(chain, rate=0.05)
        expected = chain["strike"] / chain["underlying_price"]
        np.testing.assert_allclose(enriched["moneyness"].values, expected.values)

    def test_intrinsic_call(self):
        chain = _make_chain()
        enriched = oc.enrich(chain, rate=0.05)
        calls = enriched[enriched["kind"] == "call"]
        expected = np.maximum(calls["underlying_price"] - calls["strike"], 0)
        np.testing.assert_allclose(calls["intrinsic"].values, expected.values)

    def test_intrinsic_put(self):
        chain = _make_chain()
        enriched = oc.enrich(chain, rate=0.05)
        puts = enriched[enriched["kind"] == "put"]
        expected = np.maximum(puts["strike"] - puts["underlying_price"], 0)
        np.testing.assert_allclose(puts["intrinsic"].values, expected.values)

    def test_iv_recovers_vol(self):
        """IV should approximately recover the vol used to generate prices."""
        chain = _make_chain(n_strikes=5, expiry_days=60)
        enriched = oc.enrich(chain, rate=0.05)

        # Filter to cases where IV solve should work well (not deep ITM/OTM)
        atm = enriched[
            (enriched["moneyness"] > 0.9) & (enriched["moneyness"] < 1.1)
            & enriched["iv"].notna()
        ]
        # Should recover ~0.20 within a few percent (bid/ask spread distorts slightly)
        assert len(atm) > 0
        assert (atm["iv"] > 0.10).all()
        assert (atm["iv"] < 0.40).all()

    def test_greeks_populated_where_iv_valid(self):
        chain = _make_chain()
        enriched = oc.enrich(chain, rate=0.05)
        valid = enriched[enriched["iv"].notna() & (enriched["iv"] > 0)]
        assert valid["delta"].notna().all()
        assert valid["gamma"].notna().all()
        assert valid["theta"].notna().all()
        assert valid["vega"].notna().all()
        assert valid["rho"].notna().all()

    def test_call_delta_positive(self):
        chain = _make_chain()
        enriched = oc.enrich(chain, rate=0.05)
        valid_calls = enriched[
            (enriched["kind"] == "call") & enriched["delta"].notna()
        ]
        assert (valid_calls["delta"] > 0).all()

    def test_put_delta_negative(self):
        chain = _make_chain()
        enriched = oc.enrich(chain, rate=0.05)
        valid_puts = enriched[
            (enriched["kind"] == "put") & enriched["delta"].notna()
        ]
        assert (valid_puts["delta"] < 0).all()

    def test_does_not_modify_original(self):
        chain = _make_chain()
        original_cols = list(chain.columns)
        original_len = len(chain)
        _ = oc.enrich(chain, rate=0.05)
        assert list(chain.columns) == original_cols
        assert len(chain) == original_len

    def test_custom_price_col(self):
        chain = _make_chain()
        chain["mid"] = (chain["bid"] + chain["ask"]) / 2.0
        enriched = oc.enrich(chain, rate=0.05, price_col="last")
        assert enriched["iv"].notna().any()


class TestFetchChain:
    """Test fetch_chain() dispatch logic (no live IBKR connection)."""

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            oc.fetch_chain("AAPL", provider="yahoo")

    def test_ibkr_import_error(self, monkeypatch):
        """fetch_chain('ibkr') raises ImportError if ib_async not installed."""
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "ib_async":
                raise ImportError("No module named 'ib_async'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        # Need to also clear cached import
        import sys
        sys.modules.pop("ib_async", None)
        sys.modules.pop("opticore.data.ibkr", None)

        with pytest.raises(ImportError, match="ib_async"):
            oc.fetch_chain("AAPL", provider="ibkr")
