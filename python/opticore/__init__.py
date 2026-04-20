"""
OptiCore — High-performance options pricing, IV solver, and Greeks.

Quick start:
    >>> import opticore as oc
    >>> oc.price(spot=100, strike=105, expiry=0.5, rate=0.05, vol=0.20, kind="call")
    3.444...
    >>> oc.iv(price=3.44, spot=100, strike=105, expiry=0.5, rate=0.05, kind="call")
    0.1998...
    >>> g = oc.greeks(spot=100, strike=105, expiry=0.5, rate=0.05, vol=0.20, kind="call")
    >>> g.delta
    0.4405...
"""

__version__ = "0.1.0"

import numpy as np
from typing import Union, NamedTuple

# Import C++ core (compiled via nanobind)
from opticore._core import (
    _bsm_price_scalar,
    _bsm_price_batch,
    _implied_vol_scalar,
    _implied_vol_batch,
    _greeks_scalar,
    _greeks_batch,
)


# ════════════════════════════════════════════════════════════════════════════
# Public types
# ════════════════════════════════════════════════════════════════════════════

class GreeksResult(NamedTuple):
    """All BSM Greeks computed in a single pass."""

    price: float
    delta: float
    gamma: float
    theta: float  # per calendar day
    vega: float   # per 1% vol move
    rho: float    # per 1% rate move


class Leg(NamedTuple):
    """A single leg of an options strategy for payoff diagrams."""

    kind: str       # "call" or "put"
    strike: float
    qty: int = 1    # positive = long, negative = short
    premium: float = 0.0


# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════

def _parse_kind(kind) -> bool:
    """Convert 'call'/'put' string to bool (True=call)."""
    if isinstance(kind, (bool, np.bool_)):
        return bool(kind)
    if isinstance(kind, str):
        k = kind.lower().strip()
        if k in ("call", "c"):
            return True
        if k in ("put", "p"):
            return False
    raise ValueError(f"kind must be 'call' or 'put', got: {kind!r}")


def _is_scalar(*args) -> bool:
    """Check if all arguments are scalar (not arrays)."""
    return all(np.ndim(a) == 0 for a in args)


# ════════════════════════════════════════════════════════════════════════════
# price()
# ════════════════════════════════════════════════════════════════════════════

def price(
    spot: Union[float, np.ndarray],
    strike: Union[float, np.ndarray],
    expiry: Union[float, np.ndarray],
    rate: float,
    vol: Union[float, np.ndarray],
    kind: str = "call",
    div_yield: float = 0.0,
) -> Union[float, np.ndarray]:
    """Price a European option using Black-Scholes-Merton.

    Parameters
    ----------
    spot : float or array
        Current underlying price.
    strike : float or array
        Strike price.
    expiry : float or array
        Time to expiration in years.
    rate : float
        Risk-free interest rate (continuous compounding).
    vol : float or array
        Annualized volatility.
    kind : str
        'call' or 'put' (default: 'call').
    div_yield : float
        Continuous dividend yield (default: 0.0).

    Returns
    -------
    float or ndarray
        Option price(s).

    Examples
    --------
    >>> import opticore as oc
    >>> oc.price(spot=100, strike=105, expiry=0.5, rate=0.05, vol=0.20, kind="call")
    3.444...

    >>> import numpy as np
    >>> strikes = np.arange(90, 111, dtype=float)
    >>> oc.price(spot=100, strike=strikes, expiry=0.5, rate=0.05, vol=0.20, kind="call")
    array([...])
    """
    is_call = _parse_kind(kind)

    if _is_scalar(spot, strike, expiry, vol):
        return _bsm_price_scalar(
            float(spot), float(strike), float(expiry),
            float(rate), float(vol), float(div_yield), is_call,
        )

    # Vectorized path: broadcast inputs to common shape
    spot_a = np.asarray(spot, dtype=np.float64).ravel()
    strike_a = np.asarray(strike, dtype=np.float64).ravel()
    expiry_a = np.asarray(expiry, dtype=np.float64).ravel()
    vol_a = np.asarray(vol, dtype=np.float64).ravel()

    # If spot/vol are scalar, broadcast to match strike/expiry
    n = max(len(spot_a), len(strike_a), len(expiry_a), len(vol_a))

    if len(spot_a) == 1:
        # Use optimized batch path for scalar spot
        if len(vol_a) == 1:
            strike_a = np.broadcast_to(strike_a, n).copy()
            expiry_a = np.broadcast_to(expiry_a, n).copy()
            return np.asarray(_bsm_price_batch(
                float(spot), strike_a, expiry_a,
                float(rate), float(vol), float(div_yield), is_call,
            ))

    # General case: element-wise
    spot_a = np.broadcast_to(spot_a, n).copy().astype(np.float64)
    strike_a = np.broadcast_to(strike_a, n).copy().astype(np.float64)
    expiry_a = np.broadcast_to(expiry_a, n).copy().astype(np.float64)
    vol_a = np.broadcast_to(vol_a, n).copy().astype(np.float64)

    result = np.empty(n, dtype=np.float64)
    for i in range(n):
        result[i] = _bsm_price_scalar(
            spot_a[i], strike_a[i], expiry_a[i],
            float(rate), vol_a[i], float(div_yield), is_call,
        )
    return result


# ════════════════════════════════════════════════════════════════════════════
# iv()
# ════════════════════════════════════════════════════════════════════════════

