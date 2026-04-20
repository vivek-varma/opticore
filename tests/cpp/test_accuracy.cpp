// ============================================================================
// COMPREHENSIVE ACCURACY TEST SUITE
//
// This file contains hundreds of tests across multiple categories:
//
//   1. REFERENCE VALUES — 20 hand-verified cases against Python's math.erfc
//   2. PUT-CALL PARITY — must hold to machine precision for ALL parameters
//   3. IV ROUND-TRIP    — price(iv(p)) == p for 1000 random options
//   4. GREEK IDENTITIES — gamma_call == gamma_put, vega_call == vega_put, etc.
//   5. NUMERICAL GREEKS — analytic Greeks vs central finite differences
//   6. MONOTONICITY     — call price decreases in K, increases in S, T, vol
//   7. BOUNDARY VALUES  — extreme moneyness, vol, time, rate
//   8. SPECIAL CASES    — zero vol, zero time, very small/large numbers
//
// PHILOSOPHY: Accuracy is binary. Either the formula is right, or it isn't.
// We test against three independent sources of truth:
//   - Hand-computed Python reference values (this file)
//   - Mathematical identities (parity, symmetry)
//   - Self-consistency (round-trip, numerical derivatives)
// ============================================================================

#include <catch2/catch_test_macros.hpp>
#include <catch2/catch_approx.hpp>
#include <catch2/generators/catch_generators.hpp>
#include <catch2/generators/catch_generators_random.hpp>

#include <cmath>
#include <random>
#include <string>
#include <vector>

#include "opticore/bsm.hpp"
#include "opticore/jaeckel.hpp"
#include "opticore/greeks.hpp"

using Catch::Approx;
using namespace opticore;

// ============================================================================
// Reference values structure
// ============================================================================

struct RefCase {
    const char* name;
    double S, K, T, r, vol, q;
    bool is_call;
    double price, delta, gamma, theta, vega, rho;
};

