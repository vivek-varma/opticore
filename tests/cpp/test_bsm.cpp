#include <catch2/catch_test_macros.hpp>
#include <catch2/catch_approx.hpp>
#include <cmath>
#include <random>

#include "opticore/bsm.hpp"
#include "opticore/jaeckel.hpp"
#include "opticore/greeks.hpp"

using Catch::Approx;
using namespace opticore;

// ============================================================================
// Reference values from Hull "Options, Futures, and Other Derivatives"
// and independent verification via Wolfram Alpha
// ============================================================================

TEST_CASE("BSM call price - Hull example", "[bsm]") {
    // S=42, K=40, T=0.5, r=10%, vol=20%, q=0
    // Expected call price ≈ 4.7594
    double price = bsm_call(42.0, 40.0, 0.5, 0.10, 0.20, 0.0);
    REQUIRE(price == Approx(4.7594).margin(0.001));
}

TEST_CASE("BSM put price - Hull example", "[bsm]") {
    // Same params, expected put price ≈ 0.8086
    double price = bsm_put(42.0, 40.0, 0.5, 0.10, 0.20, 0.0);
    REQUIRE(price == Approx(0.8086).margin(0.001));
}

TEST_CASE("BSM put-call parity", "[bsm]") {
    // C - P = S*exp(-qT) - K*exp(-rT)
    double S = 100.0, K = 105.0, T = 1.0, r = 0.05, vol = 0.25, q = 0.02;

    double call = bsm_call(S, K, T, r, vol, q);
    double put  = bsm_put(S, K, T, r, vol, q);

    double lhs = call - put;
    double rhs = S * std::exp(-q * T) - K * std::exp(-r * T);

    REQUIRE(lhs == Approx(rhs).margin(1e-10));
}

TEST_CASE("BSM ATM call price", "[bsm]") {
    // S=K=100, T=1, r=5%, vol=20%
    double price = bsm_call(100.0, 100.0, 1.0, 0.05, 0.20, 0.0);
    REQUIRE(price == Approx(10.4506).margin(0.001));
}

TEST_CASE("BSM edge case - zero time", "[bsm]") {
    // At expiry, call = max(S-K, 0)
    REQUIRE(bsm_call(105.0, 100.0, 0.0, 0.05, 0.20) == Approx(5.0));
    REQUIRE(bsm_call(95.0, 100.0, 0.0, 0.05, 0.20)  == Approx(0.0));
    REQUIRE(bsm_put(95.0, 100.0, 0.0, 0.05, 0.20)    == Approx(5.0));
}

TEST_CASE("BSM edge case - zero vol", "[bsm]") {
    // Zero vol = deterministic forward
    // Call = max(F - K, 0) * exp(-rT)
    double S = 100.0, K = 95.0, T = 1.0, r = 0.05;
    double F = S * std::exp(r * T);
    double expected = std::max(F - K, 0.0) * std::exp(-r * T);
    REQUIRE(bsm_call(S, K, T, r, 0.0, 0.0) == Approx(expected).margin(1e-10));
}

TEST_CASE("BSM with dividends", "[bsm]") {
    // S=100, K=100, T=1, r=5%, vol=20%, q=3%
    // Verified independently: call = 8.6525285539
    double price = bsm_call(100.0, 100.0, 1.0, 0.05, 0.20, 0.03);
    REQUIRE(price == Approx(8.6525285539).margin(0.0001));
}

// ============================================================================
// Implied volatility tests
// ============================================================================

TEST_CASE("IV round-trip - ATM call", "[iv]") {
    double vol = 0.25;
    double S = 100, K = 100, T = 1.0, r = 0.05;
    double price = bsm_call(S, K, T, r, vol, 0.0);

    double solved_vol = implied_vol(price, S, K, T, r, 0.0, true);
    REQUIRE(solved_vol == Approx(vol).margin(1e-10));
}

TEST_CASE("IV round-trip - OTM put", "[iv]") {
    double vol = 0.30;
    double S = 100, K = 80, T = 0.5, r = 0.05;
    double price = bsm_put(S, K, T, r, vol, 0.0);

    double solved_vol = implied_vol(price, S, K, T, r, 0.0, false);
    REQUIRE(solved_vol == Approx(vol).margin(1e-8));
}

TEST_CASE("IV round-trip - deep ITM call", "[iv]") {
    double vol = 0.15;
    double S = 100, K = 60, T = 2.0, r = 0.03;
    double price = bsm_call(S, K, T, r, vol, 0.0);

    double solved_vol = implied_vol(price, S, K, T, r, 0.0, true);
    REQUIRE(solved_vol == Approx(vol).margin(1e-6));
}

