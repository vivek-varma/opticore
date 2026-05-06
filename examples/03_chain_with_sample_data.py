"""End-to-end chain workflow against the bundled sample data — no IBKR, no network.

Demonstrates the four chain-level functions: ``fetch_chain``, ``enrich``,
``parity_check``, and ``implied_forward``. The sample provider ships a
synthetic SPY chain inside the wheel, so this script runs anywhere
``pip install opticore`` works.

Run::

    python examples/03_chain_with_sample_data.py
"""

import opticore as oc

# ── Fetch a tiny synthetic chain (no network, no account) ──────────────────
chain = oc.fetch_chain(provider="sample", symbol="SPY")
print(f"Loaded {len(chain)} contracts across {chain['expiry'].nunique()} expiries.")
print(chain.head(3).to_string(index=False))

# ── Enrich: adds IV, Greeks, theo_price, mispricing, moneyness, intrinsic ──
enriched = oc.enrich(chain, rate=0.045, div_yield=0.013)
solved = enriched["iv"].notna().sum()
print(f"\nIV solved on {solved}/{len(enriched)} rows.")
print(
    enriched.loc[enriched["iv"].notna(), ["strike", "kind", "iv", "delta", "vega"]]
    .head(5)
    .to_string(index=False)
)

# ── parity_check: per-(expiry, strike) put-call parity residuals ───────────
diag = oc.parity_check(chain, rate=0.045, div_yield=0.013)
print(f"\nParity residuals: max |residual| = ${diag['parity_residual'].abs().max():.4f}")

# ── implied_forward: F(T) and implied div yield per expiry ─────────────────
fwd = oc.implied_forward(chain, rate=0.045)
print("\nImplied forward by expiry:")
print(fwd.to_string(index=False))