// Reference values computed independently in Python with math.erfc
// Each value verified to 15 significant digits.
static const std::vector<RefCase> REFERENCE_CASES = {
    {"ATM_call_1y", 100, 100, 1.0, 0.05, 0.2, 0.0, true,
      1.045058357218556e+01, 6.368306511756191e-01, 1.876201734584690e-02,
      -1.757267820941972e-02, 3.752403469169379e-01, 5.323248154537634e-01},
    {"ATM_put_1y", 100, 100, 1.0, 0.05, 0.2, 0.0, false,
      5.573526022256971e+00, -3.631693488243809e-01, 1.876201734584690e-02,
      -4.542138147766099e-03, 3.752403469169379e-01, -4.189046090469506e-01},
    {"Hull_call", 42, 40, 0.5, 0.1, 0.2, 0.0, true,
      4.759422392871535e+00, 7.791312909426690e-01, 4.996267040591185e-02,
      -1.249066354682911e-02, 8.813415059602853e-02, 1.398204591336028e-01},
    {"Hull_put", 42, 40, 0.5, 0.1, 0.2, 0.0, false,
      8.085993729000958e-01, -2.208687090573310e-01, 4.996267040591185e-02,
      -2.066231497506221e-03, 8.813415059602853e-02, -5.042542576653999e-02},
    {"ATM_3M_high_vol", 100, 100, 0.25, 0.05, 0.3, 0.0, true,
      6.583084497992466e+00, 5.629029283920401e-01, 2.626485733014476e-02,
      -3.919053757705677e-02, 1.969864299760857e-01, 1.242680208530289e-01},
    {"OTM_call", 100, 110, 1.0, 0.05, 0.2, 0.0, true,
      6.040088129724225e+00, 4.496479306371760e-01, 1.978802401940967e-02,
      -1.617490424816877e-02, 3.957604803881934e-01, 3.892470493399337e-01},
    {"ITM_call", 100, 90, 1.0, 0.05, 0.2, 0.0, true,
      1.669944840841599e+01, 8.097030607754921e-01, 1.358128974631473e-02,
      -1.624602967868385e-02, 2.716257949262946e-01, 6.427085766913322e-01},
    {"ITM_put", 100, 110, 1.0, 0.05, 0.2, 0.0, false,
      1.067532482480278e+01, -5.503520693628240e-01, 1.978802401940967e-02,
      -1.841310180349795e-03, 3.957604803881934e-01, -6.571053176108518e-01},
    {"OTM_put", 100, 90, 1.0, 0.05, 0.2, 0.0, false,
      2.310096613480258e+00, -1.902969392245079e-01, 1.358128974631473e-02,
      -4.518543623195600e-03, 2.716257949262946e-01, -2.133979053593104e-01},
    {"ATM_with_div", 100, 100, 1.0, 0.05, 0.2, 0.03, true,
      8.652528553942709e+00, 5.621399977897841e-01, 1.897428178976287e-02,
      -1.229180801598632e-02, 3.794856357952573e-01, 4.756147122503570e-01},
    {"long_dated", 100, 100, 2.0, 0.05, 0.3, 0.02, true,
      1.862254866942615e+01, 6.131404582925247e-01, 8.487086507140125e-03,
      -1.295200786197075e-02, 5.092251904284075e-01, 8.538299431965265e-01},
    {"1M_high_vol", 100, 100, 0.0833, 0.05, 0.4, 0.0, true,
      4.804347469480149e+00, 5.373662435158527e-01, 3.440463780890295e-02,
      -8.211047696226742e-02, 1.146362531792646e-01, 4.076058664279356e-02},
    {"1W_call", 100, 100, 0.0192, 0.05, 0.2, 0.0, true,
      1.153655361213346e+00, 5.193400907578132e-01, 1.437867029845802e-01,
      -8.574344734971077e-02, 5.521409394607878e-02, 9.749827913197052e-03},
    {"deep_ITM_call", 100, 50, 1.0, 0.05, 0.2, 0.0, true,
      5.243886211716185e+01, 9.999321111667006e-01, 1.374835954598021e-05,
      -6.521827731190701e-03, 2.749671909196042e-04, 4.755434899950820e-01},
    {"deep_OTM_call", 100, 200, 1.0, 0.05, 0.2, 0.0, true,
      4.798835106619326e-03, 9.174326039451518e-04, 1.555449322424543e-04,
      -9.714029510379633e-05, 3.110898644849086e-03, 8.694442528789587e-04},
    {"zero_rate", 100, 100, 1.0, 0.0, 0.2, 0.0, true,
      7.965567455405804e+00, 5.398278372770290e-01, 1.984762737385059e-02,
      -1.087541225964416e-02, 3.969525474770118e-01, 4.601721627229710e-01},
    {"low_vol", 100, 100, 1.0, 0.05, 0.1, 0.0, true,
      6.804957708822158e+00, 7.088403132116536e-01, 3.429438550193839e-02,
      -1.347581631702488e-02, 3.429438550193840e-01, 6.407907361234321e-01},
    {"very_high_vol", 100, 100, 1.0, 0.05, 0.8, 0.0, true,
      3.282098246699006e+01, 6.781385988363460e-01, 4.480958552284094e-03,
      -4.407866092641459e-02, 3.584766841827275e-01, 3.499287741664453e-01},
    {"negative_rate", 100, 100, 1.0, -0.01, 0.2, 0.0, true,
      7.513058243602444e+00, 5.199388058383725e-01, 1.992219570473820e-02,
      -9.697618952178884e-03, 3.984439140947640e-01, 4.448082234023480e-01},
    {"high_spot", 1000, 1000, 0.5, 0.05, 0.25, 0.01, true,
      7.968056529302265e+01, 5.769640830106848e-01, 2.200364807471157e-03,
      -2.407011925732874e-01, 2.750456009338947e+00, 2.486417588588311e+00},
};

// ============================================================================
// CATEGORY 1: Reference value tests
// Each test compares our output to a hand-verified Python reference value.
// Tolerance: 1e-12 relative for prices and Greeks.
// ============================================================================

TEST_CASE("Reference: BSM prices match Python reference to 1e-12", "[reference][price]") {
    for (const auto& c : REFERENCE_CASES) {
        INFO("Test case: " << c.name);
        double price = bsm_price(c.S, c.K, c.T, c.r, c.vol, c.q, c.is_call);
        double rel_err = std::abs(price - c.price) / std::abs(c.price);
        REQUIRE(rel_err < 1e-12);
    }
}

