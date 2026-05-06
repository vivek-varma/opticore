"""Type stubs for opticore.plot.

The runtime module imports matplotlib lazily (inside ``_get_plt``) so the
return types in the source are loose. Here we tighten them to
``(Figure, Axes)`` — what mypy/IDEs need to autocomplete on the result.

We `from matplotlib...` import unconditionally in the stub: stubs are
never executed at runtime, only consulted by the type-checker, so this
doesn't drag matplotlib into the import path.
"""

from __future__ import annotations

from typing import Sequence

import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from opticore import Leg

def smile(
    enriched_df: pd.DataFrame,
    expiry: str | pd.Timestamp | None = ...,
    x: str = ...,
    ax: Axes | None = ...,
) -> tuple[Figure, Axes]: ...
def payoff(
    legs: Sequence[Leg],
    spot_range: tuple[float, float] | None = ...,
    num_points: int = ...,
    ax: Axes | None = ...,
) -> tuple[Figure, Axes]: ...
def greek(
    greek_name: str,
    spot_range: tuple[float, float],
    strike: float,
    expiry: float,
    rate: float,
    vol: float,
    kind: str = ...,
    div_yield: float = ...,
    num_points: int = ...,
    ax: Axes | None = ...,
) -> tuple[Figure, Axes]: ...
