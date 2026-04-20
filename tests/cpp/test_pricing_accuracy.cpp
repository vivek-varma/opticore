#include <catch2/catch_test_macros.hpp>
#include <catch2/catch_approx.hpp>
#include <catch2/generators/catch_generators.hpp>
#include <cmath>
#include <sstream>
#include <string>

#include "opticore/bsm.hpp"
#include "reference_values.hpp"

using Catch::Approx;
using namespace opticore;
using namespace opticore::test;

// ============================================================================
// Reference value tests: verify BSM pricing against 20 pre-computed cases
// spanning ATM/ITM/OTM, low/high vol, short/long expiry, with/without divs.
//
// Tolerance: 1e-10 relative error — this is essentially machine precision
// for BSM. If these fail, the formula is wrong.
// ============================================================================

TEST_CASE("BSM call prices match reference values", "[accuracy][bsm]") {
    for (size_t i = 0; i < N_REF_CASES; ++i) {
        const auto& c = REF_CASES[i];
        double computed = bsm_call(c.S, c.K, c.T, c.r, c.sigma, c.q);

        INFO("Case: " << c.desc);
        INFO("S=" << c.S << " K=" << c.K << " T=" << c.T
             << " r=" << c.r << " sigma=" << c.sigma << " q=" << c.q);
        INFO("Expected: " << c.call_price << "  Computed: " << computed);

        REQUIRE(computed == Approx(c.call_price).epsilon(1e-10));
    }
}

TEST_CASE("BSM put prices match reference values", "[accuracy][bsm]") {
    for (size_t i = 0; i < N_REF_CASES; ++i) {
        const auto& c = REF_CASES[i];
        double computed = bsm_put(c.S, c.K, c.T, c.r, c.sigma, c.q);

        INFO("Case: " << c.desc);
        REQUIRE(computed == Approx(c.put_price).epsilon(1e-10));
    }
}

// ============================================================================
// Put-call parity: C - P = S*exp(-qT) - K*exp(-rT)
//
// This is a mathematical identity that MUST hold for any correct
// implementation. Testing to 1e-12 (essentially machine precision).
// ============================================================================

TEST_CASE("Put-call parity across all reference cases", "[accuracy][parity]") {
    for (size_t i = 0; i < N_REF_CASES; ++i) {
        const auto& c = REF_CASES[i];
        double call = bsm_call(c.S, c.K, c.T, c.r, c.sigma, c.q);
        double put  = bsm_put(c.S, c.K, c.T, c.r, c.sigma, c.q);

        double lhs = call - put;
        double rhs = c.S * std::exp(-c.q * c.T) - c.K * std::exp(-c.r * c.T);

        INFO("Case: " << c.desc);
        INFO("C - P = " << lhs << "  S*exp(-qT) - K*exp(-rT) = " << rhs);

        REQUIRE(std::abs(lhs - rhs) < 1e-12);
    }
}

// ============================================================================
// Monotonicity properties: mathematical invariants that must hold
// ============================================================================

TEST_CASE("Call prices decrease with strike", "[accuracy][monotonicity]") {
    // For fixed S, T, r, sigma, q: C(K) is decreasing in K
    double S = 100, T = 1.0, r = 0.05, sigma = 0.20;

    double prev_price = INF;
    for (double K = 50; K <= 150; K += 5) {
        double price = bsm_call(S, K, T, r, sigma);
        INFO("K=" << K << " price=" << price);
        REQUIRE(price < prev_price);
        prev_price = price;
    }
}

TEST_CASE("Put prices increase with strike", "[accuracy][monotonicity]") {
    double S = 100, T = 1.0, r = 0.05, sigma = 0.20;

    double prev_price = -INF;
    for (double K = 50; K <= 150; K += 5) {
        double price = bsm_put(S, K, T, r, sigma);
        INFO("K=" << K << " price=" << price);
        REQUIRE(price > prev_price);
        prev_price = price;
    }
}

TEST_CASE("Call prices increase with volatility", "[accuracy][monotonicity]") {
    double S = 100, K = 100, T = 1.0, r = 0.05;

    double prev_price = -INF;
    for (double vol = 0.05; vol <= 1.0; vol += 0.05) {
        double price = bsm_call(S, K, T, r, vol);
        INFO("vol=" << vol << " price=" << price);
        REQUIRE(price > prev_price);
        prev_price = price;
    }
}