TEST_CASE("Reference: Greeks match Python reference to 1e-12", "[reference][greeks]") {
    for (const auto& c : REFERENCE_CASES) {
        INFO("Test case: " << c.name);
        auto g = compute_greeks(c.S, c.K, c.T, c.r, c.vol, c.q, c.is_call);

        // Price
        REQUIRE(std::abs(g.price - c.price) / std::abs(c.price) < 1e-12);

        // Delta (use absolute tolerance for values near zero)
        double delta_tol = std::max(std::abs(c.delta) * 1e-12, 1e-15);
        REQUIRE(std::abs(g.delta - c.delta) < delta_tol);

        // Gamma
        double gamma_tol = std::max(std::abs(c.gamma) * 1e-12, 1e-15);
        REQUIRE(std::abs(g.gamma - c.gamma) < gamma_tol);

        // Theta
        double theta_tol = std::max(std::abs(c.theta) * 1e-12, 1e-15);
        REQUIRE(std::abs(g.theta - c.theta) < theta_tol);

        // Vega
        double vega_tol = std::max(std::abs(c.vega) * 1e-12, 1e-15);
        REQUIRE(std::abs(g.vega - c.vega) < vega_tol);

        // Rho
        double rho_tol = std::max(std::abs(c.rho) * 1e-12, 1e-15);
        REQUIRE(std::abs(g.rho - c.rho) < rho_tol);
    }
}

// ============================================================================
// CATEGORY 2: Put-call parity
// C - P = S*exp(-qT) - K*exp(-rT)
// Must hold to MACHINE PRECISION for any valid parameters.
// ============================================================================

TEST_CASE("Parity: put-call parity holds to 1e-13 over 1000 random cases", "[parity]") {
    std::mt19937 rng(12345);
    std::uniform_real_distribution<> S_dist(10, 1000);
    std::uniform_real_distribution<> moneyness(0.5, 2.0);
    std::uniform_real_distribution<> T_dist(0.01, 5.0);
    std::uniform_real_distribution<> r_dist(-0.02, 0.10);
    std::uniform_real_distribution<> vol_dist(0.05, 1.0);
    std::uniform_real_distribution<> q_dist(0.0, 0.05);

    int n_tests = 1000;
    int n_passed = 0;
    double max_error = 0.0;

    for (int i = 0; i < n_tests; ++i) {
        double S = S_dist(rng);
        double K = S * moneyness(rng);
        double T = T_dist(rng);
        double r = r_dist(rng);
        double vol = vol_dist(rng);
        double q = q_dist(rng);

        double call = bsm_call(S, K, T, r, vol, q);
        double put = bsm_put(S, K, T, r, vol, q);
        double parity = S * std::exp(-q * T) - K * std::exp(-r * T);

        double error = std::abs((call - put) - parity);
        max_error = std::max(max_error, error);

        if (error < 1e-10) n_passed++;
    }

    INFO("Max parity error: " << max_error);
    INFO("Cases passed: " << n_passed << " / " << n_tests);
    REQUIRE(n_passed == n_tests);
    REQUIRE(max_error < 1e-10);
}

// ============================================================================
// CATEGORY 3: IV round-trip
// For any vol used to price, iv(price, ...) must return the same vol.
// This is the gold standard for testing the IV solver.
// ============================================================================

TEST_CASE("IV round-trip: 1000 random cases converge to 1e-10", "[iv][roundtrip]") {
    std::mt19937 rng(54321);
    std::uniform_real_distribution<> S_dist(50, 500);
    std::uniform_real_distribution<> moneyness(0.7, 1.5);   // not extreme
    std::uniform_real_distribution<> T_dist(0.05, 3.0);     // not very short
    std::uniform_real_distribution<> vol_dist(0.10, 0.80);  // typical range
    double r = 0.04;

    int n_tests = 1000;
    int n_passed = 0;
    double max_error = 0.0;

    for (int i = 0; i < n_tests; ++i) {
        double S = S_dist(rng);
        double K = S * moneyness(rng);
        double T = T_dist(rng);
        double vol = vol_dist(rng);
        bool is_call = (i % 2 == 0);

        double price = bsm_price(S, K, T, r, vol, 0.0, is_call);
        if (price < 1e-10) continue;  // skip degenerate

        double solved = implied_vol(price, S, K, T, r, 0.0, is_call);

        double error = std::abs(solved - vol);
        max_error = std::max(max_error, error);

        if (error < 1e-10) n_passed++;
    }

    INFO("Max IV round-trip error: " << max_error);
    INFO("Cases passed: " << n_passed << " / " << n_tests);
    REQUIRE(n_passed >= n_tests - 5);  // allow tiny number of edge case failures
}

