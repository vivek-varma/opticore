#include <catch2/catch_test_macros.hpp>
#include <catch2/catch_approx.hpp>
#include <cmath>
#include <random>
#include <vector>

#include "opticore/bsm.hpp"
#include "opticore/jaeckel.hpp"
#include "reference_values.hpp"

using Catch::Approx;
using namespace opticore;
using namespace opticore::test;

// ============================================================================
// Round-trip tests: price -> IV -> should recover original vol
//
// For all reference cases, compute the BSM price, then solve for IV.
// The solved IV must match the original within 1e-10.
// ============================================================================

TEST_CASE("IV round-trip: all reference cases (call)", "[accuracy][iv]") {
    for (size_t i = 0; i < N_REF_CASES; ++i) {
        const auto& c = REF_CASES[i];

        double price = bsm_call(c.S, c.K, c.T, c.r, c.sigma, c.q);
        double solved = implied_vol(price, c.S, c.K, c.T, c.r, c.q, true);

        INFO("Case: " << c.desc);
        INFO("True vol: " << c.sigma << "  Solved: " << solved);
        REQUIRE(solved == Approx(c.sigma).epsilon(1e-10));
    }
}

TEST_CASE("IV round-trip: all reference cases (put)", "[accuracy][iv]") {
    for (size_t i = 0; i < N_REF_CASES; ++i) {
        const auto& c = REF_CASES[i];

        double price = bsm_put(c.S, c.K, c.T, c.r, c.sigma, c.q);
        double solved = implied_vol(price, c.S, c.K, c.T, c.r, c.q, false);

        INFO("Case: " << c.desc);
        INFO("True vol: " << c.sigma << "  Solved: " << solved);
        REQUIRE(solved == Approx(c.sigma).epsilon(1e-10));
    }
}

// ============================================================================
// Fuzzing: 1000 random parameter sets
//
// Generate random parameters within reasonable bounds and verify that
// price -> IV round-trips successfully. We count successes and require
// a minimum success rate.
// ============================================================================

TEST_CASE("IV round-trip: 1000 random parameter sets", "[accuracy][iv][fuzz]") {
    std::mt19937 rng(12345);  // fixed seed for reproducibility
    std::uniform_real_distribution<> spot_dist(10, 1000);
    std::uniform_real_distribution<> moneyness_dist(0.5, 1.5);
    std::uniform_real_distribution<> time_dist(0.01, 5.0);
    std::uniform_real_distribution<> rate_dist(-0.02, 0.15);
    std::uniform_real_distribution<> vol_dist(0.05, 1.5);
    std::uniform_real_distribution<> div_dist(0.0, 0.08);

    int n_tests = 1000;
    int n_passed = 0;
    int n_arbitrage = 0;
    double max_error = 0.0;
    double worst_case_sigma = 0.0;
    double worst_case_solved = 0.0;

    for (int i = 0; i < n_tests; ++i) {
        double S = spot_dist(rng);
        double K = S * moneyness_dist(rng);
        double T = time_dist(rng);
        double r = rate_dist(rng);
        double sigma = vol_dist(rng);
        double q = div_dist(rng);
        bool is_call = (i % 2 == 0);

        double price = bsm_price(S, K, T, r, sigma, q, is_call);

        if (!std::isfinite(price) || price < 1e-12) {
            n_arbitrage++;
            continue;
        }

        double solved = implied_vol(price, S, K, T, r, q, is_call);

        if (!std::isfinite(solved)) {
            continue;
        }

        double err = std::abs(solved - sigma) / sigma;
        if (err > max_error) {
            max_error = err;
            worst_case_sigma = sigma;
            worst_case_solved = solved;
        }

        if (err < 1e-8) {
            n_passed++;
        }
    }

    INFO("Passed: " << n_passed << "/" << (n_tests - n_arbitrage));
    INFO("Max relative error: " << max_error);
    INFO("Worst case: true=" << worst_case_sigma
         << " solved=" << worst_case_solved);

    // Require at least 99% of valid cases to round-trip
    REQUIRE(n_passed >= (n_tests - n_arbitrage) * 99 / 100);
    REQUIRE(max_error < 1e-6);  // max 1 part per million error
}

// ============================================================================
// Moneyness sweep: IV solver accuracy across strike range
// ============================================================================

TEST_CASE("IV round-trip: moneyness sweep", "[accuracy][iv]") {
    double S = 100, T = 1.0, r = 0.05, sigma = 0.25;

    double max_err = 0.0;
    for (double K = 50; K <= 200; K += 5) {
        for (bool is_call : {true, false}) {
            double price = bsm_price(S, K, T, r, sigma, 0.0, is_call);
            if (price < 1e-10) continue;

            double solved = implied_vol(price, S, K, T, r, 0.0, is_call);
            double err = std::abs(solved - sigma);
            if (err > max_err) max_err = err;

            INFO("K=" << K << " kind=" << (is_call ? "call" : "put")
                 << " true=" << sigma << " solved=" << solved);
            REQUIRE(solved == Approx(sigma).epsilon(1e-10));
        }
    }

    INFO("Max error across moneyness sweep: " << max_err);
}

// ============================================================================
// Volatility sweep: IV solver across low/high vol regimes
// ============================================================================

