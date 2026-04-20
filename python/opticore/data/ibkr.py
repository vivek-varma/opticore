"""Interactive Brokers data adapter using ib_async."""

from __future__ import annotations

import asyncio
import warnings
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd


def _patch_event_loop():
    """Allow ib_async to work inside Jupyter / any running event loop.

    Jupyter (and similar environments) already run an asyncio event loop.
    ib_async's synchronous API calls asyncio.run() internally, which raises
    'This event loop is already running'. nest_asyncio patches the loop to
    allow reentrant calls. If nest_asyncio isn't available, we install it
    automatically since it's tiny and has no dependencies.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return  # No running loop — nothing to patch

    # A running loop exists (Jupyter, IPython, etc.) — patch it
    try:
        import nest_asyncio
    except ImportError:
        import subprocess
        import sys
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-q", "nest_asyncio"],
        )
        import nest_asyncio

    nest_asyncio.apply(loop)


def check_connection(
    host: str = "127.0.0.1",
    port: int = 7497,
    client_id: int = 99,
    timeout: float = 5.0,
) -> dict:
    """Test connectivity to TWS or IB Gateway.

    Parameters
    ----------
    host : str
        TWS/Gateway host (default: localhost).
    port : int
        7497 = TWS live, 7496 = TWS paper,
        4001 = Gateway live, 4002 = Gateway paper.
    client_id : int
        Client ID for this test connection (default: 99).
    timeout : float
        Seconds to wait before giving up.

    Returns
    -------
    dict
        {"connected": bool, "account": str or None, "server_version": int or None,
         "message": str}

    Examples
    --------
    >>> from opticore.data.ibkr import check_connection
    >>> result = check_connection(port=7497)
    >>> print(result["message"])
    """
    try:
        from ib_async import IB
    except ImportError:
        return {
            "connected": False,
            "account": None,
            "server_version": None,
            "message": (
                "ib_async not installed. Run: pip install opticore[ibkr]"
            ),
        }

    _patch_event_loop()

    ib = IB()
    try:
        ib.RequestTimeout = timeout
        ib.connect(
            host, port, clientId=client_id, timeout=timeout,
            readonly=True,
        )
        accounts = ib.managedAccounts()
        account = accounts[0] if accounts else None
        server_version = ib.client.serverVersion()
        ib.disconnect()
        return {
            "connected": True,
            "account": account,
            "server_version": server_version,
            "message": (
                f"Connected to IBKR at {host}:{port} "
                f"(account: {account}, server v{server_version})"
            ),
        }
    except Exception as e:
        msg = str(e)
        hint = ""
        if "Connection refused" in msg or "timed out" in msg:
            hint = (
                "\n\nTroubleshooting:\n"
                "  1. Is TWS or IB Gateway running?\n"
                "  2. In TWS: Edit > Global Configuration > API > Settings\n"
                "     - Enable 'Enable ActiveX and Socket Clients'\n"
                "     - Set 'Socket port' to 7497 (live) or 7496 (paper)\n"
                "     - Add 127.0.0.1 to 'Trusted IPs'\n"
                "  3. Common ports:\n"
                "     TWS live=7497, TWS paper=7496\n"
                "     Gateway live=4001, Gateway paper=4002"
            )
        return {
            "connected": False,
            "account": None,
            "server_version": None,
            "message": f"Connection failed: {msg}{hint}",
        }
    finally:
        if ib.isConnected():
            ib.disconnect()


def fetch_ibkr_chain(
    symbol: str,
    host: str = "127.0.0.1",
    port: int = 7497,
    client_id: int = 1,
    max_expiries: int = 6,
    strike_count: int = 20,
    market_data_type: int = 3,
    timeout: float = 30.0,
) -> pd.DataFrame:
    """Fetch option chain from Interactive Brokers.

    Connects, fetches data, and disconnects. No persistent connection.

    Parameters
    ----------
    symbol : str
        Underlying ticker (e.g. "AAPL", "SPY").
    host, port : str, int
        TWS/Gateway connection details.
    client_id : int
        Unique client ID.
    max_expiries : int
        Nearest N expiries to fetch.
    strike_count : int
        Number of strikes around ATM on each side.
    market_data_type : int
        1=live, 3=delayed (free), 4=delayed-frozen.
    timeout : float
        Max seconds to wait.

    Returns
    -------
    pd.DataFrame
        Option chain data.
    """
    try:
        from ib_async import IB, Stock, Option, util
    except ImportError:
        raise ImportError(
            "ib_async is required for IBKR data. "
            "Install with: pip install opticore[ibkr]"
        )

    _patch_event_loop()

    ib = IB()

    try:
        # ── Connect ──────────────────────────────────────────────────────
        ib.connect(host, port, clientId=client_id, timeout=timeout)
        ib.reqMarketDataType(market_data_type)

        # ── Get underlying price ─────────────────────────────────────────
        stock = Stock(symbol, "SMART", "USD")
        ib.qualifyContracts(stock)

        [ticker] = ib.reqTickers(stock)
        ib.sleep(1)  # allow data to arrive

        underlying_price = ticker.marketPrice()
        if np.isnan(underlying_price) or underlying_price <= 0:
            # Try last price
            underlying_price = ticker.last
        if np.isnan(underlying_price) or underlying_price <= 0:
            underlying_price = ticker.close
        if np.isnan(underlying_price) or underlying_price <= 0:
            raise ValueError(
                f"Could not get price for {symbol}. "
                f"Check your market data subscription."
            )

        # ── Get option chain parameters ──────────────────────────────────
        chains = ib.reqSecDefOptParams(
            stock.symbol, "", stock.secType, stock.conId
        )

        # Find the SMART chain
        chain = None
        for c in chains:
            if c.exchange == "SMART":
                chain = c
                break
        if chain is None and chains:
            chain = chains[0]
        if chain is None:
            raise ValueError(f"No option chain found for {symbol}")

        # ── Filter expiries and strikes ──────────────────────────────────
        expirations = sorted(chain.expirations)[:max_expiries]

        all_strikes = sorted(chain.strikes)
        # Find ATM index
        atm_idx = min(
            range(len(all_strikes)),
            key=lambda i: abs(all_strikes[i] - underlying_price),
        )
        lo = max(0, atm_idx - strike_count)
        hi = min(len(all_strikes), atm_idx + strike_count + 1)
        strikes = all_strikes[lo:hi]

        # ── Build option contracts ───────────────────────────────────────
        contracts = []
        for exp in expirations:
            for strike in strikes:
                for right in ["C", "P"]:
                    contracts.append(
                        Option(
                            symbol, exp, strike, right,
                            "SMART", currency="USD",
                        )
                    )

        # ── Qualify contracts (batch) ────────────────────────────────────
        # Process in chunks to avoid overwhelming TWS
        qualified = []
        chunk_size = 50
        for i in range(0, len(contracts), chunk_size):
            chunk = contracts[i : i + chunk_size]
            qualified.extend(ib.qualifyContracts(*chunk))
            ib.sleep(0.1)

        # Filter out unqualified
        qualified = [c for c in qualified if c.conId > 0]

        if not qualified:
            raise ValueError(
                f"No valid option contracts found for {symbol}. "
                f"Check symbol and market data subscription."
            )

        # ── Request market data ──────────────────────────────────────────
        tickers = []
        for i in range(0, len(qualified), chunk_size):
            chunk = qualified[i : i + chunk_size]
            chunk_tickers = ib.reqTickers(*chunk)
            tickers.extend(chunk_tickers)
            ib.sleep(0.5)  # respect pacing

        # Allow data to settle
        ib.sleep(2)

        # ── Build DataFrame ──────────────────────────────────────────────
        rows = []
        for t in tickers:
            c = t.contract
            if c is None:
                continue

            bid = t.bid if t.bid not in (None, -1, float("nan")) else np.nan
            ask = t.ask if t.ask not in (None, -1, float("nan")) else np.nan
            last = t.last if t.last not in (None, -1, float("nan")) else np.nan
            vol = t.volume if t.volume not in (None, -1) else 0
            oi = t.open_interest if hasattr(t, "open_interest") else 0

            rows.append({
                "symbol": symbol,
                "strike": float(c.strike),
                "expiry": c.lastTradeDateOrContractMonth,
                "kind": "call" if c.right == "C" else "put",
                "bid": bid,
                "ask": ask,
                "last": last,
                "volume": int(vol) if vol else 0,
                "open_interest": int(oi) if oi else 0,
                "underlying_price": underlying_price,
            })

        df = pd.DataFrame(rows)

        # Compute mid
        if not df.empty:
            df["mid"] = (df["bid"].fillna(0) + df["ask"].fillna(0)) / 2.0
            # Where mid is zero but last exists, use last
            mask = (df["mid"] <= 0) & (df["last"] > 0)
            df.loc[mask, "mid"] = df.loc[mask, "last"]

        print(f"Fetched {len(df)} option contracts for {symbol} "
              f"({len(expirations)} expiries, {len(strikes)} strikes)")

        return df

    finally:
        # Always disconnect
        if ib.isConnected():
            ib.disconnect()
