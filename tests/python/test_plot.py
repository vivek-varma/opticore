"""Tests for opticore.plot functions."""

import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")  # non-interactive backend for CI

import opticore as oc
from opticore import plot as oc_plot


@pytest.fixture
def enriched_df():
    """Synthetic enriched DataFrame for smile tests."""
    strikes = np.arange(85.0, 116.0)
    rows = []
    for exp in [
        pd.Timestamp("2026-05-01", tz="UTC"),
        pd.Timestamp("2026-06-01", tz="UTC"),
    ]:
        for k in strikes:
            iv = 0.20 + 0.002 * (k - 100) ** 2 / 100  # synthetic smile
            rows.append(
                {
                    "strike": k,
                    "expiry": exp,
                    "kind": "call",
                    "iv": iv,
                    "moneyness": k / 100.0,
                    "underlying_price": 100.0,
                }
            )
    return pd.DataFrame(rows)


class TestSmile:
    """Test oc.plot.smile()."""

    def test_returns_fig_ax_tuple(self, enriched_df):
        import matplotlib.axes
        import matplotlib.figure

        fig, ax = oc_plot.smile(enriched_df)
        assert isinstance(fig, matplotlib.figure.Figure)
        assert isinstance(ax, matplotlib.axes.Axes)

    def test_single_expiry(self, enriched_df):
        fig, ax = oc_plot.smile(enriched_df, expiry="2026-05-01")
        # Should have one line (one expiry)
        assert len(ax.get_lines()) == 1

    def test_moneyness_x(self, enriched_df):
        fig, ax = oc_plot.smile(enriched_df, x="moneyness")
        assert "moneyness" in ax.get_xlabel().lower()

    def test_custom_ax(self, enriched_df):
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        out_fig, out_ax = oc_plot.smile(enriched_df, ax=ax)
        assert out_fig is fig
        assert out_ax is ax

    def test_empty_after_filter_raises(self):
        df = pd.DataFrame(
            {
                "strike": [100],
                "expiry": ["20260501"],
                "kind": ["call"],
                "iv": [np.nan],
            }
        )
        with pytest.raises(ValueError, match="No data"):
            oc_plot.smile(df)


class TestPayoff:
    """Test oc.plot.payoff()."""

    def test_long_call(self):
        import matplotlib.axes
        import matplotlib.figure

        legs = [oc.Leg("call", strike=100, qty=1, premium=5.0)]
        fig, ax = oc_plot.payoff(legs)
        assert isinstance(fig, matplotlib.figure.Figure)
        assert isinstance(ax, matplotlib.axes.Axes)

    def test_straddle(self):
        legs = [
            oc.Leg("call", strike=100, qty=1, premium=5.0),
            oc.Leg("put", strike=100, qty=1, premium=4.0),
        ]
        fig, ax = oc_plot.payoff(legs)
        line = ax.get_lines()[0]
        x, y = line.get_xdata(), line.get_ydata()
        # Straddle has max loss at strike = -(5+4) = -9
        atm_idx = np.argmin(np.abs(x - 100))
        assert y[atm_idx] < 0  # loss at strike

    def test_custom_spot_range(self):
        legs = [oc.Leg("call", strike=100, qty=1, premium=5.0)]
        fig, ax = oc_plot.payoff(legs, spot_range=(50, 150))
        line = ax.get_lines()[0]
        x = line.get_xdata()
        assert x[0] >= 50
        assert x[-1] <= 150

    def test_empty_legs_raises(self):
        with pytest.raises(ValueError, match="At least one leg"):
            oc_plot.payoff([])

    def test_short_put(self):
        legs = [oc.Leg("put", strike=100, qty=-1, premium=4.0)]
        fig, ax = oc_plot.payoff(legs)
        line = ax.get_lines()[0]
        x, y = line.get_xdata(), line.get_ydata()
        # Short put: max profit = premium at high spot
        high_idx = np.argmax(x)
        assert y[high_idx] == pytest.approx(4.0, abs=0.5)

    def test_iron_condor(self):
        legs = [
            oc.Leg("put", strike=90, qty=1, premium=1.0),
            oc.Leg("put", strike=95, qty=-1, premium=2.5),
            oc.Leg("call", strike=105, qty=-1, premium=2.5),
            oc.Leg("call", strike=110, qty=1, premium=1.0),
        ]
        fig, ax = oc_plot.payoff(legs)
        assert fig is not None and ax is not None


class TestGreek:
    """Test oc.plot.greek()."""

    def test_delta_call(self):
        import matplotlib.axes
        import matplotlib.figure

        fig, ax = oc_plot.greek(
            "delta",
            spot_range=(80, 120),
            strike=100,
            expiry=0.5,
            rate=0.05,
            vol=0.2,
            kind="call",
        )
        assert isinstance(fig, matplotlib.figure.Figure)
        assert isinstance(ax, matplotlib.axes.Axes)

    def test_both_kinds(self):
        fig, ax = oc_plot.greek(
            "delta",
            spot_range=(80, 120),
            strike=100,
            expiry=0.5,
            rate=0.05,
            vol=0.2,
            kind="both",
        )
        # "both" should produce 2 lines (call + put) + 1 vertical strike line
        lines = ax.get_lines()
        assert len(lines) >= 2

    def test_all_greeks(self):
        for gname in ("price", "delta", "gamma", "theta", "vega", "rho"):
            fig, ax = oc_plot.greek(
                gname,
                spot_range=(80, 120),
                strike=100,
                expiry=0.5,
                rate=0.05,
                vol=0.2,
            )
            assert fig is not None and ax is not None

    def test_invalid_greek_raises(self):
        with pytest.raises(ValueError, match="greek must be one of"):
            oc_plot.greek(
                "charm",
                spot_range=(80, 120),
                strike=100,
                expiry=0.5,
                rate=0.05,
                vol=0.2,
            )

    def test_custom_ax(self):
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        out_fig, out_ax = oc_plot.greek(
            "gamma",
            spot_range=(80, 120),
            strike=100,
            expiry=0.5,
            rate=0.05,
            vol=0.2,
            ax=ax,
        )
        assert out_fig is fig
        assert out_ax is ax
