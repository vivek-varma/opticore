"""Yahoo Finance options chain adapter (no-account fallback).

Fetches delayed (~15-min) US equity option chains via the unofficial
``yfinance`` library. Useful for tutorials, CI, and any setup where
the user doesn't want to maintain an IBKR account.

Output schema matches ``ibkr.fetch_ibkr_chain`` so ``enrich()`` is provider-agnostic.

Limitations
-----------
- Unofficial Yahoo scraper — occasionally breaks when Yahoo changes HTML
- ~15-minute delayed quotes only
- Yahoo ToS forbids redistribution; fetch at runtime, never commit captured data
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def fetch_yfinance_chain(
    symbol: str,
    max_expiries: int = 6,
    strike_count: int = 20,
    timeout: float = 30.0,
) -> pd.DataFrame:
    """Fetch an option chain from Yahoo Finance.

    Parameters
    ----------
    symbol : str
        Underlying ticker (e.g. ``"AAPL"``, ``"SPY"``).
    max_expiries : int
        Number of nearest expiries to fetch (default: 6).
    strike_count : int
        Number of strikes around ATM on each side (default: 20).
        i.e. returned strike count is roughly ``2 * strike_count + 1``.
    timeout : float
        Per-request HTTP timeout passed to yfinance (default: 30s).

    Returns
    -------
    pd.DataFrame
        Columns: ``symbol, strike, expiry, kind, bid, ask, last,
        volume, open_interest, underlying_price, mid``.
        ``expiry`` is a ``YYYYMMDD`` string (matches the IBKR adapter).

    Raises
    ------
    ImportError
        If yfinance is not installed (``pip install opticore[data-yfinance]``).
    ValueError
        If the symbol has no listed options or Yahoo returns no underlying price.
    """
    try:
        import yfinance as yf
    except ImportError as e:
        raise ImportError(
            "yfinance is required for the yfinance provider. "
            "Install with: pip install opticore[data-yfinance]"
        ) from e

    tk = yf.Ticker(symbol)

    # ── Underlying price ─────────────────────────────────────────────────
    def _coerce_price(v: object) -> float:
        try:
            f = float(v)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return float("nan")
        return f if f > 0 else float("nan")

    underlying_price: float = float("nan")
    try:
        # fast_info is the modern path; falls back to .info if missing
        fi = tk.fast_info
        underlying_price = _coerce_price(
            fi.get("lastPrice") or fi.get("last_price") or fi.get("regularMarketPrice")
        )
    except Exception:
        pass

    if np.isnan(underlying_price):
        try:
            info = tk.info or {}
            underlying_price = _coerce_price(
                info.get("regularMarketPrice") or info.get("currentPrice")
            )
        except Exception:
            pass

    if np.isnan(underlying_price):
        raise ValueError(
            f"yfinance returned no price for {symbol!r}. "
            f"Check the ticker symbol or your network connection."
        )

    # ── Expiries ─────────────────────────────────────────────────────────
    expiries = list(tk.options or ())
    if not expiries:
        raise ValueError(f"No options found for {symbol!r} on Yahoo Finance.")
    expiries = expiries[:max_expiries]

    # ── Walk expiries, build rows ────────────────────────────────────────
    rows: list[dict] = []

    def _normalize_expiry(s: str) -> pd.Timestamp:
        """yfinance gives 'YYYY-MM-DD'. Return UTC midnight Timestamp."""
        return pd.Timestamp(s, tz="UTC")

    def _safe_int(v: object) -> int:
        """Coerce a possibly-NaN/None field to a non-negative int."""
        try:
            f = float(v)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0
        if not np.isfinite(f) or f < 0:
            return 0
        return int(f)

    def _row(r: pd.Series, kind: str, exp_norm: str) -> dict:
        bid = r.get("bid")
        ask = r.get("ask")
        last = r.get("lastPrice")
        # Yahoo uses 0.0 (not NaN) for missing bid/ask. Treat as missing
        # so downstream `enrich()` can mid-fallback to last.
        bid_v = float(bid) if bid and bid > 0 else np.nan
        ask_v = float(ask) if ask and ask > 0 else np.nan
        last_v = float(last) if last and last > 0 else np.nan
        return {
            "symbol": symbol,
            "strike": float(r["strike"]),
            "expiry": exp_norm,
            "kind": kind,
            "bid": bid_v,
            "ask": ask_v,
            "last": last_v,
            "volume": _safe_int(r.get("volume")),
            "open_interest": _safe_int(r.get("openInterest")),
            "underlying_price": underlying_price,
        }

    for exp in expiries:
        exp_norm = _normalize_expiry(exp)
        try:
            chain = tk.option_chain(exp)
        except Exception as e:
            # Skip an expiry that fails rather than abort the whole fetch
            logger.warning("yfinance: skipping expiry %s (%s)", exp, e.__class__.__name__)
            continue

        for df, kind in ((chain.calls, "call"), (chain.puts, "put")):
            if df is None or df.empty:
                continue
            # Filter strikes to ATM ± strike_count
            strikes = sorted(df["strike"].unique())
            if not strikes:
                continue
            atm_idx = min(
                range(len(strikes)),
                key=lambda i: abs(strikes[i] - underlying_price),
            )
            lo = max(0, atm_idx - strike_count)
            hi = min(len(strikes), atm_idx + strike_count + 1)
            keep = set(strikes[lo:hi])
            sub = df[df["strike"].isin(keep)]

            for _, r in sub.iterrows():
                rows.append(_row(r, kind, exp_norm))

    if not rows:
        raise ValueError(
            f"yfinance returned no usable rows for {symbol!r}. "
            f"The symbol may have no liquid options listed."
        )

    out = pd.DataFrame(rows)

    # ── Mid price (matches IBKR adapter) ─────────────────────────────────
    out["mid"] = (out["bid"].fillna(0) + out["ask"].fillna(0)) / 2.0
    fallback = (out["mid"] <= 0) & (out["last"] > 0)
    out.loc[fallback, "mid"] = out.loc[fallback, "last"]

    logger.info(
        "Fetched %d option contracts for %s (%d expiries) from yfinance",
        len(out),
        symbol,
        len(expiries),
    )
    return out
