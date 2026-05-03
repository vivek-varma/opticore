"""Tests for the bundled sample chain provider (Issue #9)."""

from __future__ import annotations

import opticore as oc
import pandas as pd
import pytest

EXPECTED_COLUMNS = {
    "symbol",
    "expiry",
    "strike",
    "kind",
    "bid",
    "ask",
    "last",
    "mid",
    "volume",
    "open_interest",
    "underlying_price",
}


class TestSampleProvider:
    def test_fetch_via_dispatcher(self):
        df = oc.fetch_chain(provider="sample", symbol="SPY")
        assert not df.empty
        assert set(df.columns) == EXPECTED_COLUMNS

    def test_default_symbol(self):
        """Provider has a default symbol so a bare call works."""
        from opticore.data.sample import fetch_sample_chain

        df = fetch_sample_chain()
        assert not df.empty
        assert (df["symbol"] == "SPY").all()

    def test_relabels_arbitrary_symbol(self):
        df = oc.fetch_chain(provider="sample", symbol="AAPL")
        # The bundled fixture is SPY-shaped; the symbol column gets relabeled
        # so downstream code that filters by symbol still works.
        assert (df["symbol"] == "AAPL").all()

    def test_expiry_is_timestamp(self):
        df = oc.fetch_chain(provider="sample", symbol="SPY")
        assert pd.api.types.is_datetime64_any_dtype(df["expiry"])

    def test_max_expiries_filter(self):
        df = oc.fetch_chain(provider="sample", symbol="SPY", max_expiries=2)
        assert df["expiry"].nunique() == 2

    def test_strike_count_filter(self):
        narrow = oc.fetch_chain(
            provider="sample", symbol="SPY", strike_count=2, max_expiries=1
        )
        # 2 strikes per side + ATM = at most 5 unique strikes
        assert narrow["strike"].nunique() <= 5

    def test_rejects_provider_kwargs(self):
        """sample provider takes no extras (host/port etc are nonsense)."""
        with pytest.raises(TypeError, match="sample provider takes no provider_kwargs"):
            oc.fetch_chain(provider="sample", symbol="SPY", port=7497)

    def test_unknown_provider_lists_sample(self):
        with pytest.raises(ValueError, match="sample"):
            oc.fetch_chain("AAPL", provider="bogus")

    def test_compatible_with_enrich(self):
        """End-to-end: sample chain → enrich produces IV + Greeks."""
        chain = oc.fetch_chain(provider="sample", symbol="SPY")
        enriched = oc.enrich(chain, rate=0.045, div_yield=0.013)
        for col in ("iv", "delta", "gamma", "theta", "vega", "rho", "theo_price"):
            assert col in enriched.columns, f"missing {col}"
        # Most rows should solve for IV on a clean synthetic chain
        # (deep-OTM contracts with floored bids may not solve — that's OK)
        assert enriched["iv"].notna().sum() > 0.85 * len(enriched)

    def test_compatible_with_parity_check(self):
        chain = oc.fetch_chain(provider="sample", symbol="SPY")
        diag = oc.parity_check(chain, rate=0.045, div_yield=0.013)
        assert not diag.empty
        # The synthetic chain has a small mid jitter, so allow a loose budget.
        # Residuals should still be well under $1 across the board.
        assert diag["parity_residual"].abs().max() < 1.0

    def test_compatible_with_implied_forward(self):
        chain = oc.fetch_chain(provider="sample", symbol="SPY")
        out = oc.implied_forward(chain, rate=0.045)
        assert not out.empty
        # Implied div yield should land near the ~1.3% used at fixture time
        assert (out["implied_div_yield"].between(0.005, 0.025)).all()
