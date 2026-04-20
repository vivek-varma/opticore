"""Visualization functions for options analytics."""

from __future__ import annotations

from typing import Optional, Sequence

import numpy as np

from opticore import Leg
from opticore import greeks as oc_greeks


def _get_plt():
    """Lazy import matplotlib."""
    try:
        import matplotlib.pyplot as plt

        return plt
    except ImportError:
        raise ImportError(
            "matplotlib is required for plotting. Install with: pip install opticore[viz]"
        )


def smile(
    enriched_df,
    expiry: Optional[str] = None,
    x: str = "strike",
    ax=None,
):
    """Plot implied volatility smile from an enriched chain DataFrame.

    Parameters
    ----------
    enriched_df : pd.DataFrame
        DataFrame with 'strike', 'expiry', 'iv', 'kind' columns
        (output of oc.enrich()).
    expiry : str or None
        Specific expiry date to plot (e.g. '2026-06-20'). If None, plots all.
    x : str
        X-axis variable: 'strike' or 'moneyness'.
    ax : matplotlib.axes.Axes or None
        Axes to plot on. If None, creates a new figure.

    Returns
    -------
    matplotlib.figure.Figure
    """
    plt = _get_plt()
    import pandas as pd

    df = enriched_df.copy()

    # Filter valid IV
    df = df[df["iv"].notna() & (df["iv"] > 0) & (df["iv"] < 5.0)]

    # Use calls only for cleaner smile
    df = df[df["kind"].str.lower().isin(["call", "c"])]

    if expiry is not None:
        df = df[df["expiry"].astype(str).str.startswith(str(expiry))]

    if df.empty:
        raise ValueError("No data to plot after filtering.")

    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(10, 6))
    else:
        fig = ax.get_figure()

    x_col = x if x in df.columns else "strike"

    # Group by expiry and plot each
    for exp, group in df.groupby("expiry"):
        group = group.sort_values(x_col)
        label = pd.Timestamp(exp).strftime("%Y-%m-%d") if hasattr(exp, "strftime") else str(exp)
        ax.plot(group[x_col], group["iv"] * 100, "o-", markersize=4, label=label)

    ax.set_xlabel(x_col.replace("_", " ").title())
    ax.set_ylabel("Implied Volatility (%)")
    ax.set_title("IV Smile")
    ax.legend(title="Expiry", fontsize=9)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    return fig


def payoff(
    legs: Sequence[Leg],
    spot_range: tuple[float, float] = None,
    num_points: int = 200,
    ax=None,
):
    """Plot strategy payoff diagram.

    Parameters
    ----------
    legs : list of Leg
        Strategy legs. Each Leg(kind, strike, qty, premium).
    spot_range : tuple or None
        (low, high) for the x-axis. Auto-computed if None.
    num_points : int
        Number of points to plot.
    ax : matplotlib.axes.Axes or None

    Returns
    -------
    matplotlib.figure.Figure

    Examples
    --------
    >>> import opticore as oc
    >>> fig = oc.plot.payoff([
    ...     oc.Leg("call", strike=105, qty=1, premium=3.50),
    ...     oc.Leg("put",  strike=95,  qty=1, premium=2.10),
    ... ])
    """
    plt = _get_plt()

    if not legs:
        raise ValueError("At least one leg is required.")

    # Determine spot range
    strikes = [leg.strike for leg in legs]
    if spot_range is None:
        mid = np.mean(strikes)
        span = max(np.ptp(strikes) * 1.5, mid * 0.2)
        spot_range = (mid - span, mid + span)

    spots = np.linspace(spot_range[0], spot_range[1], num_points)

    # Compute payoff at expiry for each leg
    total_payoff = np.zeros_like(spots)
    total_cost = 0.0

    for leg in legs:
        if leg.kind.lower() in ("call", "c"):
            intrinsic = np.maximum(spots - leg.strike, 0)
        else:
            intrinsic = np.maximum(leg.strike - spots, 0)

        total_payoff += leg.qty * intrinsic
        total_cost += leg.qty * leg.premium

    net_pnl = total_payoff - total_cost

    # Plot
    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(10, 6))
    else:
        fig = ax.get_figure()

    ax.plot(spots, net_pnl, "b-", linewidth=2, label="P&L at Expiry")
    ax.axhline(y=0, color="gray", linestyle="-", linewidth=0.5)

    # Mark break-even points
    sign_changes = np.where(np.diff(np.sign(net_pnl)))[0]
    for idx in sign_changes:
        # Linear interpolation for exact break-even
        x0, x1 = spots[idx], spots[idx + 1]
        y0, y1 = net_pnl[idx], net_pnl[idx + 1]
        be = x0 - y0 * (x1 - x0) / (y1 - y0)
        ax.axvline(x=be, color="red", linestyle="--", alpha=0.5, linewidth=1)
        ax.annotate(f"BE: {be:.1f}", xy=(be, 0), fontsize=9, ha="center", va="bottom", color="red")

    # Mark strikes
    for leg in legs:
        ax.axvline(x=leg.strike, color="gray", linestyle=":", alpha=0.4)

    # Fill profit/loss regions
    ax.fill_between(spots, net_pnl, 0, where=(net_pnl > 0), alpha=0.1, color="green")
    ax.fill_between(spots, net_pnl, 0, where=(net_pnl < 0), alpha=0.1, color="red")

    ax.set_xlabel("Underlying Price at Expiry")
    ax.set_ylabel("Profit / Loss")
    ax.set_title("Strategy Payoff")
    ax.legend()
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    return fig


def greek(
    greek_name: str,
    spot_range: tuple[float, float],
    strike: float,
    expiry: float,
    rate: float,
    vol: float,
    kind: str = "both",
    div_yield: float = 0.0,
    num_points: int = 200,
    ax=None,
):
    """Plot a Greek as a function of spot price.

    Parameters
    ----------
    greek_name : str
        One of: 'delta', 'gamma', 'theta', 'vega', 'rho', 'price'.
    spot_range : tuple
        (low, high) range for the underlying price.
    strike, expiry, rate, vol, div_yield : float
        BSM parameters.
    kind : str
        'call', 'put', or 'both' (overlays both on same axes).
    num_points : int
        Number of points to compute.

    Returns
    -------
    matplotlib.figure.Figure
    """
    plt = _get_plt()

    spots = np.linspace(spot_range[0], spot_range[1], num_points)
    valid_greeks = {"price", "delta", "gamma", "theta", "vega", "rho"}
    if greek_name not in valid_greeks:
        raise ValueError(f"greek must be one of {valid_greeks}, got: {greek_name!r}")

    kinds = []
    if kind.lower() in ("call", "c", "both"):
        kinds.append(("call", True))
    if kind.lower() in ("put", "p", "both"):
        kinds.append(("put", False))

    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(10, 6))
    else:
        fig = ax.get_figure()

    for label, is_call in kinds:
        values = []
        for s in spots:
            g = oc_greeks(s, strike, expiry, rate, vol, label, div_yield)
            values.append(getattr(g, greek_name))

        ax.plot(spots, values, linewidth=2, label=label.capitalize())

    ax.axvline(x=strike, color="gray", linestyle=":", alpha=0.5, label=f"Strike ({strike})")
    ax.set_xlabel("Spot Price")
    ax.set_ylabel(greek_name.capitalize())
    ax.set_title(f"{greek_name.capitalize()} vs Spot Price")
    ax.legend()
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    return fig
