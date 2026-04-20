# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-04-XX

### Added
- Packaging: `cibuildwheel` config + release workflow builds wheels for CPython
  3.10–3.13 on linux (manylinux2014) / macos / windows on tag push
- TestPyPI dry-run via `workflow_dispatch` input `publish_to_testpypi`
- `RELEASING.md` documenting the release process
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
