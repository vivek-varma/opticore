# Architecture Decision Records

This directory captures the reasoning behind non-obvious technical choices so future contributors (and future-us) don't re-litigate settled questions.

## Format

Each ADR is a short markdown file named `NNNN-kebab-case-title.md`. Structure:

```markdown
# NNNN — Title

**Status:** Accepted | Superseded by NNNN | Deprecated
**Date:** YYYY-MM-DD

## Context
What's the problem and constraints?

## Decision
What did we choose?

## Consequences
What do we gain and give up?

## Alternatives considered
What else did we look at, and why not?
```

## Index

| # | Title | Status |
|---|---|---|
| [0001](0001-nanobind-over-pybind11.md) | Use nanobind instead of pybind11 for Python bindings | Accepted |
| [0002](0002-nan-propagation-not-exceptions.md) | Numerical edge cases return NaN, never raise | Accepted |
| [0003](0003-newton-raphson-iv-solver.md) | Use Newton-Raphson for IV in Phase 1, defer real Jaeckel to Phase 2 | Accepted |
| [0004](0004-ephemeral-ibkr-connection.md) | IBKR connections are ephemeral (connect → fetch → disconnect) | Accepted |
| [0005](0005-apache-2-license.md) | License the project under Apache-2.0 | Accepted |

## When to write a new ADR

- Choosing between libraries / frameworks / algorithms where the trade-off isn't obvious
- Committing to an API shape that will be hard to change later
- Revisiting or reversing a prior ADR (write a new one with `Status: Superseded by ...`)

Skip for: bug fixes, routine refactors, matters of style.
