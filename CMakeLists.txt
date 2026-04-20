cmake_minimum_required(VERSION 3.20)
project(opticore VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# ─── Options ────────────────────────────────────────────────────────────────
option(OPTICORE_BUILD_TESTS "Build C++ tests" ON)
option(OPTICORE_BUILD_BENCHMARKS "Build C++ benchmarks" OFF)
option(OPTICORE_BUILD_PYTHON "Build Python bindings" ON)

# ─── Core library (static) ─────────────────────────────────────────────────
add_library(opticore_core STATIC
    src/bsm.cpp
    src/jaeckel.cpp
    src/greeks.cpp
)

target_include_directories(opticore_core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_compile_options(opticore_core PRIVATE
    $<$<CXX_COMPILER_ID:GNU,Clang,AppleClang>:-O3 -march=native -Wall -Wextra>
    $<$<CXX_COMPILER_ID:MSVC>:/O2 /W4>
)

# ─── Python bindings (nanobind) ─────────────────────────────────────────────
if(OPTICORE_BUILD_PYTHON)
    # Find Python and nanobind
    find_package(Python 3.10
        REQUIRED COMPONENTS Interpreter Development.Module
        OPTIONAL_COMPONENTS Development.SABIModule
    )

    # Try to find nanobind via pip-installed package
    execute_process(
        COMMAND "${Python_EXECUTABLE}" -m nanobind --cmake_dir
        OUTPUT_STRIP_TRAILING_WHITESPACE
        OUTPUT_VARIABLE nanobind_ROOT
        RESULT_VARIABLE nanobind_FOUND
    )

    if(nanobind_FOUND EQUAL 0)
        list(APPEND CMAKE_PREFIX_PATH "${nanobind_ROOT}")
    endif()

    find_package(nanobind CONFIG REQUIRED)

    nanobind_add_module(_core
        src/bindings.cpp
    )

    target_link_libraries(_core PRIVATE opticore_core)

    # Install the module into the Python package directory
    install(TARGETS _core LIBRARY DESTINATION opticore)
endif()

# ─── C++ Tests (Catch2) ────────────────────────────────────────────────────
if(OPTICORE_BUILD_TESTS)
    enable_testing()

    # Try to find Catch2; if not found, fetch it
    find_package(Catch2 3 QUIET)
    if(NOT Catch2_FOUND)
        include(FetchContent)
        FetchContent_Declare(
            Catch2
            GIT_REPOSITORY https://github.com/catchorg/Catch2.git
            GIT_TAG        v3.5.4
        )
        FetchContent_MakeAvailable(Catch2)
    endif()

    add_executable(opticore_tests
        tests/cpp/test_bsm.cpp
        tests/cpp/test_accuracy.cpp
        tests/cpp/test_pricing_accuracy.cpp
        tests/cpp/test_iv_accuracy.cpp
        tests/cpp/test_greeks_accuracy.cpp
    )

    target_link_libraries(opticore_tests PRIVATE
        opticore_core
        Catch2::Catch2WithMain
    )

    include(CTest)
    include(Catch)
    catch_discover_tests(opticore_tests)
endif()