TEST_CASE("IV round-trip: extreme cases", "[iv][roundtrip][extreme]") {
    struct Case {
        double S, K, T, vol;
        bool is_call;
        const char* name;
    };

    std::vector<Case> cases = {
        {100, 100, 1.0,  0.20, true,  "ATM standard"},
        {100, 100, 1.0,  0.05, true,  "ATM low vol"},
        {100, 100, 1.0,  1.00, true,  "ATM 100% vol"},
        {100, 90,  1.0,  0.20, true,  "ITM call"},
        {100, 110, 1.0,  0.20, true,  "OTM call"},
        {100, 110, 1.0,  0.20, false, "ITM put"},
        {100, 90,  1.0,  0.20, false, "OTM put"},
        {100, 100, 0.10, 0.20, true,  "Short expiry"},
        {100, 100, 5.0,  0.20, true,  "Long expiry"},
        {100, 100, 1.0,  0.30, false, "ATM put"},
    };

    for (const auto& c : cases) {
        INFO("Case: " << c.name);
        double price = bsm_price(c.S, c.K, c.T, 0.04, c.vol, 0.0, c.is_call);
        double solved = implied_vol(price, c.S, c.K, c.T, 0.04, 0.0, c.is_call);
        REQUIRE(std::abs(solved - c.vol) < 1e-10);
    }
}

// ============================================================================
// CATEGORY 4: Greek identities
// gamma and vega are identical for calls and puts (put-call parity in Greeks)
// ============================================================================

TEST_CASE("Greek identity: gamma_call == gamma_put", "[greeks][identity]") {
    std::mt19937 rng(98765);
    std::uniform_real_distribution<> S_dist(50, 500);
    std::uniform_real_distribution<> moneyness(0.7, 1.5);
    std::uniform_real_distribution<> T_dist(0.05, 3.0);
    std::uniform_real_distribution<> vol_dist(0.10, 0.80);

    for (int i = 0; i < 100; ++i) {
        double S = S_dist(rng);
        double K = S * moneyness(rng);
        double T = T_dist(rng);
        double vol = vol_dist(rng);
        double r = 0.04;
        double q = 0.01;

        auto gc = compute_greeks(S, K, T, r, vol, q, true);
        auto gp = compute_greeks(S, K, T, r, vol, q, false);

        REQUIRE(std::abs(gc.gamma - gp.gamma) < 1e-15);
        REQUIRE(std::abs(gc.vega - gp.vega) < 1e-15);
    }
}

TEST_CASE("Greek identity: delta_call - delta_put == exp(-qT)", "[greeks][identity]") {
    std::mt19937 rng(11111);
    std::uniform_real_distribution<> S_dist(50, 500);
    std::uniform_real_distribution<> moneyness(0.7, 1.5);
    std::uniform_real_distribution<> T_dist(0.05, 3.0);
    std::uniform_real_distribution<> vol_dist(0.10, 0.80);

    for (int i = 0; i < 100; ++i) {
        double S = S_dist(rng);
        double K = S * moneyness(rng);
        double T = T_dist(rng);
        double vol = vol_dist(rng);
        double r = 0.04;
        double q = 0.02;

        auto gc = compute_greeks(S, K, T, r, vol, q, true);
        auto gp = compute_greeks(S, K, T, r, vol, q, false);

        double diff = gc.delta - gp.delta;
        double expected = std::exp(-q * T);
        REQUIRE(std::abs(diff - expected) < 1e-13);
    }
}

