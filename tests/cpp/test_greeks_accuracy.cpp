#include <catch2/catch_test_macros.hpp>
#include <catch2/catch_approx.hpp>
#include <cmath>

#include "opticore/bsm.hpp"
#include "opticore/greeks.hpp"
#include "reference_values.hpp"

using Catch::Approx;
using namespace opticore;
using namespace opticore::test;

// ============================================================================
// Reference value tests for Greeks
// Tolerance 1e-9 — very tight since these are analytic formulas
// ============================================================================

TEST_CASE("Delta matches reference values (call)", "[accuracy][greeks]") {
    for (size_t i = 0; i < N_REF_CASES; ++i) {
        const auto& c = REF_CASES[i];
        auto g = compute_greeks(c.S, c.K, c.T, c.r, c.sigma, c.q, true);

        INFO("Case: " << c.desc);
        INFO("Expected: " << c.call_delta << "  Computed: " << g.delta);
        REQUIRE(g.delta == Approx(c.call_delta).epsilon(1e-9));
    }
}

TEST_CASE("Delta matches reference values (put)", "[accuracy][greeks]") {
    for (size_t i = 0; i < N_REF_CASES; ++i) {
        const auto& c = REF_CASES[i];
        auto g = compute_greeks(c.S, c.K, c.T, c.r, c.sigma, c.q, false);

        INFO("Case: " << c.desc);
        REQUIRE(g.delta == Approx(c.put_delta).epsilon(1e-9));
    }
}

TEST_CASE("Gamma matches reference values", "[accuracy][greeks]") {
    for (size_t i = 0; i < N_REF_CASES; ++i) {
        const auto& c = REF_CASES[i];
        auto gc = compute_greeks(c.S, c.K, c.T, c.r, c.sigma, c.q, true);
        auto gp = compute_greeks(c.S, c.K, c.T, c.r, c.sigma, c.q, false);

        INFO("Case: " << c.desc);
        // Gamma same for call and put
        REQUIRE(gc.gamma == Approx(c.gamma).epsilon(1e-9));
        REQUIRE(gp.gamma == Approx(c.gamma).epsilon(1e-9));
    }
}

TEST_CASE("Vega matches reference values", "[accuracy][greeks]") {
    for (size_t i = 0; i < N_REF_CASES; ++i) {
        const auto& c = REF_CASES[i];
        auto gc = compute_greeks(c.S, c.K, c.T, c.r, c.sigma, c.q, true);
        auto gp = compute_greeks(c.S, c.K, c.T, c.r, c.sigma, c.q, false);

        INFO("Case: " << c.desc);
        // Vega same for call and put
        REQUIRE(gc.vega == Approx(c.vega).epsilon(1e-9));
        REQUIRE(gp.vega == Approx(c.vega).epsilon(1e-9));
    }
}

TEST_CASE("Theta matches reference values (call)", "[accuracy][greeks]") {
    for (size_t i = 0; i < N_REF_CASES; ++i) {
        const auto& c = REF_CASES[i];
        auto g = compute_greeks(c.S, c.K, c.T, c.r, c.sigma, c.q, true);

        INFO("Case: " << c.desc);
        INFO("Expected: " << c.call_theta << "  Computed: " << g.theta);
        REQUIRE(g.theta == Approx(c.call_theta).epsilon(1e-9));
    }
}

TEST_CASE("Theta matches reference values (put)", "[accuracy][greeks]") {
    for (size_t i = 0; i < N_REF_CASES; ++i) {
        const auto& c = REF_CASES[i];
        auto g = compute_greeks(c.S, c.K, c.T, c.r, c.sigma, c.q, false);

        INFO("Case: " << c.desc);
        REQUIRE(g.theta == Approx(c.put_theta).epsilon(1e-9));
    }
}

TEST_CASE("Rho matches reference values (call)", "[accuracy][greeks]") {
    for (size_t i = 0; i < N_REF_CASES; ++i) {
        const auto& c = REF_CASES[i];
        auto g = compute_greeks(c.S, c.K, c.T, c.r, c.sigma, c.q, true);

        INFO("Case: " << c.desc);
        REQUIRE(g.rho == Approx(c.call_rho).epsilon(1e-9));
    }
}

