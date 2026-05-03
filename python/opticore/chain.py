"""Option chain fetching and enrichment."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def check_connection(
    host: str = "127.0.0.1",
    port: int = 7497,
    client_id: int = 99,
    timeout: float = 5.0,
) -> dict:
    """Test connectivity to TWS or IB Gateway.

    Quick way to verify your IBKR setup before fetching data.

    Returns
    -------
    dict with keys: connected (bool), account, server_version, message

    Examples
    --------
    >>> import opticore as oc
    >>> status = oc.check_connection()
    >>> print(status["message"])
    """
    from opticore.data.ibkr import check_connection as _check

    return _check(host=host, port=port, client_id=client_id, timeout=timeout)


def fetch_chain(
    symbol: str,
    provider: str = "ibkr",
    max_expiries: int = 6,
    strike_count: int = 20,
    timeout: float = 30.0,
    **provider_kwargs,
) -> pd.DataFrame:
    """Fetch an option chain for a given symbol.

    Parameters
    ----------
    symbol : str
        Underlying ticker symbol (e.g. "AAPL", "SPY").
    provider : str
        Data provider. Supported:
          - ``"ibkr"`` (default): Interactive Brokers via TWS/IB Gateway.
            Requires an account + market-data subscription.
          - ``"yfinance"`` (aliases: ``"yahoo"``, ``"yf"``): Yahoo Finance,
            ~15-min delayed, no account needed. Install via
            ``pip install opticore[data-yfinance]``.
    max_expiries : int
        Number of nearest expiries to fetch (default: 6). Shared contract
        across all providers.
    strike_count : int
        Number of strikes around ATM on each side (default: 20). Shared
        contract across all providers.
    timeout : float
        Maximum seconds to wait for data (default: 30). Shared contract
        across all providers.
    **provider_kwargs
        Provider-specific options. Unknown kwargs are forwarded as-is
        to the underlying provider adapter.

        ``ibkr`` accepts:
            - ``host`` (str, default ``"127.0.0.1"``)
            - ``port`` (int, default ``7497`` — TWS live; use ``4001`` for Gateway)
            - ``client_id`` (int, default ``1``)
            - ``market_data_type`` (int, default ``3`` — 1=live, 3=delayed, 4=frozen)

        ``yfinance`` accepts no extra kwargs.

    Returns
    -------
    pd.DataFrame
        Option chain with columns: symbol, strike, expiry, kind,
        bid, ask, last, volume, open_interest, underlying_price, mid.

    Examples
    --------
    >>> import opticore as oc
    >>> # Default IBKR (uses defaults for host/port/client_id/market_data_type)
    >>> chain = oc.fetch_chain("AAPL")  # doctest: +SKIP
    >>> # IBKR with explicit Gateway port
    >>> chain = oc.fetch_chain("AAPL", port=4001, client_id=42)  # doctest: +SKIP
    >>> # yfinance (no account)
    >>> chain = oc.fetch_chain("AAPL", provider="yfinance")  # doctest: +SKIP
    """
    p = provider.lower()
    shared = dict(
        symbol=symbol,
        max_expiries=max_expiries,
        strike_count=strike_count,
        timeout=timeout,
    )
    if p == "ibkr":
        from opticore.data.ibkr import fetch_ibkr_chain

        return fetch_ibkr_chain(**shared, **provider_kwargs)
    elif p in ("yfinance", "yahoo", "yf"):
        if provider_kwargs:
            raise TypeError(
                f"yfinance provider takes no provider_kwargs, got: {sorted(provider_kwargs)}"
            )
        from opticore.data.yfinance_adapter import fetch_yfinance_chain

        return fetch_yfinance_chain(**shared)
    else:
        raise ValueError(f"Unknown provider: {provider!r}. Supported: 'ibkr', 'yfinance'.")


def enrich(
    chain: pd.DataFrame,
    rate: float = 0.045,
    div_yield: float = 0.0,
    price_col: str = "mid",
) -> pd.DataFrame:
    """Enrich an option chain DataFrame with IV and Greeks.

    Adds columns: mid, tte, iv, delta, gamma, theta, vega, rho, moneyness, intrinsic.

    Parameters
    ----------
    chain : pd.DataFrame
        Must have columns: strike, expiry, kind, underlying_price,
        and either 'mid' or 'bid'+'ask' (or the column named by price_col).
    rate : float
        Risk-free interest rate (default: 0.045).
    div_yield : float
        Continuous dividend yield (default: 0.0).
    price_col : str
        Column to use for option price: 'mid', 'bid', 'ask', 'last'.

    Returns
    -------
    pd.DataFrame
        Original chain with added columns.
    """
    from opticore._core import _greeks_batch, _implied_vol_batch

    df = chain.copy()

    # ── Compute mid if not present ───────────────────────────────────────
    if "mid" not in df.columns and "bid" in df.columns and "ask" in df.columns:
        df["mid"] = (df["bid"] + df["ask"]) / 2.0

    # ── Time to expiry in years ──────────────────────────────────────────
    now = datetime.now(timezone.utc)
    df["expiry_dt"] = pd.to_datetime(df["expiry"], utc=True)
    df["tte"] = (df["expiry_dt"] - now).dt.total_seconds() / (365.25 * 24 * 3600)
    df["tte"] = df["tte"].clip(lower=1e-6)  # avoid zero/negative

    # ── Moneyness ────────────────────────────────────────────────────────
    df["moneyness"] = df["strike"] / df["underlying_price"]

    # ── Intrinsic value ──────────────────────────────────────────────────
    is_call = df["kind"].str.lower().isin(["call", "c"])
    df["intrinsic"] = np.where(
        is_call,
        np.maximum(df["underlying_price"] - df["strike"], 0),
        np.maximum(df["strike"] - df["underlying_price"], 0),
    )

    # ── Vectorized IV + Greeks ───────────────────────────────────────────
    # Single trip into C++ for IV solve, then a second for Greeks. NaN
    # propagation handles unsolvable rows: _implied_vol_batch returns NaN,
    # _greeks_batch then produces NaN price/greeks for those rows naturally.
    #
    # Use Series.to_numpy() (not .values) — it's the stable pandas API and
    # always returns a numpy.ndarray. In pandas 3.0+, .values can return an
    # ExtensionArray which nanobind's strict ndarray check rejects.
    # ascontiguousarray then guarantees C-contiguous layout (required by the
    # C++ binding's `nb::c_contig` constraint).
    prices = np.ascontiguousarray(df[price_col].to_numpy(dtype=np.float64, copy=False))
    spots = np.ascontiguousarray(df["underlying_price"].to_numpy(dtype=np.float64, copy=False))
    strikes = np.ascontiguousarray(df["strike"].to_numpy(dtype=np.float64, copy=False))
    ttes = np.ascontiguousarray(df["tte"].to_numpy(dtype=np.float64, copy=False))
    is_call_arr = np.ascontiguousarray(is_call.to_numpy(dtype=bool, copy=False))

    iv_values = np.asarray(
        _implied_vol_batch(
            prices,
            spots,
            strikes,
            ttes,
            float(rate),
            float(div_yield),
            is_call_arr,
        )
    )
    df["iv"] = iv_values

    model_price, delta, gamma, theta, vega, rho = _greeks_batch(
        spots,
        strikes,
        ttes,
        float(rate),
        iv_values,
        float(div_yield),
        is_call_arr,
    )

    df["model_price"] = np.asarray(model_price)
    df["delta"] = np.asarray(delta)
    df["gamma"] = np.asarray(gamma)
    df["theta"] = np.asarray(theta)
    df["vega"] = np.asarray(vega)
    df["rho"] = np.asarray(rho)

    # ── Summary ──────────────────────────────────────────────────────────
    n_total = len(df)
    n_failed = df["iv"].isna().sum()
    n_success = n_total - n_failed
    pct_failed = (n_failed / n_total * 100) if n_total > 0 else 0

    logger.info("Enriched %d options, %d IV failures (%.1f%%)", n_success, n_failed, pct_failed)

    # Clean up temp column
    df.drop(columns=["expiry_dt"], inplace=True, errors="ignore")

    return df