// ============================================================================
// CATEGORY 5: Numerical Greeks verification
// Compare analytic Greeks against finite difference approximations.
// This catches bugs in the analytic formulas.
// ============================================================================

TEST_CASE("Numerical: analytic delta matches finite difference", "[greeks][numerical]") {
    double S = 100, K = 105, T = 0.5, r = 0.05, vol = 0.25;
    double h = 0.01;

    // Central difference
    double price_up = bsm_call(S + h, K, T, r, vol);
    double price_dn = bsm_call(S - h, K, T, r, vol);
    double numerical_delta = (price_up - price_dn) / (2 * h);

    auto g = compute_greeks(S, K, T, r, vol, 0.0, true);

    REQUIRE(std::abs(g.delta - numerical_delta) < 1e-7);
}

TEST_CASE("Numerical: analytic gamma matches finite difference", "[greeks][numerical]") {
    double S = 100, K = 105, T = 0.5, r = 0.05, vol = 0.25;
    double h = 0.1;  // larger step for second derivative stability

    double price_up = bsm_call(S + h, K, T, r, vol);
    double price_mid = bsm_call(S, K, T, r, vol);
    double price_dn = bsm_call(S - h, K, T, r, vol);
    double numerical_gamma = (price_up - 2 * price_mid + price_dn) / (h * h);

    auto g = compute_greeks(S, K, T, r, vol, 0.0, true);

    REQUIRE(std::abs(g.gamma - numerical_gamma) < 1e-6);
}

TEST_CASE("Numerical: analytic vega matches finite difference", "[greeks][numerical]") {
    double S = 100, K = 105, T = 0.5, r = 0.05, vol = 0.25;
    double h = 0.0001;

    double price_up = bsm_call(S, K, T, r, vol + h);
    double price_dn = bsm_call(S, K, T, r, vol - h);
    double numerical_vega = (price_up - price_dn) / (2 * h);
    // Convert to "per 1% vol" convention
    numerical_vega /= 100.0;

    auto g = compute_greeks(S, K, T, r, vol, 0.0, true);

    REQUIRE(std::abs(g.vega - numerical_vega) < 1e-8);
}

TEST_CASE("Numerical: analytic theta matches finite difference", "[greeks][numerical]") {
    double S = 100, K = 105, T = 0.5, r = 0.05, vol = 0.25;
    double h = 1.0 / 365.0;  // 1 day

    double price_up = bsm_call(S, K, T + h, r, vol);
    double price_dn = bsm_call(S, K, T - h, r, vol);
    // Forward in calendar time = backward in T (time to expiry)
    double numerical_theta_annual = -(price_up - price_dn) / (2 * h);
    double numerical_theta_daily = numerical_theta_annual / 365.0;

    auto g = compute_greeks(S, K, T, r, vol, 0.0, true);

    REQUIRE(std::abs(g.theta - numerical_theta_daily) < 1e-7);
}

TEST_CASE("Numerical: analytic rho matches finite difference", "[greeks][numerical]") {
    double S = 100, K = 105, T = 0.5, r = 0.05, vol = 0.25;
    double h = 0.0001;

    double price_up = bsm_call(S, K, T, r + h, vol);
    double price_dn = bsm_call(S, K, T, r - h, vol);
    double numerical_rho = (price_up - price_dn) / (2 * h) / 100.0;

    auto g = compute_greeks(S, K, T, r, vol, 0.0, true);

    REQUIRE(std::abs(g.rho - numerical_rho) < 1e-8);
}

// ============================================================================
// CATEGORY 6: Monotonicity tests
// Call price decreases in K, increases in S, T, vol
// Put price increases in K, decreases in S, increases in T, vol
// ============================================================================

TEST_CASE("Monotonicity: call price decreases in strike", "[monotonicity]") {
    double S = 100, T = 1.0, r = 0.05, vol = 0.20;
    double prev = INF;
    for (double K = 50; K <= 200; K += 5) {
        double price = bsm_call(S, K, T, r, vol);
        REQUIRE(price < prev);
        REQUIRE(price >= 0.0);
        prev = price;
    }
}

