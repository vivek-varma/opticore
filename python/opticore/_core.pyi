"""Type stubs for the compiled nanobind module `opticore._core`.

These bindings are defined in `src/bindings.cpp`. The underscore prefix is a
convention: nothing here is part of the public API — users call `opticore.price`,
`opticore.iv`, `opticore.greeks`, etc. These stubs exist so mypy and IDEs can
see through the Python wrappers in `opticore/__init__.py` without treating the
C++ module as `Any`.

Could be auto-generated via `python -m nanobind.stubgen -m opticore._core`,
but hand-writing is fine given the small surface (6 functions).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

# ── Scalar ──────────────────────────────────────────────────────────────────

def _bsm_price_scalar(
    spot: float,
    strike: float,
    expiry: float,
    rate: float,
    vol: float,
    div_yield: float = ...,
    is_call: bool = ...,
) -> float: ...

def _implied_vol_scalar(
    price: float,
    spot: float,
    strike: float,
    expiry: float,
    rate: float,
    div_yield: float = ...,
    is_call: bool = ...,
) -> float: ...

def _greeks_scalar(
    spot: float,
    strike: float,
    expiry: float,
    rate: float,
    vol: float,
    div_yield: float = ...,
    is_call: bool = ...,
) -> tuple[float, float, float, float, float, float]:
    """Returns (price, delta, gamma, theta, vega, rho)."""
    ...

# ── Batch (NumPy float64 1-D arrays) ────────────────────────────────────────

def _bsm_price_batch(
    spot: float,
    strike: NDArray[np.float64],
    expiry: NDArray[np.float64],
    rate: float,
    vol: float,
    div_yield: float = ...,
    is_call: bool = ...,
) -> NDArray[np.float64]: ...

def _implied_vol_batch(
    price: NDArray[np.float64],
    spot: NDArray[np.float64],
    strike: NDArray[np.float64],
    expiry: NDArray[np.float64],
    rate: float,
    div_yield: float = ...,
    is_call: NDArray[np.bool_] = ...,
) -> NDArray[np.float64]: ...

def _greeks_batch(
    spot: NDArray[np.float64],
    strike: NDArray[np.float64],
    expiry: NDArray[np.float64],
    rate: float,
    vol: NDArray[np.float64],
    div_yield: float = ...,
    is_call: NDArray[np.bool_] = ...,
) -> tuple[
    NDArray[np.float64],  # price
    NDArray[np.float64],  # delta
    NDArray[np.float64],  # gamma
    NDArray[np.float64],  # theta
    NDArray[np.float64],  # vega
    NDArray[np.float64],  # rho
]: ...