TEST_CASE("IV round-trip: low volatility regime", "[accuracy][iv]") {
    double S = 100, K = 100, T = 1.0, r = 0.05;

    for (double sigma = 0.01; sigma <= 0.20; sigma += 0.01) {
        double price = bsm_call(S, K, T, r, sigma);
        double solved = implied_vol(price, S, K, T, r, 0.0, true);

        INFO("sigma=" << sigma << " solved=" << solved);
        // At sigma < 0.02, vega is tiny and double precision limits us to ~1e-10
        // absolute error. For sigma >= 0.02 we hit machine precision.
        double tol = (sigma < 0.02) ? 1e-9 : 1e-12;
        REQUIRE(std::abs(solved - sigma) < tol);
    }
}

TEST_CASE("IV round-trip: high volatility regime", "[accuracy][iv]") {
    double S = 100, K = 100, T = 1.0, r = 0.05;

    for (double sigma = 0.20; sigma <= 2.0; sigma += 0.1) {
        double price = bsm_call(S, K, T, r, sigma);
        double solved = implied_vol(price, S, K, T, r, 0.0, true);

        INFO("sigma=" << sigma << " solved=" << solved);
        REQUIRE(solved == Approx(sigma).epsilon(1e-10));
    }
}

// ============================================================================
// Time sweep: IV solver across short/long expiry regimes
// ============================================================================

TEST_CASE("IV round-trip: short expiry regime", "[accuracy][iv]") {
    double S = 100, K = 100, r = 0.05, sigma = 0.25;

    for (double T = 1.0/365; T <= 30.0/365; T += 1.0/365) {
        double price = bsm_call(S, K, T, r, sigma);
        double solved = implied_vol(price, S, K, T, r, 0.0, true);

        INFO("T=" << T << " solved=" << solved);
        REQUIRE(solved == Approx(sigma).epsilon(1e-8));
    }
}

TEST_CASE("IV round-trip: long expiry regime", "[accuracy][iv]") {
    double S = 100, K = 100, r = 0.05, sigma = 0.25;

    for (double T = 1.0; T <= 10.0; T += 0.5) {
        double price = bsm_call(S, K, T, r, sigma);
        double solved = implied_vol(price, S, K, T, r, 0.0, true);

        INFO("T=" << T << " solved=" << solved);
        REQUIRE(solved == Approx(sigma).epsilon(1e-10));
    }
}

// ============================================================================
// Arbitrage bounds enforcement
// ============================================================================

TEST_CASE("IV returns NaN for price below intrinsic", "[accuracy][iv]") {
    double S = 100, K = 80, T = 1.0, r = 0.05;

    // Intrinsic is ~S - K*exp(-rT) = ~100 - 76 = 24ish
    double too_low = 10.0;  // well below intrinsic
    double solved = implied_vol(too_low, S, K, T, r, 0.0, true);
    REQUIRE(std::isnan(solved));
}

TEST_CASE("IV returns NaN for price above maximum", "[accuracy][iv]") {
    double S = 100, K = 100, T = 1.0, r = 0.05;

    // Max price for call is S
    double too_high = 200.0;
    double solved = implied_vol(too_high, S, K, T, r, 0.0, true);
    REQUIRE(std::isnan(solved));
}

TEST_CASE("IV returns NaN for negative price", "[accuracy][iv]") {
    double solved = implied_vol(-5.0, 100, 100, 1.0, 0.05, 0.0, true);
    REQUIRE(std::isnan(solved));
}

TEST_CASE("IV returns 0 for zero price", "[accuracy][iv]") {
    // Zero price means zero vol (or so far OTM that it's worthless)
    double solved = implied_vol(0.0, 100, 100, 1.0, 0.05, 0.0, true);
    REQUIRE(solved == 0.0);
}

// ============================================================================
// Convergence: verify the solver doesn't need too many iterations
//
// We can't directly count iterations from the public API, but we can
// verify that it converges in reasonable time (indirectly via performance).
// ============================================================================

TEST_CASE("IV solver handles challenging ATM inputs", "[accuracy][iv]") {
    // ATM options are actually the hardest for some solvers because
    // the initial guess can oscillate. Test a range near ATM.
    double S = 100, T = 1.0, r = 0.05, sigma = 0.20;

    for (double K = 95; K <= 105; K += 0.5) {
        double price = bsm_call(S, K, T, r, sigma);
        double solved = implied_vol(price, S, K, T, r, 0.0, true);

        INFO("Near-ATM K=" << K);
        REQUIRE(solved == Approx(sigma).epsilon(1e-10));
    }
}

TEST_CASE("IV solver handles far-OTM puts with tiny prices", "[accuracy][iv]") {
    // Far OTM puts have very small prices, solver must still converge
    double S = 100, T = 1.0, r = 0.05, sigma = 0.25;

    for (double K = 50; K <= 70; K += 5) {
        double price = bsm_put(S, K, T, r, sigma);
        if (price < 1e-8) continue;  // too small to solve reliably

        double solved = implied_vol(price, S, K, T, r, 0.0, false);

        INFO("Far OTM put K=" << K << " price=" << price);
        REQUIRE(solved == Approx(sigma).epsilon(1e-8));
    }
}
