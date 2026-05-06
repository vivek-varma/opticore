# Thank you for contributing to OptiCore!

Please review the [AGENT.md](https://github.com/vivek-varma/opticore/blob/main/AGENT.md) for project context before submitting.

## Checklist

- [ ] Tests added / updated — C++ tests pass (`./build_and_test.sh`) and Python tests pass (`pytest tests/python/`)
- [ ] Numerical accuracy verified (see tolerance ladder in AGENT.md — do not tighten tolerances without asking)
- [ ] CHANGELOG.md updated with a brief description of the change
- [ ] Lint clean (`cmake --build build --target lint 2>/dev/null || cmake --build build 2>&1 | grep -v "^--"`)
- [ ] If changing the Python API: `python -c "import opticore; print(opticore.__version__)"` works
- [ ] If adding C++ code: new symbols are exported in `src/bindings.cpp` with nanobind ndarray tag
- [ ] This PR targets the `main` branch

## Notes for Phase 1 contributors

Phase 1 scope is locked to 6 functions (see ROADMAP.md). Please do not expand scope without an ADR. If your change touches `jaeckel.cpp`, the C++ test reference values, or the tolerance ladder — please ask first.

## Questions?

Open a discussion at https://github.com/vivek-varma/opticore/discussions
