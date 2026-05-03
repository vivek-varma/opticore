"""Bundled sample chain — works with zero config and no IBKR / yfinance.

Loads a small synthetic SPY chain that ships inside the wheel. Use this for
tutorials, CI smoke tests, or anywhere you want ``oc.fetch_chain`` to
"just work" without external dependencies.

Output schema matches ``ibkr.fetch_ibkr_chain`` and
``yfinance_adapter.fetch_yfinance_chain`` so downstream ``enrich`` /
``parity_check`` / ``implied_forward`` are provider-agnostic.

The data is **synthetic** (BSM-priced with a realistic smile + skew) — it
is internally consistent but does not reflect any real market quote.
"""

from __future__ import annotations

import logging
from importlib import resources

import pandas as pd

logger = logging.getLogger(__name__)

# The bundled fixture only contains this symbol. We accept any symbol
# argument for API parity with live providers but always return the same data.
SAMPLE_SYMBOL = "SPY"

# The fixture was generated with prices/IVs that assume this snapshot date.
# We rebase the `expiry` column relative to "now" on load so that
# (expiry - now) stays equal to the original time-to-expiry — otherwise
# `enrich()` would use a stale tte and produce wonky IVs / parity residuals.
_FIXTURE_AS_OF = pd.Timestamp("2026-04-15", tz="UTC")


def _load_bundled() -> pd.DataFrame:
    """Read the parquet that ships inside the package, rebased to today."""
    pkg = resources.files("opticore.data")
    with resources.as_file(pkg / "sample_chain.parquet") as path:
        df = pd.read_parquet(path)

    # Shift every expiry forward by (now - fixture_as_of) so days-to-expiry
    # is preserved. This makes the synthetic chain "always fresh."
    now = pd.Timestamp.now(tz="UTC")
    delta = now - _FIXTURE_AS_OF
    df = df.copy()
    df["expiry"] = df["expiry"] + delta
    return df


def fetch_sample_chain(
    symbol: str = SAMPLE_SYMBOL,
    max_expiries: int = 6,
    strike_count: int = 20,
    timeout: float = 30.0,  # noqa: ARG001 — accepted for signature parity
) -> pd.DataFrame:
    """Return the bundled sample option chain.

    Parameters
    ----------
    symbol : str
        Ignored except for the ``symbol`` column on the output. The bundled
        fixture is SPY-shaped; pass any string. A warning is logged if it
        differs from the bundled symbol so users know the data is fake.
    max_expiries : int
        Keep only the nearest N expiries (default 6). The fixture has 6.
    strike_count : int
        Number of strikes around ATM on each side (default 20). The fixture
        has 31 strikes total; this filters around the underlying price.
    timeout : float
        Accepted for signature parity with live providers; unused.

    Returns
    -------
    pd.DataFrame
        Same columns as the live providers: symbol, expiry, strike, kind,
        bid, ask, last, mid, volume, open_interest, underlying_price.
    """
    df = _load_bundled()

    if symbol != SAMPLE_SYMBOL:
        logger.warning(
            "sample provider: bundled fixture is %s-shaped; "
            "relabeling rows as %r (data is synthetic, not real %s).",
            SAMPLE_SYMBOL,
            symbol,
            symbol,
        )
        df = df.copy()
        df["symbol"] = symbol

    # ── Filter to nearest max_expiries ──────────────────────────────────
    expiries = sorted(df["expiry"].unique())[:max_expiries]
    df = df[df["expiry"].isin(expiries)]

    # ── Filter to ATM ± strike_count ────────────────────────────────────
    # Underlying is constant across the fixture
    spot = float(df["underlying_price"].iloc[0])
    all_strikes = sorted(df["strike"].unique())
    atm_idx = min(
        range(len(all_strikes)),
        key=lambda i: abs(all_strikes[i] - spot),
    )
    lo = max(0, atm_idx - strike_count)
    hi = min(len(all_strikes), atm_idx + strike_count + 1)
    keep = set(all_strikes[lo:hi])
    df = df[df["strike"].isin(keep)].reset_index(drop=True)

    logger.info(
        "Loaded sample chain: %d rows, %d expiries, %d strikes "
        "(synthetic — see opticore.data.sample)",
        len(df),
        df["expiry"].nunique(),
        df["strike"].nunique(),
    )
    return df
