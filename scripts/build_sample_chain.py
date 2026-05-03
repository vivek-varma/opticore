"""Build the bundled sample chain shipped with opticore.

Run once and commit the output:
    python scripts/build_sample_chain.py

Why synthetic: Yahoo's ToS forbids redistributing captured quotes, and we
don't yet have a no-strings real-data source. We synthesize a realistic
SPY-like chain (BSM-priced with a smile/skew) so users without an IBKR
account can still run `01_quickstart.ipynb` end-to-end. The data is clearly
fake but mathematically consistent — IV recovers, parity holds.

The output is a single parquet at:
    python/opticore/data/sample_chain.parquet

Schema matches the live providers (ibkr, yfinance) exactly:
    symbol, expiry (UTC Timestamp), strike, kind, bid, ask, last, mid,
    volume, open_interest, underlying_price.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import opticore as oc
import pandas as pd

# Frozen "snapshot" date so the parquet is reproducible. Pretend this chain
# was captured at 2026-04-15 16:00 UTC.
AS_OF = datetime(2026, 4, 15, 16, 0, tzinfo=timezone.utc)
SYMBOL = "SPY"
SPOT = 510.0
RATE = 0.045
DIV_YIELD = 0.013

# Six expiries: 2 weekly + 2 monthly + 2 quarterly
EXPIRY_DAYS = [7, 14, 35, 70, 182, 273]


def vol_smile(strike: float, spot: float, tte: float) -> float:
    """Realistic SPY-like skew: lower strikes have higher IV, decays with √T."""
    moneyness = np.log(strike / spot)
    base = 0.16
    skew = -0.45 * moneyness
    smile = 1.5 * moneyness * moneyness
    term_decay = 1.0 / (1.0 + tte)  # short-dated has fatter smile
    return float(base + (skew + smile) * term_decay)


def main() -> Path:
    rng = np.random.default_rng(20260415)
    rows: list[dict] = []

    for d in EXPIRY_DAYS:
        exp_dt = AS_OF + timedelta(days=d)
        # Normalize expiry to UTC midnight (matches IBKR/yfinance schema)
        exp_ts = pd.Timestamp(exp_dt.date(), tz="UTC")
        tte = (exp_ts.to_pydatetime() - AS_OF).total_seconds() / (365.25 * 24 * 3600)

        # ATM ± ~10% in $5 strikes
        strikes = np.arange(SPOT * 0.85, SPOT * 1.15 + 1, 5.0)

        for k in strikes:
            iv = vol_smile(float(k), SPOT, tte)
            for kind in ("call", "put"):
                model = oc.price(
                    spot=SPOT,
                    strike=float(k),
                    expiry=tte,
                    rate=RATE,
                    vol=iv,
                    kind=kind,
                    div_yield=DIV_YIELD,
                )
                # Realistic spread: 1-2% of mid, wider for OTM
                otm = (kind == "call" and k > SPOT) or (kind == "put" and k < SPOT)
                spread_pct = 0.012 if not otm else 0.025
                half = max(model * spread_pct / 2, 0.01)
                # Mild jitter on mid (±0.3% of model)
                jitter = rng.normal(0, model * 0.003)
                mid = max(model + jitter, 0.01)
                bid = max(mid - half, 0.01)
                ask = mid + half
                # Volume / OI: ATM has more
                atm_factor = np.exp(-((np.log(k / SPOT)) ** 2) / 0.005)
                vol = int(max(rng.normal(2000 * atm_factor, 400), 0))
                oi = int(max(rng.normal(8000 * atm_factor, 1500), 0))

                rows.append(
                    {
                        "symbol": SYMBOL,
                        "expiry": exp_ts,
                        "strike": float(k),
                        "kind": kind,
                        "bid": round(bid, 2),
                        "ask": round(ask, 2),
                        "last": round(mid, 2),
                        "mid": round(mid, 2),
                        "volume": vol,
                        "open_interest": oi,
                        "underlying_price": SPOT,
                    }
                )

    df = pd.DataFrame(rows)

    out_dir = Path(__file__).resolve().parents[1] / "python" / "opticore" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "sample_chain.parquet"
    df.to_parquet(out_path, index=False, compression="zstd")

    print(f"Wrote {len(df)} rows to {out_path}")
    print(f"  expiries: {df['expiry'].nunique()}")
    print(f"  strikes : {df['strike'].nunique()}")
    print(f"  size    : {out_path.stat().st_size / 1024:.1f} KiB")
    return out_path


if __name__ == "__main__":
    main()