def iv(
    price_val: Union[float, np.ndarray],
    spot: Union[float, np.ndarray],
    strike: Union[float, np.ndarray],
    expiry: Union[float, np.ndarray],
    rate: float,
    kind: str = "call",
    div_yield: float = 0.0,
) -> Union[float, np.ndarray]:
    """Compute implied volatility using Jaeckel's 'Let's Be Rational'.

    Achieves full 64-bit machine precision in ≤ 2 iterations.

    Parameters
    ----------
    price_val : float or array
        Observed option price(s).
    spot : float or array
        Current underlying price.
    strike : float or array
        Strike price.
    expiry : float or array
        Time to expiration in years.
    rate : float
        Risk-free rate.
    kind : str
        'call' or 'put'.
    div_yield : float
        Continuous dividend yield.

    Returns
    -------
    float or ndarray
        Implied volatility. NaN where no valid solution exists.

    Examples
    --------
    >>> import opticore as oc
    >>> oc.iv(price=3.44, spot=100, strike=105, expiry=0.5, rate=0.05, kind="call")
    0.1998...
    """
    is_call = _parse_kind(kind)

    if _is_scalar(price_val, spot, strike, expiry):
        return _implied_vol_scalar(
            float(price_val), float(spot), float(strike), float(expiry),
            float(rate), float(div_yield), is_call,
        )

    # Vectorized
    p = np.asarray(price_val, dtype=np.float64).ravel()
    s = np.asarray(spot, dtype=np.float64).ravel()
    k = np.asarray(strike, dtype=np.float64).ravel()
    t = np.asarray(expiry, dtype=np.float64).ravel()

    n = max(len(p), len(s), len(k), len(t))
    p = np.broadcast_to(p, n).copy().astype(np.float64)
    s = np.broadcast_to(s, n).copy().astype(np.float64)
    k = np.broadcast_to(k, n).copy().astype(np.float64)
    t = np.broadcast_to(t, n).copy().astype(np.float64)
    ic = np.full(n, is_call, dtype=bool)

    return np.asarray(_implied_vol_batch(p, s, k, t, float(rate), float(div_yield), ic))


# ════════════════════════════════════════════════════════════════════════════
# greeks()
# ════════════════════════════════════════════════════════════════════════════

def greeks(
    spot: float,
    strike: float,
    expiry: float,
    rate: float,
    vol: float,
    kind: str = "call",
    div_yield: float = 0.0,
) -> GreeksResult:
    """Compute price + all first-order Greeks in a single pass.

    Parameters
    ----------
    spot, strike, expiry, rate, vol, div_yield : float
        Standard BSM parameters.
    kind : str
        'call' or 'put'.

    Returns
    -------
    GreeksResult
        Named tuple with: price, delta, gamma, theta (per day),
        vega (per 1% vol), rho (per 1% rate).

    Examples
    --------
    >>> import opticore as oc
    >>> g = oc.greeks(spot=100, strike=105, expiry=0.5, rate=0.05, vol=0.20, kind="call")
    >>> g.delta
    0.4405...
    """
    is_call = _parse_kind(kind)
    result = _greeks_scalar(
        float(spot), float(strike), float(expiry),
        float(rate), float(vol), float(div_yield), is_call,
    )
    return GreeksResult(*result)


def greeks_table(
    spot: Union[float, np.ndarray],
    strike: Union[float, np.ndarray],
    expiry: Union[float, np.ndarray],
    rate: float,
    vol: Union[float, np.ndarray],
    kind: str = "call",
    div_yield: float = 0.0,
) -> "pd.DataFrame":
    """Compute Greeks for multiple options, returned as a DataFrame.

    Parameters
    ----------
    Same as greeks(), but spot, strike, expiry, vol can be arrays.

    Returns
    -------
    pandas.DataFrame
        Columns: strike, expiry, price, delta, gamma, theta, vega, rho
    """
    import pandas as pd

    is_call = _parse_kind(kind)

    s = np.atleast_1d(np.asarray(spot, dtype=np.float64))
    k = np.atleast_1d(np.asarray(strike, dtype=np.float64))
    t = np.atleast_1d(np.asarray(expiry, dtype=np.float64))
    v = np.atleast_1d(np.asarray(vol, dtype=np.float64))

    n = max(len(s), len(k), len(t), len(v))
    s = np.broadcast_to(s, n).copy().astype(np.float64)
    k = np.broadcast_to(k, n).copy().astype(np.float64)
    t = np.broadcast_to(t, n).copy().astype(np.float64)
    v = np.broadcast_to(v, n).copy().astype(np.float64)
    ic = np.full(n, is_call, dtype=bool)

    price_arr, delta, gamma, theta, vega, rho = _greeks_batch(
        s, k, t, float(rate), v, float(div_yield), ic,
    )

    return pd.DataFrame({
        "strike": k,
        "expiry": t,
        "price": np.asarray(price_arr),
        "delta": np.asarray(delta),
        "gamma": np.asarray(gamma),
        "theta": np.asarray(theta),
        "vega": np.asarray(vega),
        "rho": np.asarray(rho),
    })


# ════════════════════════════════════════════════════════════════════════════
# Re-exports
# ════════════════════════════════════════════════════════════════════════════

# Chain operations (pure Python, no C++ dependency)
from opticore.chain import fetch_chain, enrich, check_connection  # noqa: E402

# Make plot submodule importable
from opticore import plot  # noqa: F401, E402

__all__ = [
    "price",
    "iv",
    "greeks",
    "greeks_table",
    "fetch_chain",
    "enrich",
    "check_connection",
    "GreeksResult",
    "Leg",
    "plot",
    "__version__",
]
