# 0005 — License the project under Apache-2.0

**Status:** Accepted
**Date:** 2026-04-05

## Context

License choice for an open-source quantitative finance library has real consequences:

- **Permissive** licenses (MIT, BSD, Apache-2.0) let commercial users integrate without disclosing their own source. This maximizes adoption.
- **Copyleft** licenses (GPL, AGPL) force downstream users to also open-source their code. This protects contributors from proprietary forks but scares off commercial adoption — which is ~80% of the serious users in this space.

Our competitive landscape:

- **QuantLib** — BSD-3-Clause (permissive)
- **py_vollib** — MIT (permissive)
- **FinancePy** — GPL-3.0 (copyleft) ← blocks commercial users
- **Pyfolio / zipline** — Apache-2.0

We explicitly target the users who can't use FinancePy because of its GPL.

## Decision

**Apache-2.0** across the entire project — C++ source, Python source, CMake modules, notebooks.

## Consequences

**Gains:**
- **Commercial adoption is unblocked.** Hedge funds, prop shops, fintech startups can link OptiCore into proprietary stacks.
- **Explicit patent grant.** Apache-2.0 includes a patent license that MIT and BSD do not. Important in a field (options math) where algorithmic patents historically exist (e.g., Jaeckel's own work has been referenced in patents).
- **Requires preservation of NOTICE file** on redistribution — gives us a minimal credit mechanism without being onerous.
- **Compatible with GPL-3** (downstream users can combine our code into a GPL-3 project) but not GPL-2 (acceptable — GPL-2 is fading).

**Give up:**
- Downstream proprietary forks are legal. We can't prevent a closed-source "OptiCore Pro" built on top of us. Accepted: the whole point of permissive licensing is that adoption > control.
- Apache-2.0 boilerplate header is longer than MIT's. Mitigation: we only require it in new source files, not one-off examples.

## Policy

- New source files must include the Apache-2.0 header (short form acceptable: `SPDX-License-Identifier: Apache-2.0`).
- Contributions are implicitly Apache-2.0 under the Apache-2.0 Contributor License Agreement (Section 5 of the license itself). No separate CLA needed.
- Third-party code must be license-compatible (permissive or Apache-2.0-compatible copyleft). BSD/MIT/ISC OK; GPL not OK. Check before adding any dependency.

## Alternatives considered

- **MIT** — shorter, equally permissive, but lacks the patent grant. Rejected for this project given the math-algorithm patent exposure.
- **BSD-3-Clause** — matches QuantLib but lacks the patent grant. Same reasoning as MIT.
- **GPL-3.0** — would force all downstream users to open-source. Rejected: FinancePy already occupies this niche and we're targeting its overflow.
- **MPL-2.0** — file-level copyleft. Interesting but unusual in this space; unfamiliar license = adoption friction.
- **Dual license (Apache-2.0 + commercial)** — overkill for Phase 1; revisit if someone actually offers money for a commercial-only variant.