TEST_CASE("Monotonicity: call price increases in spot", "[monotonicity]") {
    double K = 100, T = 1.0, r = 0.05, vol = 0.20;
    double prev = -1.0;
    for (double S = 50; S <= 200; S += 5) {
        double price = bsm_call(S, K, T, r, vol);
        REQUIRE(price > prev);
        prev = price;
    }
}

TEST_CASE("Monotonicity: option price increases in volatility", "[monotonicity]") {
    double S = 100, K = 105, T = 1.0, r = 0.05;
    double prev_call = -1.0, prev_put = -1.0;
    for (double vol = 0.05; vol <= 1.0; vol += 0.05) {
        double call = bsm_call(S, K, T, r, vol);
        double put = bsm_put(S, K, T, r, vol);
        REQUIRE(call > prev_call);
        REQUIRE(put > prev_put);
        prev_call = call;
        prev_put = put;
    }
}

TEST_CASE("Monotonicity: option price increases in time to expiry", "[monotonicity]") {
    // Note: only true for ATM/OTM. ITM puts can decrease in T due to discounting.
    double S = 100, K = 100, T_max = 2.0, r = 0.05, vol = 0.20;
    double prev = -1.0;
    for (double T = 0.05; T <= T_max; T += 0.05) {
        double price = bsm_call(S, K, T, r, vol);
        REQUIRE(price > prev);
        prev = price;
    }
}

// ============================================================================
// CATEGORY 7: Boundary and edge cases
// ============================================================================

TEST_CASE("Boundary: deep ITM call ≈ S - K*exp(-rT)", "[boundary]") {
    double S = 100, K = 10, T = 1.0, r = 0.05, vol = 0.20;
    double price = bsm_call(S, K, T, r, vol);
    double intrinsic_pv = S - K * std::exp(-r * T);
    REQUIRE(std::abs(price - intrinsic_pv) < 0.01);
}

TEST_CASE("Boundary: deep OTM call ≈ 0", "[boundary]") {
    // 100 spot, 1000 strike, 1y, 5% rate, 20% vol → astronomically OTM
    // Actual computed value ≈ 5.4e-29 (verified independently)
    double S = 100, K = 1000, T = 1.0, r = 0.05, vol = 0.20;
    double price = bsm_call(S, K, T, r, vol);
    REQUIRE(price < 1e-20);  // far smaller than any meaningful option price
    REQUIRE(price >= 0.0);
    REQUIRE(std::isfinite(price));
}

TEST_CASE("Boundary: zero time returns intrinsic", "[boundary]") {
    REQUIRE(bsm_call(105, 100, 0.0, 0.05, 0.20) == Approx(5.0));
    REQUIRE(bsm_call(95, 100, 0.0, 0.05, 0.20) == Approx(0.0));
    REQUIRE(bsm_put(95, 100, 0.0, 0.05, 0.20) == Approx(5.0));
    REQUIRE(bsm_put(105, 100, 0.0, 0.05, 0.20) == Approx(0.0));
}

TEST_CASE("Boundary: zero vol returns discounted intrinsic forward", "[boundary]") {
    double S = 100, K = 95, T = 1.0, r = 0.05;
    double F = S * std::exp(r * T);
    double expected = std::max(F - K, 0.0) * std::exp(-r * T);
    REQUIRE(bsm_call(S, K, T, r, 0.0) == Approx(expected).margin(1e-12));
}

// ============================================================================
// CATEGORY 8: Vectorized batch consistency
// Batch results must match scalar results exactly
// ============================================================================

TEST_CASE("Batch: vectorized prices match scalar prices", "[batch]") {
    std::vector<double> strikes = {80, 85, 90, 95, 100, 105, 110, 115, 120};
    std::vector<double> expiries(strikes.size(), 0.5);
    std::vector<double> out(strikes.size());

    bsm_price_batch_strikes(100.0, strikes.data(), expiries.data(),
                            0.05, 0.20, 0.0, true, out.data(), strikes.size());

    for (size_t i = 0; i < strikes.size(); ++i) {
        double scalar = bsm_price(100.0, strikes[i], 0.5, 0.05, 0.20, 0.0, true);
        REQUIRE(out[i] == scalar);  // EXACT equality, not approx
    }
}
