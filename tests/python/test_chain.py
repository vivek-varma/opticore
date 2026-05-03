"""Tests for chain enrichment (oc.enrich) using synthetic data."""

from datetime import datetime, timedelta, timezone

import numpy as np
import opticore as oc
import pandas as pd
import pytest


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
                spot=underlying,
                strike=k,
                expiry=tte,
                rate=0.05,
                vol=vol,
                kind=kind,
            )
            # Simulate bid/ask spread
            rows.append(
                {
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
                }
            )

    return pd.DataFrame(rows)


class TestEnrich:
    """Test oc.enrich() with synthetic chain data."""

    def test_adds_expected_columns(self):
        chain = _make_chain()
        enriched = oc.enrich(chain, rate=0.05)

        expected_cols = {
            "mid",
            "tte",
            "moneyness",
            "intrinsic",
            "iv",
            "model_price",
            "delta",
            "gamma",
            "theta",
            "vega",
            "rho",
        }
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
            (enriched["moneyness"] > 0.9) & (enriched["moneyness"] < 1.1) & enriched["iv"].notna()
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
        valid_calls = enriched[(enriched["kind"] == "call") & enriched["delta"].notna()]
        assert (valid_calls["delta"] > 0).all()

    def test_put_delta_negative(self):
        chain = _make_chain()
        enriched = oc.enrich(chain, rate=0.05)
        valid_puts = enriched[(enriched["kind"] == "put") & enriched["delta"].notna()]
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


class TestEnrichPerformance:
    """Lock in vectorized enrich performance (Issue #21)."""

    def test_large_chain_under_budget(self):
        """Enriching a 1000-row chain should complete in well under 1 second.

        With the vectorized batch path, this typically runs in ~2ms. The 1s
        budget is intentionally loose to avoid CI flakiness; if this fails,
        someone has reintroduced a per-row Python loop.
        """
        import time

        # Build a 1000-row synthetic chain (50 strikes × 10 expiries × 2 kinds)
        underlying = 100.0
        rows = []
        now = datetime.now(timezone.utc)
        for d in range(1, 11):
            expiry_dt = now + timedelta(days=30 * d)
            expiry_str = expiry_dt.strftime("%Y%m%d")
            tte = 30 * d / 365.25
            for k in np.linspace(70, 130, 50):
                for kind in ("call", "put"):
                    p = oc.price(
                        spot=underlying,
                        strike=k,
                        expiry=tte,
                        rate=0.05,
                        vol=0.20,
                        kind=kind,
                    )
                    rows.append(
                        {
                            "symbol": "TEST",
                            "strike": k,
                            "expiry": expiry_str,
                            "kind": kind,
                            "bid": max(p * 0.95, 0.01),
                            "ask": p * 1.05,
                            "last": p,
                            "volume": 100,
                            "open_interest": 500,
                            "underlying_price": underlying,
                        }
                    )
        chain = pd.DataFrame(rows)
        assert len(chain) == 1000

        # Warm-up
        _ = oc.enrich(chain.iloc[:10].copy(), rate=0.05)

        t0 = time.perf_counter()
        enriched = oc.enrich(chain, rate=0.05)
        elapsed = time.perf_counter() - t0

        assert elapsed < 1.0, (
            f"enrich() on 1000 rows took {elapsed * 1000:.1f}ms "
            f"(budget: 1000ms). A per-row Python loop may have been reintroduced."
        )
        # Sanity: most rows should solve
        assert enriched["iv"].notna().sum() > 950


class TestFetchChain:
    """Test fetch_chain() dispatch logic (no live IBKR connection)."""

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            oc.fetch_chain("AAPL", provider="bogus_provider_xyz")

    def test_yfinance_rejects_provider_kwargs(self):
        """yfinance accepts no extra kwargs — host/port/client_id are nonsense for it."""
        with pytest.raises(TypeError, match="yfinance provider takes no provider_kwargs"):
            oc.fetch_chain("AAPL", provider="yfinance", port=7497)

    def test_ibkr_provider_kwargs_forwarded(self, monkeypatch):
        """fetch_chain forwards provider_kwargs to fetch_ibkr_chain unchanged."""
        captured = {}

        def fake_fetch(**kwargs):
            captured.update(kwargs)
            return pd.DataFrame()

        import opticore.data.ibkr as ibkr_mod

        monkeypatch.setattr(ibkr_mod, "fetch_ibkr_chain", fake_fetch)
        oc.fetch_chain(
            "AAPL",
            provider="ibkr",
            max_expiries=4,
            strike_count=10,
            host="10.0.0.1",
            port=4001,
            client_id=42,
            market_data_type=4,
        )
        assert captured["symbol"] == "AAPL"
        assert captured["max_expiries"] == 4
        assert captured["strike_count"] == 10
        assert captured["host"] == "10.0.0.1"
        assert captured["port"] == 4001
        assert captured["client_id"] == 42
        assert captured["market_data_type"] == 4

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