TEST_CASE("Call prices increase with expiry", "[accuracy][monotonicity]") {
    double S = 100, K = 100, r = 0.05, sigma = 0.20;

    double prev_price = -INF;
    for (double T = 0.01; T <= 5.0; T += 0.1) {
        double price = bsm_call(S, K, T, r, sigma);
        INFO("T=" << T << " price=" << price);
        REQUIRE(price >= prev_price);  // non-decreasing (equal possible at boundaries)
        prev_price = price;
    }
}

TEST_CASE("Call delta between 0 and 1", "[accuracy][monotonicity]") {
    for (size_t i = 0; i < N_REF_CASES; ++i) {
        const auto& c = REF_CASES[i];
        INFO("Case: " << c.desc);
        REQUIRE(c.call_delta >= 0.0);
        REQUIRE(c.call_delta <= 1.0);
    }
}

TEST_CASE("Put delta between -1 and 0", "[accuracy][monotonicity]") {
    for (size_t i = 0; i < N_REF_CASES; ++i) {
        const auto& c = REF_CASES[i];
        INFO("Case: " << c.desc);
        REQUIRE(c.put_delta >= -1.0);
        REQUIRE(c.put_delta <= 0.0);
    }
}

TEST_CASE("Gamma is always non-negative", "[accuracy][monotonicity]") {
    for (size_t i = 0; i < N_REF_CASES; ++i) {
        const auto& c = REF_CASES[i];
        INFO("Case: " << c.desc);
        REQUIRE(c.gamma >= 0.0);
    }
}

TEST_CASE("Vega is always non-negative", "[accuracy][monotonicity]") {
    for (size_t i = 0; i < N_REF_CASES; ++i) {
        const auto& c = REF_CASES[i];
        INFO("Case: " << c.desc);
        REQUIRE(c.vega >= 0.0);
    }
}

// ============================================================================
// Arbitrage bounds: option prices must satisfy no-arbitrage constraints
// ============================================================================

TEST_CASE("Call price bounds: max(S*exp(-qT) - K*exp(-rT), 0) <= C <= S*exp(-qT)",
          "[accuracy][bounds]") {
    for (size_t i = 0; i < N_REF_CASES; ++i) {
        const auto& c = REF_CASES[i];
        double call = bsm_call(c.S, c.K, c.T, c.r, c.sigma, c.q);

        double lower = std::max(c.S * std::exp(-c.q * c.T) - c.K * std::exp(-c.r * c.T), 0.0);
        double upper = c.S * std::exp(-c.q * c.T);

        INFO("Case: " << c.desc);
        INFO("Lower: " << lower << "  Call: " << call << "  Upper: " << upper);

        REQUIRE(call >= lower - 1e-12);
        REQUIRE(call <= upper + 1e-12);
    }
}

TEST_CASE("Put price bounds: max(K*exp(-rT) - S*exp(-qT), 0) <= P <= K*exp(-rT)",
          "[accuracy][bounds]") {
    for (size_t i = 0; i < N_REF_CASES; ++i) {
        const auto& c = REF_CASES[i];
        double put = bsm_put(c.S, c.K, c.T, c.r, c.sigma, c.q);

        double lower = std::max(c.K * std::exp(-c.r * c.T) - c.S * std::exp(-c.q * c.T), 0.0);
        double upper = c.K * std::exp(-c.r * c.T);

        INFO("Case: " << c.desc);
        INFO("Lower: " << lower << "  Put: " << put << "  Upper: " << upper);

        REQUIRE(put >= lower - 1e-12);
        REQUIRE(put <= upper + 1e-12);
    }
}

// ============================================================================
// Extreme parameter tests: very deep ITM/OTM, very short/long expiry
// ============================================================================

TEST_CASE("Deep ITM call converges to S - K*exp(-rT)", "[accuracy][extreme]") {
    // When S >> K, call should approach forward - discounted strike
    double S = 1000, K = 100, T = 1.0, r = 0.05, sigma = 0.20;
    double call = bsm_call(S, K, T, r, sigma);
    double expected = S - K * std::exp(-r * T);

    INFO("Deep ITM call: " << call << "  Expected: " << expected);
    REQUIRE(call == Approx(expected).epsilon(1e-8));
}

