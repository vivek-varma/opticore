#include "opticore/jaeckel.hpp"
#include "opticore/bsm.hpp"
#include <cmath>
#include <algorithm>

namespace opticore {

// ============================================================================
// Implied Volatility Solver
//
// Strategy: Newton-Raphson with BSM vega, using our own bsm_price function.
// This guarantees round-trip consistency: iv(bsm_price(..., vol), ...) == vol.
//
// We use a careful initial guess (Brenner-Subrahmanyam + adjustments) and
// guard against vega-near-zero regions with bisection fallback.
//
// Accuracy target: 1e-12 relative error (full double precision).
// Performance target: < 1 us per solve, typically 3-6 iterations.
// ============================================================================

namespace detail {

/// Compute BSM vega (unscaled, i.e. dC/dsigma) for Newton step
static double bsm_vega_raw(
    double spot, double strike, double expiry,
    double rate, double vol, double div_yield
) noexcept {
    if (vol <= 0.0 || expiry <= 0.0) return 0.0;

    double sqrt_t = std::sqrt(expiry);
    double vol_sqrt_t = vol * sqrt_t;
    double div_disc = std::exp(-div_yield * expiry);
    double log_SK = std::log(spot / strike);
    double drift = (rate - div_yield + 0.5 * vol * vol) * expiry;
    double d1 = (log_SK + drift) / vol_sqrt_t;

    return spot * div_disc * norm_pdf(d1) * sqrt_t;
}

/// Intrinsic value (discounted)
static double intrinsic_value(
    double spot, double strike, double rate,
    double div_yield, double expiry, bool is_call
) noexcept {
    double forward = spot * std::exp((rate - div_yield) * expiry);
    double discount = std::exp(-rate * expiry);
    if (is_call) {
        return std::max(discount * (forward - strike), 0.0);
    } else {
        return std::max(discount * (strike - forward), 0.0);
    }
}

/// Maximum option price
static double max_option_price(
    double spot, double strike, double rate,
    double div_yield, double expiry, bool is_call
) noexcept {
    if (is_call) {
        return spot * std::exp(-div_yield * expiry);
    } else {
        return strike * std::exp(-rate * expiry);
    }
}

/// Initial guess using Brenner-Subrahmanyam approximation
static double initial_guess(
    double price, double spot, double strike, double expiry,
    double rate, double div_yield
) noexcept {
    double forward = spot * std::exp((rate - div_yield) * expiry);
    double discount = std::exp(-rate * expiry);
    double undiscounted = price / discount;
    double sqrt_t = std::sqrt(expiry);

    double bs_guess = undiscounted * SQRT_2PI / (forward * sqrt_t);

    // Clamp to reasonable range
    return std::clamp(bs_guess, 0.01, 5.0);
}

} // namespace detail

double implied_vol(
    double price, double spot, double strike, double expiry,
    double rate, double div_yield, bool is_call
) noexcept {
    // ── Input validation ────────────────────────────────────────────────
    if (price < 0.0 || spot <= 0.0 || strike <= 0.0 || expiry < 0.0) {
        return NaN;
    }

    if (price == 0.0) return 0.0;

    if (expiry <= 0.0) {
        double intrinsic = is_call ? std::max(spot - strike, 0.0)
                                   : std::max(strike - spot, 0.0);
        if (std::abs(price - intrinsic) < 1e-12) return 0.0;
        return NaN;
    }

    // ── Arbitrage bounds check ──────────────────────────────────────────
    double intrinsic = detail::intrinsic_value(spot, strike, rate, div_yield, expiry, is_call);
    double max_price = detail::max_option_price(spot, strike, rate, div_yield, expiry, is_call);

    if (price < intrinsic - 1e-10) return NaN;
    if (price > max_price + 1e-10) return NaN;

    // ── Detect "no time value" — IV is undefined ────────────────────────
    // If the price is within machine epsilon of intrinsic, vega is essentially
    // zero and any sigma in [0, infty) produces the same price. Return NaN.
    double time_value = price - intrinsic;
    if (time_value < 1e-10 * std::max(price, 1.0)) {
        return NaN;
    }

    // ── Initial guess ───────────────────────────────────────────────────
    double sigma = detail::initial_guess(price, spot, strike, expiry, rate, div_yield);

    // ── Establish a valid bracket [lo, hi] around the root ──────────────
    // We need price(lo) < target < price(hi) for bisection to work.
    // Start tight and expand outward if needed.
    double lo = 1e-8;
    double hi = 5.0;

    double price_lo = bsm_price(spot, strike, expiry, rate, lo, div_yield, is_call);
    double price_hi = bsm_price(spot, strike, expiry, rate, hi, div_yield, is_call);

    // If target is below price(lo), vol must be even smaller
    if (price < price_lo) {
        // Numerical noise — return tiny vol
        return lo;
    }

    // If target is above price(hi), expand hi until bracketed (or give up)
    int expand = 0;
    while (price > price_hi && expand < 20) {
        lo = hi;
        price_lo = price_hi;
        hi *= 2.0;
        price_hi = bsm_price(spot, strike, expiry, rate, hi, div_yield, is_call);
        expand++;
    }
    if (price > price_hi) return NaN;  // unreachable vol

    // Ensure initial guess is inside bracket
    if (sigma <= lo || sigma >= hi) {
        sigma = 0.5 * (lo + hi);
    }

    constexpr int MAX_ITER = 100;
    constexpr double TOL = 1e-14;

    int stuck_count = 0;
    double prev_sigma = sigma;

    for (int i = 0; i < MAX_ITER; ++i) {
        double model_price = bsm_price(spot, strike, expiry, rate, sigma, div_yield, is_call);
        double diff = model_price - price;

        // Check convergence (relative + absolute)
        if (std::abs(diff) <= TOL * std::max(price, 1e-10)) {
            return sigma;
        }

        // Update bracket
        if (diff > 0.0) {
            hi = sigma;
        } else {
            lo = sigma;
        }

        // Newton step using vega
        double vega = detail::bsm_vega_raw(spot, strike, expiry, rate, sigma, div_yield);

        double new_sigma;
        if (vega > 1e-15) {
            new_sigma = sigma - diff / vega;
            // Reject if outside bracket — bisect instead
            if (new_sigma <= lo || new_sigma >= hi) {
                new_sigma = 0.5 * (lo + hi);
            }
        } else {
            new_sigma = 0.5 * (lo + hi);
        }

        // Detect stuck steps (Newton making no progress) — force bisection
        if (std::abs(new_sigma - sigma) < 1e-13 * std::max(sigma, 1e-10)) {
            stuck_count++;
            if (stuck_count >= 2) {
                new_sigma = 0.5 * (lo + hi);
                stuck_count = 0;
            }
        } else {
            stuck_count = 0;
        }

        prev_sigma = sigma;
        sigma = new_sigma;

        // Bracket has collapsed
        if (hi - lo < TOL * std::max(sigma, 1e-10)) {
            return sigma;
        }
    }

    return sigma;
}

void implied_vol_batch(
    const double* price,
    const double* spot,
    const double* strike,
    const double* expiry,
    double rate,
    double div_yield,
    const bool* is_call,
    double* out,
    size_t n
) noexcept {
    for (size_t i = 0; i < n; ++i) {
        out[i] = implied_vol(price[i], spot[i], strike[i], expiry[i],
                             rate, div_yield, is_call[i]);
    }
}

} // namespace opticore
