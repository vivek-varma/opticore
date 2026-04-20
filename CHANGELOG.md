# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-05-XX

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