TEST_CASE("Rho matches reference values (put)", "[accuracy][greeks]") {
    for (size_t i = 0; i < N_REF_CASES; ++i) {
        const auto& c = REF_CASES[i];
        auto g = compute_greeks(c.S, c.K, c.T, c.r, c.sigma, c.q, false);

        INFO("Case: " << c.desc);
        REQUIRE(g.rho == Approx(c.put_rho).epsilon(1e-9));
    }
}

// ============================================================================
// Finite-difference verification of Greeks
//
// Compute Greeks numerically via central differences and compare to the
// analytic values. This catches algebra errors that might produce wrong
// but self-consistent formulas.
// ============================================================================

TEST_CASE("Delta = dP/dS (finite difference)", "[accuracy][greeks][fd]") {
    double S = 100, K = 105, T = 0.5, r = 0.05, sigma = 0.25, q = 0.02;
    double h = S * 1e-5;  // small bump

    for (bool is_call : {true, false}) {
        double up = bsm_price(S + h, K, T, r, sigma, q, is_call);
        double dn = bsm_price(S - h, K, T, r, sigma, q, is_call);
        double fd_delta = (up - dn) / (2 * h);

        auto g = compute_greeks(S, K, T, r, sigma, q, is_call);

        INFO(std::string(is_call ? "Call" : "Put"));
        INFO("Analytic: " << g.delta << "  FD: " << fd_delta);
        REQUIRE(g.delta == Approx(fd_delta).epsilon(1e-6));
    }
}

TEST_CASE("Gamma = d^2P/dS^2 (finite difference)", "[accuracy][greeks][fd]") {
    double S = 100, K = 105, T = 0.5, r = 0.05, sigma = 0.25, q = 0.02;
    double h = S * 1e-4;  // slightly larger for second derivative

    double up = bsm_price(S + h, K, T, r, sigma, q, true);
    double mid = bsm_price(S, K, T, r, sigma, q, true);
    double dn = bsm_price(S - h, K, T, r, sigma, q, true);

    double fd_gamma = (up - 2 * mid + dn) / (h * h);

    auto g = compute_greeks(S, K, T, r, sigma, q, true);

    INFO("Analytic: " << g.gamma << "  FD: " << fd_gamma);
    REQUIRE(g.gamma == Approx(fd_gamma).epsilon(1e-4));
}

TEST_CASE("Vega = dP/dsigma (finite difference)", "[accuracy][greeks][fd]") {
    double S = 100, K = 105, T = 0.5, r = 0.05, sigma = 0.25, q = 0.02;
    double h = 1e-6;

    for (bool is_call : {true, false}) {
        double up = bsm_price(S, K, T, r, sigma + h, q, is_call);
        double dn = bsm_price(S, K, T, r, sigma - h, q, is_call);
        double fd_vega = (up - dn) / (2 * h);
        // Convert to "per 1% vol move" convention
        fd_vega /= 100.0;

        auto g = compute_greeks(S, K, T, r, sigma, q, is_call);

        INFO(std::string(is_call ? "Call" : "Put"));
        INFO("Analytic: " << g.vega << "  FD: " << fd_vega);
        REQUIRE(g.vega == Approx(fd_vega).epsilon(1e-6));
    }
}

TEST_CASE("Theta = -dP/dT (finite difference)", "[accuracy][greeks][fd]") {
    double S = 100, K = 105, T = 0.5, r = 0.05, sigma = 0.25, q = 0.02;
    double h = 1e-6;

    for (bool is_call : {true, false}) {
        double up = bsm_price(S, K, T + h, r, sigma, q, is_call);
        double dn = bsm_price(S, K, T - h, r, sigma, q, is_call);
        // theta = -dP/dT (option loses value as time passes)
        // Our convention: per calendar day
        double fd_theta = -(up - dn) / (2 * h) / 365.0;

        auto g = compute_greeks(S, K, T, r, sigma, q, is_call);

        INFO(std::string(is_call ? "Call" : "Put"));
        INFO("Analytic: " << g.theta << "  FD: " << fd_theta);
        REQUIRE(g.theta == Approx(fd_theta).epsilon(1e-5));
    }
}

