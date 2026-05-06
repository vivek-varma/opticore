"""Implied volatility round-trip — price → iv() should recover σ to machine precision.

Run::

    python examples/02_implied_vol.py
"""

import opticore as oc

S, K, T, r, sigma = 100.0, 105.0, 0.5, 0.05, 0.20

# Forward: price the option at known σ
mid = oc.price(spot=S, strike=K, expiry=T, rate=r, vol=sigma, kind="call")
print(f"Priced at σ={sigma:.4f}: mid = ${mid:.6f}")

# Inverse: solve for σ given the price
solved = oc.iv(price=mid, spot=S, strike=K, expiry=T, rate=r, kind="call")
print(f"Recovered σ:           σ = {solved:.16f}")
print(f"Round-trip error:      {abs(solved - sigma):.2e}")
