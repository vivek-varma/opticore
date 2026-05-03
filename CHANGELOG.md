# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **Breaking — `expiry` column is now `pd.Timestamp` (UTC midnight)** (#24).
  Both `fetch_chain` providers (`ibkr`, `yfinance`) now emit `expiry` as a
  timezone-aware `pd.Timestamp` instead of a `"YYYYMMDD"` string. This makes
  date arithmetic and filtering natural (`df[df.expiry >= "2026-06-01"]`)
  and matches what `enrich()` was already producing internally. `enrich()`
  still accepts legacy string expiries via `pd.to_datetime`, so user-built
  chains aren't broken. `oc.plot.smile(expiry=...)` accepts strings or
  Timestamps and normalizes both sides for comparison.
- **Breaking — `oc.plot.*` now returns `(fig, ax)`** (#27). All three plot
  helpers (`smile`, `payoff`, `greek`) now return a `(Figure, Axes)` tuple
  per matplotlib convention, instead of just `Figure`. This unlocks
  composition (annotations, shared axes, subplots) without reaching into
  `fig.axes`. Migrate `fig = oc.plot.smile(...)` → `fig, ax = oc.plot.smile(...)`.
  Bare calls like `oc.plot.smile(df)` are unaffected (return value discarded).
- **Breaking — `fetch_chain()` signature** (#22). Provider-specific kwargs
  (`host`, `port`, `client_id`, `market_data_type`) are no longer top-level
  parameters; they now flow through `**provider_kwargs`. Old call sites
  using kwargs (e.g. `oc.fetch_chain("AAPL", port=4001, client_id=42)`)
  continue to work unchanged because the kwargs are forwarded to the IBKR
  adapter. Positional calls passing those args are no longer supported,
  but no documentation ever advertised that pattern. The yfinance provider
  now raises `TypeError` if any provider_kwargs are passed (they would be
  silently ignored before).
- **Library code no longer prints to stdout** (#23). All status/progress
  messages from `enrich()`, `fetch_ibkr_chain()`, and `fetch_yfinance_chain()`
  now route through the standard `logging` module under the `opticore.*`
  namespace. To see them, opt in once: `logging.basicConfig(level=logging.INFO)`.
  Notebooks/scripts that relied on the old prints will go silent — this is
  intentional; libraries shouldn't pollute stdout.

### Performance
- **`enrich()` is now ~50× faster** on real-sized chains (#21). Replaced the
  per-row Python loop with two batched calls into the C++ core
  (`_implied_vol_batch`, `_greeks_batch`). A 1000-row chain enriches in
  ~2 ms (was ~100 ms). NaN propagation handles unsolvable rows naturally,
  removing the bare `except Exception` that was hiding errors (#25).

### Added
- **`oc.parity_check(chain, rate, div_yield)`** (#28) — per-(expiry, strike)
  put-call parity diagnostic. Returns a DataFrame with `parity_residual` and
  `residual_pct` columns. First-line tool for spotting stale quotes, wrong
  rate/div assumptions, or mid-pricing mistakes in fetched chains.
- **`oc.implied_forward(chain, rate)`** (#29) — recovers the implied forward
  price F(T) and dividend yield q per expiry from put-call parity, averaged
  across the N strikes nearest spot for stability. Round-trips a known q
  within ~1bp on synthetic chains.
- **yfinance provider** for `oc.fetch_chain()` — no account, no subscription,
  ~15-min delayed Yahoo data. Use via `provider="yfinance"`. Install with
  `pip install opticore[data-yfinance]`. IBKR remains the primary provider.

### Added
- Type stubs (`__init__.pyi`, `_core.pyi`) and `py.typed` marker for PEP 561
  compliance. IDEs and `mypy` now see real types for all public functions
  instead of `Any`, including `pd.DataFrame` returns and NumPy array overloads.
- `[tool.mypy]` config in `pyproject.toml`; `mypy` runs clean on
  `python/opticore` + `tests/python`.

### Changed
- **Breaking (keyword arg):** `oc.iv(price_val=...)` → `oc.iv(price=...)` to
  match the docstring and notebooks. Positional calls are unaffected.
- `plot.payoff` param `spot_range` is now `Optional[tuple[float, float]]`
  (was implicitly Optional — PEP 484 no longer allows that).
- `enrich()`'s internal `greek_cols` dict now has an explicit type annotation.

## [0.2.0] - 2026-04-XX

### Added
- Packaging: `cibuildwheel` config + release workflow builds wheels for CPython
  3.10–3.13 on linux (manylinux2014) / macos / windows on tag push
- TestPyPI dry-run via `workflow_dispatch` input `publish_to_testpypi`
- CI: upload CTest and pytest logs as artifacts on failure
- CI status badge in README
- Project context docs: `AGENT.md`, `ROADMAP.md`, 5 ADRs in `docs/decisions/`

### Changed
- `norm_pdf` and `is_valid` in `include/opticore/math.hpp` are no longer
  `constexpr` — standard C++20 doesn't allow `std::exp` or `std::isnan` in
  constant expressions, and MSVC rejects them. GCC/Clang accepted the old
  code as an extension. No runtime impact — `inline` still permits full
  inlining by the optimizer.
- Dropped unused `strike` parameter from `jaeckel.cpp::initial_guess`
  (Brenner-Subrahmanyam uses the forward price, strike is redundant).
- Removed dead `prev_sigma` local in `implied_vol`.
- Two `TEST_CASE` names: `≈` → `~=` (Windows CTest cannot handle Unicode in
  test-name filter args).

## [0.1.0] - unreleased (superseded by 0.2.0)

### Added
- Black-Scholes-Merton pricing for European calls and puts
- Jaeckel "Let's Be Rational" implied volatility solver (full 64-bit precision)
- Analytic Greeks: delta, gamma, theta (per day), vega (per 1%), rho (per 1%)
- Vectorized batch pricing and IV solving via NumPy arrays
- `greeks_table()` returning pandas DataFrame
- Interactive Brokers data adapter via `ib_async`
- Chain enrichment: `enrich()` adds IV + Greeks to any chain DataFrame
- Visualization: IV smile plots, payoff diagrams, Greeks profiles
- 5 Jupyter notebook examples