TEST_CASE("IV round-trip - many random cases", "[iv]") {
    // Seed for reproducibility
    std::mt19937 rng(42);
    std::uniform_real_distribution<> spot_dist(50, 200);
    std::uniform_real_distribution<> vol_dist(0.05, 1.0);
    std::uniform_real_distribution<> time_dist(0.01, 5.0);

    int n_tests = 100;
    int n_passed = 0;

    for (int i = 0; i < n_tests; ++i) {
        double S = spot_dist(rng);
        double K = S * (0.5 + std::uniform_real_distribution<>(0, 1.0)(rng));
        double T = time_dist(rng);
        double vol = vol_dist(rng);
        double r = 0.05;
        bool is_call = (i % 2 == 0);

        double price = bsm_price(S, K, T, r, vol, 0.0, is_call);

        if (price > 0 && std::isfinite(price)) {
            double solved = implied_vol(price, S, K, T, r, 0.0, is_call);
            if (std::isfinite(solved) && std::abs(solved - vol) < 1e-4) {
                n_passed++;
            }
        } else {
            n_passed++;  // edge case, skip
        }
    }

    REQUIRE(n_passed >= 90);  // at least 90% should round-trip
}

TEST_CASE("IV - invalid price returns NaN", "[iv]") {
    // Negative price
    REQUIRE(std::isnan(implied_vol(-1.0, 100, 100, 1.0, 0.05, 0.0, true)));

    // Price above spot (for call) = arbitrage
    double max_call = 100.0;  // undiscounted forward
    double result = implied_vol(max_call + 10, 100, 100, 1.0, 0.05, 0.0, true);
    REQUIRE(std::isnan(result));
}

// ============================================================================
// Greeks tests
// ============================================================================

TEST_CASE("Greeks - ATM call delta near 0.5", "[greeks]") {
    auto g = compute_greeks(100, 100, 1.0, 0.05, 0.20, 0.0, true);
    // ATM call delta should be slightly above 0.5 due to drift
    REQUIRE(g.delta > 0.5);
    REQUIRE(g.delta < 0.7);
}

TEST_CASE("Greeks - put delta is negative", "[greeks]") {
    auto g = compute_greeks(100, 100, 1.0, 0.05, 0.20, 0.0, false);
    REQUIRE(g.delta < 0.0);
    REQUIRE(g.delta > -1.0);
}

TEST_CASE("Greeks - call + put delta = exp(-qT)", "[greeks]") {
    double S = 100, K = 105, T = 0.5, r = 0.05, vol = 0.25, q = 0.02;

    auto gc = compute_greeks(S, K, T, r, vol, q, true);
    auto gp = compute_greeks(S, K, T, r, vol, q, false);

    double sum = gc.delta + std::abs(gp.delta);
    REQUIRE(sum == Approx(std::exp(-q * T)).margin(1e-8));
}

TEST_CASE("Greeks - gamma is positive", "[greeks]") {
    auto g = compute_greeks(100, 100, 1.0, 0.05, 0.20, 0.0, true);
    REQUIRE(g.gamma > 0.0);
}

TEST_CASE("Greeks - gamma same for call and put", "[greeks]") {
    double S = 100, K = 105, T = 0.5, r = 0.05, vol = 0.25;

    auto gc = compute_greeks(S, K, T, r, vol, 0.0, true);
    auto gp = compute_greeks(S, K, T, r, vol, 0.0, false);

    REQUIRE(gc.gamma == Approx(gp.gamma).margin(1e-12));
}

TEST_CASE("Greeks - vega same for call and put", "[greeks]") {
    double S = 100, K = 105, T = 0.5, r = 0.05, vol = 0.25;

    auto gc = compute_greeks(S, K, T, r, vol, 0.0, true);
    auto gp = compute_greeks(S, K, T, r, vol, 0.0, false);

    REQUIRE(gc.vega == Approx(gp.vega).margin(1e-12));
}

TEST_CASE("Greeks - theta is negative for long options", "[greeks]") {
    auto gc = compute_greeks(100, 100, 1.0, 0.05, 0.20, 0.0, true);
    REQUIRE(gc.theta < 0.0);  // time decay

    auto gp = compute_greeks(100, 100, 1.0, 0.05, 0.20, 0.0, false);
    REQUIRE(gp.theta < 0.0);
}

TEST_CASE("Greeks - price matches bsm_price", "[greeks]") {
    double S = 100, K = 105, T = 0.5, r = 0.05, vol = 0.25;

    auto g = compute_greeks(S, K, T, r, vol, 0.0, true);
    double p = bsm_call(S, K, T, r, vol, 0.0);

    REQUIRE(g.price == Approx(p).margin(1e-12));
}
