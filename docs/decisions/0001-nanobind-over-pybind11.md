# 0001 — Use nanobind instead of pybind11 for Python bindings

**Status:** Accepted
**Date:** 2026-04-05

## Context

OptiCore needs a C++ ↔ Python bridge that:

1. Handles NumPy arrays with zero-copy semantics (batch pricing is a core differentiator — it must not pay a per-element Python overhead).
2. Compiles fast enough that contributors don't bounce on build times.
3. Produces a small wheel so `pip install` is quick and the PyPI footprint is reasonable.
4. Has a stable ABI so we don't have to rebuild on every Python point release.

The mainstream choices are **pybind11** (ubiquitous) and **nanobind** (newer, from the same author as pybind11).

## Decision

Use **nanobind 2.x**.

## Consequences

**Gains:**
- ~4× faster compile than pybind11 on the same bindings file (measured during prototype).
- ~5× smaller compiled `_core.so`.
- Stable ABI across Python 3.10–3.13 (one wheel per platform, not per Python version).
- Cleaner ndarray API with explicit framework tags (`nb::numpy`).
- Author is the same as pybind11, so the mental model transfers.

**Give up:**
- Smaller ecosystem, fewer Stack Overflow answers (mitigated: official docs are good and our binding surface is tiny — 6 functions).
- Requires C++17/20 — not a problem since the core is already C++20.
- One gotcha we hit: ndarray return types need the `nb::numpy` framework tag explicitly, otherwise Python receives a raw DLTensor capsule that NumPy can't interpret. Documented in `AGENT.md`.

## Alternatives considered

- **pybind11** — proven, but 4× slower to compile and larger binaries. Author himself recommends nanobind for new projects.
- **Cython** — overkill; we don't want a second language in the build.
- **ctypes / cffi** — no zero-copy ndarray story, too much boilerplate for typed numerical code.
- **Pure Python + NumPy** — performance ceiling too low; the whole pitch is "faster than py_vollib without Numba".
