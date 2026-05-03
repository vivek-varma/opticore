"""Type stubs for the public OptiCore API.

Overrides the runtime `__init__.py` for type-checkers / IDEs. We ship this
stub (rather than relying on inline hints alone) for two reasons:

1. `greeks_table` has a forward-reference string return type `"pandas.DataFrame"`
   in the .py source because pandas is imported lazily. The stub binds it to
   the real `pandas.DataFrame` so mypy and IDEs can autocomplete columns.
2. The scalar/vectorized dispatch in `price` and `iv` is cleaner to express
   via `@overload` than via the runtime `Union[float, ndarray]` annotations.
"""

from __future__ import annotations

from typing import Any, NamedTuple, Union, overload

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray

from opticore import plot as plot

__version__: str

# ── Public types ────────────────────────────────────────────────────────────

class GreeksResult(NamedTuple):
    price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float

class Leg(NamedTuple):
    kind: str
    strike: float
    qty: int = 1
    premium: float = 0.0

# ── price() ─────────────────────────────────────────────────────────────────

@overload
def price(
    spot: float,
    strike: float,
    expiry: float,
    rate: float,
    vol: float,
    kind: str = ...,
    div_yield: float = ...,
) -> float: ...
@overload
def price(
    spot: ArrayLike,
    strike: ArrayLike,
    expiry: ArrayLike,
    rate: float,
    vol: ArrayLike,
    kind: str = ...,
    div_yield: float = ...,
) -> NDArray[np.float64]: ...

# ── iv() ────────────────────────────────────────────────────────────────────

@overload
def iv(
    price: float,
    spot: float,
    strike: float,
    expiry: float,
    rate: float,
    kind: str = ...,
    div_yield: float = ...,
) -> float: ...
@overload
def iv(
    price: ArrayLike,
    spot: ArrayLike,
    strike: ArrayLike,
    expiry: ArrayLike,
    rate: float,
    kind: str = ...,
    div_yield: float = ...,
) -> NDArray[np.float64]: ...

# ── greeks() ────────────────────────────────────────────────────────────────

def greeks(
    spot: float,
    strike: float,
    expiry: float,
    rate: float,
    vol: float,
    kind: str = ...,
    div_yield: float = ...,
) -> GreeksResult: ...
def greeks_table(
    spot: Union[float, ArrayLike],
    strike: Union[float, ArrayLike],
    expiry: Union[float, ArrayLike],
    rate: float,
    vol: Union[float, ArrayLike],
    kind: str = ...,
    div_yield: float = ...,
) -> pd.DataFrame: ...

# ── Chain ops (re-exported from opticore.chain) ─────────────────────────────

def check_connection(
    host: str = ...,
    port: int = ...,
    client_id: int = ...,
    timeout: float = ...,
) -> dict: ...
def fetch_chain(
    symbol: str,
    provider: str = ...,
    max_expiries: int = ...,
    strike_count: int = ...,
    timeout: float = ...,
    **provider_kwargs: Any,
) -> pd.DataFrame: ...
def enrich(
    chain: pd.DataFrame,
    rate: float = ...,
    div_yield: float = ...,
    price_col: str = ...,
) -> pd.DataFrame: ...
