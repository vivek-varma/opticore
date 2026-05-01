"""Option chain fetching and enrichment."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd


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
    host: str = "127.0.0.1",
    port: int = 7497,
    client_id: int = 1,
    max_expiries: int = 6,
    strike_count: int = 20,
    market_data_type: int = 3,
    timeout: float = 30.0,
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
    host : str
        TWS/Gateway host (default: localhost).
    port : int
        TWS port (7497) or Gateway port (4001).
    client_id : int
        Unique client ID for the IBKR connection.
    max_expiries : int
        Number of nearest expiries to fetch (default: 6).
    strike_count : int
        Number of strikes around ATM on each side (default: 20).
    market_data_type : int
        1=live (paid), 3=delayed (free), 4=delayed-frozen.
    timeout : float
        Maximum seconds to wait for data.

    Returns
    -------
    pd.DataFrame
        Option chain with columns: symbol, strike, expiry, kind,
        bid, ask, last, volume, open_interest, underlying_price.

    Examples
    --------
    >>> import opticore as oc
    >>> chain = oc.fetch_chain("AAPL")
    >>> chain.head()
    """
    p = provider.lower()
    if p == "ibkr":
        from opticore.data.ibkr import fetch_ibkr_chain

        return fetch_ibkr_chain(
            symbol=symbol,
            host=host,
            port=port,
            client_id=client_id,
            max_expiries=max_expiries,
            strike_count=strike_count,
            market_data_type=market_data_type,
            timeout=timeout,
        )
    elif p in ("yfinance", "yahoo", "yf"):
        from opticore.data.yfinance_adapter import fetch_yfinance_chain

        return fetch_yfinance_chain(
            symbol=symbol,
            max_expiries=max_expiries,
            strike_count=strike_count,
            timeout=timeout,
        )
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
    from opticore import iv as oc_iv

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

    # ── Implied volatility ───────────────────────────────────────────────
    prices = df[price_col].values.astype(np.float64)
    spots = df["underlying_price"].values.astype(np.float64)
    strikes = df["strike"].values.astype(np.float64)
    ttes = df["tte"].values.astype(np.float64)
    is_call_arr = is_call.values

    iv_values = np.empty(len(df), dtype=np.float64)
    for i in range(len(df)):
        kind_str = "call" if is_call_arr[i] else "put"
        try:
            iv_values[i] = oc_iv(
                price=prices[i],
                spot=spots[i],
                strike=strikes[i],
                expiry=ttes[i],
                rate=rate,
                kind=kind_str,
                div_yield=div_yield,
            )
        except Exception:
            iv_values[i] = np.nan

    df["iv"] = iv_values

    # ── Greeks (using solved IV) ─────────────────────────────────────────
    from opticore._core import _greeks_scalar

    greek_cols: dict[str, list[float]] = {
        "delta": [],
        "gamma": [],
        "theta": [],
        "vega": [],
        "rho": [],
    }
    model_price: list[float] = []

    for i in range(len(df)):
        v = iv_values[i]
        if np.isnan(v) or v <= 0:
            model_price.append(np.nan)
            for col in greek_cols:
                greek_cols[col].append(np.nan)
            continue

        result = _greeks_scalar(
            spots[i],
            strikes[i],
            ttes[i],
            rate,
            v,
            div_yield,
            bool(is_call_arr[i]),
        )
        model_price.append(result[0])
        greek_cols["delta"].append(result[1])
        greek_cols["gamma"].append(result[2])
        greek_cols["theta"].append(result[3])
        greek_cols["vega"].append(result[4])
        greek_cols["rho"].append(result[5])

    df["model_price"] = model_price
    for col, values in greek_cols.items():
        df[col] = values

    # ── Summary ──────────────────────────────────────────────────────────
    n_total = len(df)
    n_failed = df["iv"].isna().sum()
    n_success = n_total - n_failed
    pct_failed = (n_failed / n_total * 100) if n_total > 0 else 0

    print(f"Enriched {n_success} options, {n_failed} IV failures ({pct_failed:.1f}%)")

    # Clean up temp column
    df.drop(columns=["expiry_dt"], inplace=True, errors="ignore")

    return df
