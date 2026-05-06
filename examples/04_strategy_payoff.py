"""Iron condor strategy — build the legs and plot the P&L diagram.

Run (requires matplotlib — ``pip install opticore[viz]``)::

    python examples/04_strategy_payoff.py
"""

import matplotlib

matplotlib.use("Agg")  # headless-safe; remove this line for an interactive window
import matplotlib.pyplot as plt
import opticore as oc

# Iron condor on an underlying near $100. Sell the inner spreads, buy the wings.
legs = [
    oc.Leg("put", strike=90, qty=1, premium=1.00),  # long wing
    oc.Leg("put", strike=95, qty=-1, premium=2.50),  # short put
    oc.Leg("call", strike=105, qty=-1, premium=2.50),  # short call
    oc.Leg("call", strike=110, qty=1, premium=1.00),  # long wing
]

net_credit = -sum(leg.qty * leg.premium for leg in legs)
print(f"Net credit (max profit): ${net_credit:.2f}")

fig, ax = oc.plot.payoff(legs, spot_range=(80, 120))
ax.set_title("Iron Condor at Expiry")

out = "iron_condor.png"
fig.savefig(out, dpi=120, bbox_inches="tight")
plt.close(fig)
print(f"Saved {out}")