TEST_CASE("Rho = dP/dr (finite difference)", "[accuracy][greeks][fd]") {
    double S = 100, K = 105, T = 0.5, r = 0.05, sigma = 0.25, q = 0.02;
    double h = 1e-7;

    for (bool is_call : {true, false}) {
        double up = bsm_price(S, K, T, r + h, sigma, q, is_call);
        double dn = bsm_price(S, K, T, r - h, sigma, q, is_call);
        // Convert to "per 1% rate move" convention
        double fd_rho = (up - dn) / (2 * h) / 100.0;

        auto g = compute_greeks(S, K, T, r, sigma, q, is_call);

        INFO(std::string(is_call ? "Call" : "Put"));
        INFO("Analytic: " << g.rho << "  FD: " << fd_rho);
        REQUIRE(g.rho == Approx(fd_rho).epsilon(1e-6));
    }
}

// ============================================================================
// Greek identities
// ============================================================================

TEST_CASE("Call delta - put delta = exp(-qT) (identity)",
          "[accuracy][greeks][identity]") {
    for (size_t i = 0; i < N_REF_CASES; ++i) {
        const auto& c = REF_CASES[i];
        auto gc = compute_greeks(c.S, c.K, c.T, c.r, c.sigma, c.q, true);
        auto gp = compute_greeks(c.S, c.K, c.T, c.r, c.sigma, c.q, false);

        double diff = gc.delta - gp.delta;
        double expected = std::exp(-c.q * c.T);

        INFO("Case: " << c.desc);
        INFO("delta_c - delta_p = " << diff << "  exp(-qT) = " << expected);
        REQUIRE(diff == Approx(expected).epsilon(1e-12));
    }
}

TEST_CASE("Call rho - put rho = K*T*exp(-rT) (identity)",
          "[accuracy][greeks][identity]") {
    for (size_t i = 0; i < N_REF_CASES; ++i) {
        const auto& c = REF_CASES[i];
        auto gc = compute_greeks(c.S, c.K, c.T, c.r, c.sigma, c.q, true);
        auto gp = compute_greeks(c.S, c.K, c.T, c.r, c.sigma, c.q, false);

        // Convert back from /100 convention
        double diff = (gc.rho - gp.rho) * 100.0;
        double expected = c.K * c.T * std::exp(-c.r * c.T);

        INFO("Case: " << c.desc);
        REQUIRE(diff == Approx(expected).epsilon(1e-12));
    }
}

TEST_CASE("Gamma is non-negative at all strikes", "[accuracy][greeks]") {
    double S = 100, T = 1.0, r = 0.05, sigma = 0.20;

    for (double K = 10; K <= 500; K += 10) {
        auto g = compute_greeks(S, K, T, r, sigma, 0.0, true);
        INFO("K=" << K << " gamma=" << g.gamma);
        REQUIRE(g.gamma >= 0.0);
    }
}

TEST_CASE("Vega is non-negative at all strikes", "[accuracy][greeks]") {
    double S = 100, T = 1.0, r = 0.05, sigma = 0.20;

    for (double K = 10; K <= 500; K += 10) {
        auto g = compute_greeks(S, K, T, r, sigma, 0.0, true);
        INFO("K=" << K << " vega=" << g.vega);
        REQUIRE(g.vega >= 0.0);
    }
}

TEST_CASE("Call delta is monotonic in spot", "[accuracy][greeks]") {
    double K = 100, T = 1.0, r = 0.05, sigma = 0.20;

    double prev_delta = -INF;
    for (double S = 50; S <= 150; S += 5) {
        auto g = compute_greeks(S, K, T, r, sigma, 0.0, true);
        INFO("S=" << S << " delta=" << g.delta);
        REQUIRE(g.delta > prev_delta);
        prev_delta = g.delta;
    }
}
