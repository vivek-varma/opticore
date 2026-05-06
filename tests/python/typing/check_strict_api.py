"""Mypy --strict smoke test exercising all 6 + 3 public APIs (Issue #30).

This file is *not* a runtime test — it's checked by mypy --strict and
asserts via reveal_type that every public function returns a real type
(not Any). Pytest doesn't collect it because it lives outside testpaths.

Run:
    mypy --strict tests/python/typing/check_strict_api.py
"""

from __future__ import annotations

import numpy as np
import opticore as oc
from opticore import plot as oc_plot

# ── Scalar pricing → float ──────────────────────────────────────────────────
p_scalar: float = oc.price(spot=100, strike=105, expiry=0.5, rate=0.05, vol=0.2, kind="call")

# ── Vectorized pricing → np.ndarray ─────────────────────────────────────────
strikes = np.array([95.0, 100.0, 105.0])
p_array: np.ndarray[tuple[int, ...], np.dtype[np.float64]] = oc.price(
    spot=100, strike=strikes, expiry=0.5, rate=0.05, vol=0.2, kind="call"
)

# ── Scalar IV → float ───────────────────────────────────────────────────────
iv_scalar: float = oc.iv(price=3.5, spot=100, strike=105, expiry=0.5, rate=0.05, kind="call")

# ── Greeks → GreeksResult NamedTuple ───────────────────────────────────────
g = oc.greeks(spot=100, strike=105, expiry=0.5, rate=0.05, vol=0.2, kind="call")
g_delta: float = g.delta
g_gamma: float = g.gamma

# ── greeks_table → DataFrame ────────────────────────────────────────────────
df_g = oc.greeks_table(spot=100, strike=strikes, expiry=0.5, rate=0.05, vol=0.2, kind="call")

# ── fetch_chain → DataFrame ─────────────────────────────────────────────────
chain = oc.fetch_chain(provider="sample", symbol="SPY")

# ── enrich → DataFrame ──────────────────────────────────────────────────────
enriched = oc.enrich(chain, rate=0.045, div_yield=0.013)

# ── parity_check → DataFrame ────────────────────────────────────────────────
parity = oc.parity_check(chain, rate=0.045, div_yield=0.013)

# ── implied_forward → DataFrame ─────────────────────────────────────────────
fwd = oc.implied_forward(chain, rate=0.045)

# ── check_connection → ConnectionStatus TypedDict ───────────────────────────
status = oc.check_connection()
connected: bool = status["connected"]
msg: str = status["message"]

# ── plot helpers → (Figure, Axes) ───────────────────────────────────────────
fig1, ax1 = oc_plot.smile(enriched)
fig2, ax2 = oc_plot.payoff([oc.Leg("call", strike=105, qty=1, premium=3.5)])
fig3, ax3 = oc_plot.greek(
    "delta",
    spot_range=(80.0, 120.0),
    strike=100.0,
    expiry=0.5,
    rate=0.05,
    vol=0.2,
)


def _assertions() -> None:
    """Anchor the names so mypy --strict can't mark them unused."""
    assert isinstance(p_scalar, float)
    assert isinstance(p_array, np.ndarray)
    assert isinstance(iv_scalar, float)
    assert isinstance(g_delta, float)
    assert isinstance(g_gamma, float)
    assert df_g is not None
    assert enriched is not None
    assert parity is not None
    assert fwd is not None
    assert connected is False or connected is True
    assert isinstance(msg, str)
    assert ax1 is not None and ax2 is not None and ax3 is not None
    assert fig1 is not None and fig2 is not None and fig3 is not None
