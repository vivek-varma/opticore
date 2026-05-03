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
          - ``"sample"``: a tiny synthetic SPY chain bundled with the wheel.
            Zero dependencies, zero config — ideal for tutorials and CI.
            Data is BSM-priced with a realistic smile, *not* real quotes.
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
    elif p == "sample":
        if provider_kwargs:
            raise TypeError(
                f"sample provider takes no provider_kwargs, got: {sorted(provider_kwargs)}"
            )
        from opticore.data.sample import fetch_sample_chain

        return fetch_sample_chain(**shared)
    else:
        raise ValueError(
            f"Unknown provider: {provider!r}. Supported: 'ibkr', 'yfinance', 'sample'."
        )


def enrich(
    chain: pd.DataFrame,
    rate: float = 0.045,
    div_yield: float = 0.0,
    price_col: str = "mid",
    include_theo: bool = True,
) -> pd.DataFrame:
    """Enrich an option chain DataFrame with IV and Greeks.

    Adds columns: ``mid, tte, iv, delta, gamma, theta, vega, rho,
    moneyness, intrinsic``. When ``include_theo=True`` (default), also
    adds ``theo_price`` (BSM price at the recovered IV) and ``mispricing``
    (``price_col`` minus ``theo_price``) — useful for spotting stale quotes.

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
    include_theo : bool
        If True (default), add ``theo_price`` and ``mispricing`` columns.
        Set False to skip them — useful when you only need IV/Greeks
        and want to keep the output narrow.

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
    # Accept either pd.Timestamp (current schema) or legacy "YYYYMMDD" /
    # "YYYY-MM-DD" strings (pandas can parse both via to_datetime).
    now = datetime.now(timezone.utc)
    expiry_dt = pd.to_datetime(df["expiry"], utc=True)
    df["tte"] = (expiry_dt - now).dt.total_seconds() / (365.25 * 24 * 3600)
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

    theo_price, delta, gamma, theta, vega, rho = _greeks_batch(
        spots,
        strikes,
        ttes,
        float(rate),
        iv_values,
        float(div_yield),
        is_call_arr,
    )

    if include_theo:
        df["theo_price"] = np.asarray(theo_price)
        df["mispricing"] = df[price_col] - df["theo_price"]
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

    return df


# ════════════════════════════════════════════════════════════════════════════
# Parity diagnostics
# ════════════════════════════════════════════════════════════════════════════


def _pivot_call_put(chain: pd.DataFrame, price_col: str) -> pd.DataFrame:
    """Inner helper: align call/put rows side-by-side per (expiry, strike).

    Returns a frame with columns: expiry, strike, underlying_price,
    call_mid, put_mid (only rows where BOTH call and put exist).
    """
    df = chain.copy()
    if price_col == "mid" and "mid" not in df.columns and {"bid", "ask"}.issubset(df.columns):
        df["mid"] = (df["bid"] + df["ask"]) / 2.0
    if price_col not in df.columns:
        raise KeyError(f"Chain has no {price_col!r} column.")

    if df.empty or "kind" not in df.columns:
        return pd.DataFrame(
            columns=[
                "expiry",
                "strike",
                "underlying_price",
                "call_mid",
                "put_mid",
            ]
        )

    df["_kind"] = (
        df["kind"].str.lower().map({"call": "call", "c": "call", "put": "put", "p": "put"})
    )
    keep = ["expiry", "strike", "underlying_price", "_kind", price_col]
    sub = df[keep].dropna(subset=[price_col])

    if sub.empty or sub["_kind"].nunique() < 2:
        return pd.DataFrame(
            columns=[
                "expiry",
                "strike",
                "underlying_price",
                "call_mid",
                "put_mid",
            ]
        )

    # Pivot kinds into columns; keep underlying_price (assumed constant per expiry)
    pivot = sub.pivot_table(
        index=["expiry", "strike"],
        columns="_kind",
        values=price_col,
        aggfunc="first",
    ).reset_index()

    # Bring underlying_price back (first observed per expiry)
    spot_per_expiry = sub.groupby("expiry")["underlying_price"].first().rename("underlying_price")
    pivot = pivot.merge(spot_per_expiry, on="expiry", how="left")

    pivot = pivot.dropna(subset=["call", "put"])
    return pivot.rename(columns={"call": "call_mid", "put": "put_mid"})


def parity_check(
    chain: pd.DataFrame,
    rate: float = 0.045,
    div_yield: float = 0.0,
    price_col: str = "mid",
) -> pd.DataFrame:
    """Compute per-(expiry, strike) put-call parity residuals.

    Parity (Black-Scholes-Merton with continuous dividend yield)::

        C - P = S * exp(-q*T) - K * exp(-r*T)

    Large residuals indicate stale quotes, wide spreads, mid-pricing error,
    or a wrong assumption about ``rate`` / ``div_yield``. This is the first
    diagnostic to run when an enriched chain looks weird.

    Parameters
    ----------
    chain : pd.DataFrame
        Must have columns: ``expiry``, ``strike``, ``kind``,
        ``underlying_price``, and the column named by ``price_col``
        (or ``bid`` + ``ask`` to compute ``mid``).
    rate : float
        Risk-free rate (default: 0.045).
    div_yield : float
        Continuous dividend yield (default: 0.0).
    price_col : str
        Which price to use: 'mid' (default), 'last', 'bid', 'ask'.

    Returns
    -------
    pd.DataFrame
        Columns: expiry, strike, call_mid, put_mid,
        parity_residual, residual_pct.
        ``parity_residual = (C - P) - (S*exp(-q*T) - K*exp(-r*T))``.
        ``residual_pct = residual / underlying_price * 100``.

    Examples
    --------
    >>> import opticore as oc
    >>> diag = oc.parity_check(chain, rate=0.05)  # doctest: +SKIP
    >>> diag.nlargest(5, "residual_pct")          # doctest: +SKIP
    """
    p = _pivot_call_put(chain, price_col)
    if p.empty:
        return pd.DataFrame(
            columns=[
                "expiry",
                "strike",
                "call_mid",
                "put_mid",
                "parity_residual",
                "residual_pct",
            ]
        )

    # Time to expiry in years (accept Timestamp or legacy string)
    now = datetime.now(timezone.utc)
    expiry_dt = pd.to_datetime(p["expiry"], utc=True)
    tte = (expiry_dt - now).dt.total_seconds() / (365.25 * 24 * 3600)
    tte = tte.clip(lower=1e-6).to_numpy(dtype=np.float64)

    S = p["underlying_price"].to_numpy(dtype=np.float64)
    K = p["strike"].to_numpy(dtype=np.float64)
    expected = S * np.exp(-div_yield * tte) - K * np.exp(-rate * tte)
    actual = p["call_mid"].to_numpy(dtype=np.float64) - p["put_mid"].to_numpy(dtype=np.float64)
    residual = actual - expected

    out = p[["expiry", "strike", "call_mid", "put_mid"]].copy()
    out["parity_residual"] = residual
    out["residual_pct"] = residual / S * 100.0
    return out.reset_index(drop=True)


def implied_forward(
    chain: pd.DataFrame,
    rate: float = 0.045,
    n_atm_strikes: int = 3,
    price_col: str = "mid",
) -> pd.DataFrame:
    """Recover the implied forward price F(T) and dividend yield q per expiry.

    From put-call parity::

        C - P = exp(-r*T) * (F - K)
        ⇒ F = K + exp(r*T) * (C - P)

    Then::

        F = S * exp((r - q) * T)
        ⇒ q = r - ln(F / S) / T

    For numerical stability, F is averaged across the ``n_atm_strikes``
    strikes nearest the spot — these have the tightest (C - P) and least
    bid/ask noise leverage.

    Parameters
    ----------
    chain : pd.DataFrame
        Same schema as ``parity_check`` / ``enrich``.
    rate : float
        Risk-free rate (default: 0.045). The implied yield is computed
        relative to this — pass the same rate you'd use for ``enrich``.
    n_atm_strikes : int
        Number of strikes nearest spot used to average F per expiry (default: 3).
    price_col : str
        Which price to use (default: 'mid').

    Returns
    -------
    pd.DataFrame
        Columns: expiry, tte, forward, implied_div_yield, n_strikes_used.

    Examples
    --------
    >>> import opticore as oc
    >>> oc.implied_forward(chain, rate=0.05)  # doctest: +SKIP
    """
    p = _pivot_call_put(chain, price_col)
    if p.empty:
        return pd.DataFrame(
            columns=["expiry", "tte", "forward", "implied_div_yield", "n_strikes_used"]
        )

    now = datetime.now(timezone.utc)
    expiry_dt = pd.to_datetime(p["expiry"], utc=True)
    p = p.assign(_tte=(expiry_dt - now).dt.total_seconds() / (365.25 * 24 * 3600))
    # F per row from parity; average the k nearest spot per expiry.
    p["_F_row"] = p["strike"] + np.exp(rate * p["_tte"]) * (p["call_mid"] - p["put_mid"])
    p["_dist"] = (p["strike"] - p["underlying_price"]).abs()

    rows = []
    for exp, grp in p.groupby("expiry", sort=True):
        atm = grp.nsmallest(n_atm_strikes, "_dist")
        if atm.empty:
            continue
        tte = float(atm["_tte"].iloc[0])
        if tte <= 0:
            continue
        F = float(atm["_F_row"].mean())
        S = float(atm["underlying_price"].iloc[0])
        if F <= 0 or S <= 0:
            q = float("nan")
        else:
            q = rate - np.log(F / S) / tte
        rows.append(
            {
                "expiry": exp,
                "tte": tte,
                "forward": F,
                "implied_div_yield": q,
                "n_strikes_used": int(len(atm)),
            }
        )

    return pd.DataFrame(
        rows,
        columns=["expiry", "tte", "forward", "implied_div_yield", "n_strikes_used"],
    )
