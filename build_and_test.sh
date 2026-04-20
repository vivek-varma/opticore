#!/usr/bin/env bash
# OptiCore — build and run the full C++ accuracy test suite.
#
# Usage:  ./build_and_test.sh
#
# Requires: cmake >= 3.20, a C++20 compiler (g++ 11+, clang 14+, or MSVC 2022+),
#           internet access (CMake will fetch Catch2 v3.5.4 on first build).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "  OptiCore C++ build & test"
echo "=========================================="

# 1. Configure
echo ""
echo "[1/3] Configuring CMake..."
cmake -B build \
      -DOPTICORE_BUILD_TESTS=ON \
      -DOPTICORE_BUILD_PYTHON=OFF \
      -DCMAKE_BUILD_TYPE=Release

# 2. Build
echo ""
echo "[2/3] Building (this may take 1-2 min on first run while Catch2 downloads)..."
cmake --build build --config Release -j

# 3. Test
echo ""
echo "[3/3] Running test suite..."
echo ""
./build/opticore_tests

echo ""
echo "=========================================="
echo "  Done. Expected: 96 test cases / 1653+ assertions all passing."
echo "=========================================="
