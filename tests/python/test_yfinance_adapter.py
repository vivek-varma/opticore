"""Tests for the yfinance provider.

Yahoo's API is flaky (rate limits, HTML changes), so we mock yfinance
entirely. This test exercises the adapter's transformation logic and
the schema contract with ``fetch_chain`` / ``enrich``.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest


def _fake_calls() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "contractSymbol": ["AAPL260501C00100000", "AAPL260501C00105000"],
            "lastTradeDate": pd.to_datetime(
                ["2026-04-28 15:00:00+00:00", "2026-04-28 15:01:00+00:00"]
            ),
            "strike": [100.0, 105.0],
            "lastPrice": [3.50, 1.20],
            "bid": [3.45, 1.15],
            "ask": [3.55, 1.25],
            "change": [0.0, 0.0],
            "percentChange": [0.0, 0.0],
            "volume": [100, 50],
            "openInterest": [500, 250],
            "impliedVolatility": [0.20, 0.22],
            "inTheMoney": [True, False],
            "contractSize": ["REGULAR", "REGULAR"],
            "currency": ["USD", "USD"],
        }
    )


def _fake_puts() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "contractSymbol": ["AAPL260501P00100000"],
            "lastTradeDate": pd.to_datetime(["2026-04-28 15:00:00+00:00"]),
            "strike": [100.0],
            "lastPrice": [2.10],
            "bid": [2.05],
            "ask": [2.15],
            "change": [0.0],
            "percentChange": [0.0],
            "volume": [80],
            "openInterest": [400],
            "impliedVolatility": [0.21],
            "inTheMoney": [False],
            "contractSize": ["REGULAR"],
            "currency": ["USD"],
        }
    )


def _make_fake_yf():
    """Return a fake yfinance module shape sufficient for the adapter."""
    chain = SimpleNamespace(calls=_fake_calls(), puts=_fake_puts())

    class FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol
            self.options = ("2026-05-01", "2026-05-08")
            self.fast_info = {"lastPrice": 102.50}
            self.info = {"regularMarketPrice": 102.50}

        def option_chain(self, expiry):
            return chain

    return SimpleNamespace(Ticker=FakeTicker)


def test_fetch_yfinance_returns_expected_schema():
    fake_yf = _make_fake_yf()
    with patch.dict("sys.modules", {"yfinance": fake_yf}):
        from opticore.data.yfinance_adapter import fetch_yfinance_chain

        df = fetch_yfinance_chain("AAPL", max_expiries=1, strike_count=10)

    expected = {
        "symbol",
        "strike",
        "expiry",
        "kind",
        "bid",
        "ask",
        "last",
        "volume",
        "open_interest",
        "underlying_price",
        "mid",
    }
    assert set(df.columns) == expected
    assert (df["symbol"] == "AAPL").all()
    assert set(df["kind"].unique()) <= {"call", "put"}
    # Expiry is a UTC-midnight pd.Timestamp (matches IBKR adapter, see #24)
    assert pd.api.types.is_datetime64_any_dtype(df["expiry"])
    assert df["expiry"].iloc[0] == pd.Timestamp("2026-05-01", tz="UTC")
    # Mid computed from bid/ask
    np.testing.assert_allclose(
        df.loc[df["strike"] == 100.0, "mid"].iloc[0],
        (3.45 + 3.55) / 2,
    )


def test_fetch_yfinance_strike_count_filter():
    """strike_count limits the strike window around ATM."""
    fake_yf = _make_fake_yf()
    with patch.dict("sys.modules", {"yfinance": fake_yf}):
        from opticore.data.yfinance_adapter import fetch_yfinance_chain

        # Underlying = 102.50, strikes available [100, 105]. ATM=105.
        # strike_count=0 → keep only ATM strike per side
        df = fetch_yfinance_chain("AAPL", max_expiries=1, strike_count=0)

    # Only one strike per kind per expiry
    assert len(df) <= 2  # at most 1 call + 1 put


def test_fetch_yfinance_raises_on_unknown_symbol():
    fake = SimpleNamespace(
        Ticker=lambda s: SimpleNamespace(
            options=(),
            fast_info={"lastPrice": 0},
            info={},
            option_chain=lambda e: None,
        )
    )
    with patch.dict("sys.modules", {"yfinance": fake}):
        from opticore.data.yfinance_adapter import fetch_yfinance_chain

        with pytest.raises(ValueError, match="no price"):
            fetch_yfinance_chain("BOGUS")


def test_fetch_chain_routes_yfinance():
    """fetch_chain(provider='yfinance') wires through correctly."""
    fake_yf = _make_fake_yf()
    with patch.dict("sys.modules", {"yfinance": fake_yf}):
        from opticore import fetch_chain

        df = fetch_chain("AAPL", provider="yfinance", max_expiries=1, strike_count=10)
    assert "strike" in df.columns
    assert "underlying_price" in df.columns


def test_fetch_chain_unknown_provider_lists_yfinance():
    from opticore import fetch_chain

    with pytest.raises(ValueError, match="yfinance"):
        fetch_chain("AAPL", provider="bogus")


def test_yfinance_output_compatible_with_enrich():
    """End-to-end: yfinance chain → enrich() produces IV + Greeks."""
    fake_yf = _make_fake_yf()
    with patch.dict("sys.modules", {"yfinance": fake_yf}):
        from opticore import enrich, fetch_chain

        chain = fetch_chain("AAPL", provider="yfinance", max_expiries=1, strike_count=10)
        enriched = enrich(chain, rate=0.05)

    # enrich() adds these columns
    for col in ("iv", "delta", "gamma", "theta", "vega", "rho", "mid", "tte"):
        assert col in enriched.columns, f"missing {col}"
    # Greeks are numeric (NaN allowed where IV doesn't solve)
    assert pd.api.types.is_numeric_dtype(enriched["delta"])
