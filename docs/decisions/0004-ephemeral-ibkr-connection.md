# 0004 — IBKR connections are ephemeral (connect → fetch → disconnect)

**Status:** Accepted
**Date:** 2026-04-10

## Context

Interactive Brokers' API (via `ib_async`) supports two usage styles:

1. **Persistent connection** — keep `IB()` alive across calls, subscribe to streaming tickers, handle events.
2. **Ephemeral connection** — connect, request, disconnect, all inside one function.

Our target audience is retail users pulling option chains in Jupyter notebooks. They don't want to think about connection lifecycle, client IDs colliding, or background event loops.

## Decision

Every IBKR-touching function — `check_connection()`, `fetch_ibkr_chain()` — owns its own connection end-to-end:

```python
def fetch_ibkr_chain(...):
    ib = IB()
    try:
        ib.connect(...)
        # ... do work ...
        return df
    finally:
        if ib.isConnected():
            ib.disconnect()
```

No library-global `IB` instance. No long-running event loop for the user to manage.

## Consequences

**Gains:**
- **Dead simple mental model.** Call function → get data. No setup, no teardown, no background state.
- **No client-ID collisions.** Each call gets its own `client_id` default (and users can override).
- **Works in notebooks cleanly.** Combined with `nest_asyncio` patching, one cell = one atomic fetch.
- **Exceptions always clean up.** The `finally` block guarantees disconnect even if fetching fails midway.

**Give up:**
- **Latency.** Every `fetch_ibkr_chain` call pays ~100–300ms of TCP + API handshake. For Phase 1 (periodic analysis, not HFT), this is irrelevant.
- **No streaming.** Users who want tick-by-tick updates can't use our adapter. Documented non-goal for Phase 1; Phase 4 can add a streaming API as a separate layer if demand emerges.
- **TWS pacing rules are our problem.** Because we don't persist the connection, we can't batch across calls. We mitigate with in-function chunking (50 contracts per qualify/reqTickers batch).

## Gotchas this decision surfaced

- **Jupyter event-loop conflict.** `ib_async`'s sync API calls `asyncio.run()`, which raises when Jupyter has a loop running. Fix: `_patch_event_loop()` in `python/opticore/data/ibkr.py` auto-applies `nest_asyncio` (auto-installs the package if missing).
- **"open orders timed out" warnings.** Pass `readonly=True` to `ib.connect()`; we don't need order state, and this suppresses the warnings.

## Alternatives considered

- **Persistent connection with a context manager** — `with oc.ibkr_session() as s:` style. Rejected on ergonomics: retail users shouldn't need to learn context managers for one-off pulls. Revisit in Phase 4 if streaming becomes a goal.
- **Background thread with a persistent connection** — too much state to reason about, thread-safety footguns, unacceptable for a "drop into notebook" experience.
- **Only offer an async API** — retail users don't want to think about `await`.