TEST_CASE("Deep OTM call converges to 0", "[accuracy][extreme]") {
    double S = 100, K = 10000, T = 1.0, r = 0.05, sigma = 0.20;
    double call = bsm_call(S, K, T, r, sigma);

    INFO("Deep OTM call: " << call);
    REQUIRE(call < 1e-20);
    REQUIRE(call >= 0.0);
}

TEST_CASE("Deep ITM put converges to K*exp(-rT) - S", "[accuracy][extreme]") {
    double S = 10, K = 1000, T = 1.0, r = 0.05, sigma = 0.20;
    double put = bsm_put(S, K, T, r, sigma);
    double expected = K * std::exp(-r * T) - S;

    INFO("Deep ITM put: " << put << "  Expected: " << expected);
    REQUIRE(put == Approx(expected).epsilon(1e-8));
}

TEST_CASE("Deep OTM put converges to 0", "[accuracy][extreme]") {
    double S = 10000, K = 100, T = 1.0, r = 0.05, sigma = 0.20;
    double put = bsm_put(S, K, T, r, sigma);

    INFO("Deep OTM put: " << put);
    REQUIRE(put < 1e-20);
    REQUIRE(put >= 0.0);
}

TEST_CASE("Very short expiry matches intrinsic", "[accuracy][extreme]") {
    double S = 105, K = 100, r = 0.05, sigma = 0.20;
    double T = 1e-8;  // essentially zero time

    double call = bsm_call(S, K, T, r, sigma);
    double intrinsic = S - K;  // Call is ITM by 5

    INFO("Short expiry call: " << call << "  Intrinsic: " << intrinsic);
    REQUIRE(call == Approx(intrinsic).epsilon(1e-6));
}

TEST_CASE("Very long expiry call approaches S*exp(-qT)", "[accuracy][extreme]") {
    // For very long expiry, call approaches spot (minus dividends)
    double S = 100, K = 100, r = 0.05, sigma = 0.20, q = 0.0;
    double T = 100.0;

    double call = bsm_call(S, K, T, r, sigma, q);

    INFO("Long expiry call: " << call);
    // With no dividends, should approach S
    REQUIRE(call < S);
    REQUIRE(call > 0.9 * S);
}

// ============================================================================
// Edge cases: zero/boundary values
// ============================================================================

TEST_CASE("Zero volatility edge case", "[accuracy][edge]") {
    // Zero vol means deterministic payoff
    double S = 100, K = 95, T = 1.0, r = 0.05;

    double call = bsm_call(S, K, T, r, 0.0);
    double F = S * std::exp(r * T);
    double expected = std::max(F - K, 0.0) * std::exp(-r * T);

    REQUIRE(call == Approx(expected).epsilon(1e-12));
}

TEST_CASE("Zero time edge case", "[accuracy][edge]") {
    // At expiry: price = max(S - K, 0)
    REQUIRE(bsm_call(105, 100, 0.0, 0.05, 0.20) == Approx(5.0));
    REQUIRE(bsm_call(95,  100, 0.0, 0.05, 0.20) == Approx(0.0));
    REQUIRE(bsm_put(105,  100, 0.0, 0.05, 0.20) == Approx(0.0));
    REQUIRE(bsm_put(95,   100, 0.0, 0.05, 0.20) == Approx(5.0));
}

TEST_CASE("Negative rate works correctly", "[accuracy][edge]") {
    // Negative rates are legal (some currencies had them)
    double call = bsm_call(100, 100, 1.0, -0.02, 0.20);
    INFO("Negative rate call: " << call);
    REQUIRE(call > 0.0);
    REQUIRE(std::isfinite(call));
}

TEST_CASE("Invalid inputs return NaN", "[accuracy][edge]") {
    REQUIRE(std::isnan(bsm_call(-100, 100, 1.0, 0.05, 0.20)));  // negative spot
    REQUIRE(std::isnan(bsm_call(100, -100, 1.0, 0.05, 0.20)));  // negative strike
    REQUIRE(std::isnan(bsm_call(100, 100, 1.0, 0.05, -0.20))); // negative vol
    REQUIRE(std::isnan(bsm_call(0.0, 100, 1.0, 0.05, 0.20)));  // zero spot
    REQUIRE(std::isnan(bsm_call(100, 0.0, 1.0, 0.05, 0.20)));  // zero strike
}
