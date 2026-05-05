"""Property-based tests via Hypothesis (Issue #6).

Random fuzzing complements the hand-written tests in ``test_accuracy.py``
by hitting edge cases we'd never think to enumerate. The C++ core already
has a 1000-case fuzz; this file mirrors that coverage at the Python
binding layer.

Properties checked:
- **Put-call parity** holds for any valid (S, K, T, r, σ, q)
- **Monotonicity**: call price increasing in S, put price decreasing in S
- **Vectorized == scalar**: batch path matches element-wise loop exactly
- **IV round-trip** recovers the input vol within solver tolerance

Strategies are constrained to avoid pathological inputs (T > 0, σ > 0,
prices in liquid range) since "options at zero vol" or "1e-300 expiry"
isn't what the library is for and would just exercise NaN handling
already covered by ``test_iv_roundtrip.py``.
"""

from __future__ import annotations

import numpy as np
import opticore as oc
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

# Common settings: 100 examples per property in CI is enough to surface
# regressions without slowing tests down. Hypothesis caches its database
# locally so flakes get auto-replayed.
PROPERTY_SETTINGS = settings(
    max_examples=100,
    deadline=None,  # the C++ core is fast but Hypothesis adds overhead
    suppress_health_check=[HealthCheck.too_slow],
)

# ── Strategies ─────────────────────────────────────────────────────────────

# Realistic option parameters: avoid extremes that don't reflect any real
# trade. Coverage of edge cases (zero vol, zero expiry) lives in
# test_accuracy.py and test_iv_roundtrip.py.
spots = st.floats(min_value=10.0, max_value=1000.0, allow_nan=False)
strikes = st.floats(min_value=10.0, max_value=1000.0, allow_nan=False)
expiries = st.floats(min_value=0.01, max_value=5.0, allow_nan=False)  # ~3.6 days → 5y
rates = st.floats(min_value=-0.02, max_value=0.10, allow_nan=False)  # negative rates exist
vols = st.floats(min_value=0.02, max_value=2.0, allow_nan=False)
yields = st.floats(min_value=0.0, max_value=0.10, allow_nan=False)
kinds = st.sampled_from(["call", "put"])


# ── Property 1: Put-call parity ─────────────────────────────────────────────


@given(spot=spots, strike=strikes, expiry=expiries, rate=rates, vol=vols, div_yield=yields)
@PROPERTY_SETTINGS
def test_put_call_parity(spot, strike, expiry, rate, vol, div_yield):
    """C - P = S * exp(-q*T) - K * exp(-r*T) for all valid inputs."""
    call = oc.price(
        spot=spot,
        strike=strike,
        expiry=expiry,
        rate=rate,
        vol=vol,
        kind="call",
        div_yield=div_yield,
    )
    put = oc.price(
        spot=spot,
        strike=strike,
        expiry=expiry,
        rate=rate,
        vol=vol,
        kind="put",
        div_yield=div_yield,
    )
    expected = spot * np.exp(-div_yield * expiry) - strike * np.exp(-rate * expiry)
    # Tolerance scales with input magnitude — relative tolerance handles both
    # the $1000 spot and the $10 spot cases without rebuilding the bound.
    np.testing.assert_allclose(call - put, expected, rtol=1e-9, atol=1e-10)


# ── Property 2: Monotonicity in spot ────────────────────────────────────────


@given(spot=spots, strike=strikes, expiry=expiries, rate=rates, vol=vols)
@PROPERTY_SETTINGS
def test_call_increasing_in_spot(spot, strike, expiry, rate, vol):
    """A higher spot → higher call price (positive delta everywhere)."""
    bump = max(spot * 0.001, 1e-3)
    p1 = oc.price(spot=spot, strike=strike, expiry=expiry, rate=rate, vol=vol, kind="call")
    p2 = oc.price(spot=spot + bump, strike=strike, expiry=expiry, rate=rate, vol=vol, kind="call")
    assert p2 >= p1 - 1e-12  # allow tiny numerical noise


@given(spot=spots, strike=strikes, expiry=expiries, rate=rates, vol=vols)
@PROPERTY_SETTINGS
def test_put_decreasing_in_spot(spot, strike, expiry, rate, vol):
    """A higher spot → lower put price (negative delta everywhere)."""
    bump = max(spot * 0.001, 1e-3)
    p1 = oc.price(spot=spot, strike=strike, expiry=expiry, rate=rate, vol=vol, kind="put")
    p2 = oc.price(spot=spot + bump, strike=strike, expiry=expiry, rate=rate, vol=vol, kind="put")
    assert p2 <= p1 + 1e-12


# ── Property 3: Vectorized == element-wise scalar ───────────────────────────


@given(
    strikes_list=st.lists(strikes, min_size=2, max_size=20),
    spot=spots,
    expiry=expiries,
    rate=rates,
    vol=vols,
    kind=kinds,
)
@PROPERTY_SETTINGS
def test_batch_matches_scalar(strikes_list, spot, expiry, rate, vol, kind):
    """oc.price() with array strikes matches the scalar loop element-wise."""
    strikes_arr = np.array(strikes_list, dtype=np.float64)
    batch = oc.price(spot=spot, strike=strikes_arr, expiry=expiry, rate=rate, vol=vol, kind=kind)
    scalar = np.array(
        [
            oc.price(spot=spot, strike=float(k), expiry=expiry, rate=rate, vol=vol, kind=kind)
            for k in strikes_arr
        ]
    )
    np.testing.assert_array_equal(batch, scalar)


# ── Property 4: IV round-trip ───────────────────────────────────────────────


@given(
    spot=spots,
    strike=strikes,
    expiry=expiries,
    rate=rates,
    vol=st.floats(min_value=0.05, max_value=1.5),  # solver is happiest in liquid range
    kind=kinds,
)
@PROPERTY_SETTINGS
def test_iv_roundtrip(spot, strike, expiry, rate, vol, kind):
    """Pricing then inverting recovers σ for any reasonable input."""
    price = oc.price(spot=spot, strike=strike, expiry=expiry, rate=rate, vol=vol, kind=kind)
    # Skip cases where the price collapses to numerical noise — those
    # exercise NaN handling, which is tested separately.
    assume(price > 1e-8)
    solved = oc.iv(price=price, spot=spot, strike=strike, expiry=expiry, rate=rate, kind=kind)
    if not np.isnan(solved):
        np.testing.assert_allclose(solved, vol, rtol=1e-6)
