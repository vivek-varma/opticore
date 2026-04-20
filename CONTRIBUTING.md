# Contributing to OptiCore

Thanks for your interest in contributing! Here's how to get started.

## Development setup

```bash
git clone https://github.com/opticore/opticore.git
cd opticore
pip install -e ".[dev]"
```

## Running tests

```bash
# Python tests
pytest tests/python/ -v

# C++ tests
cmake -B build -DOPTICORE_BUILD_TESTS=ON
cmake --build build
ctest --test-dir build --output-on-failure
```

## Code style

- **C++**: clang-format with LLVM style, 100 column limit
- **Python**: ruff (format + lint). Run `ruff check .` and `ruff format .`

Both are enforced in CI.

## Submitting changes

1. Fork the repo and create a branch from `main`
2. Add tests for any new functionality
3. Ensure all tests pass locally
4. Open a pull request with a clear description

## Adding a new pricing model

1. Add C++ header in `include/opticore/` and implementation in `src/`
2. Add nanobind binding in `src/bindings.cpp`
3. Add Python wrapper in `python/opticore/__init__.py`
4. Add tests in both `tests/cpp/` and `tests/python/`
5. Add a Jupyter notebook example in `notebooks/`

## Reporting bugs

Open a GitHub issue with:
- What you expected to happen
- What actually happened
- Minimal code to reproduce
- Your OS and Python version
