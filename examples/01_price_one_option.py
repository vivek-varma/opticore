"""Price a single European call. The minimum useful OptiCore example.

Run::

    python examples/01_price_one_option.py
"""

import opticore as oc

price = oc.price(spot=100, strike=105, expiry=0.5, rate=0.05, vol=0.20, kind="call")
print(f"Call price: ${price:.4f}")

# Same call, but with all Greeks in a single C++ pass.
g = oc.greeks(spot=100, strike=105, expiry=0.5, rate=0.05, vol=0.20, kind="call")
print(f"Δ={g.delta:.4f}  Γ={g.gamma:.4f}  Θ={g.theta:.4f}  ν={g.vega:.4f}  ρ={g.rho:.4f}")
