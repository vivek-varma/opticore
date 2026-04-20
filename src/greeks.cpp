#include "opticore/greeks.hpp"
#include "opticore/bsm.hpp"
#include <cmath>

namespace opticore {

// ============================================================================
// All-in-one Greeks computation
// ============================================================================

GreeksResult compute_greeks(
    double spot, double strike, double expiry,
    double rate, double vol, double div_yield,
    bool is_call
) noexcept {
    GreeksResult g{};

    // Handle degenerate inputs
    if (spot <= 0.0 || strike <= 0.0 || vol < 0.0) {
        g = {NaN, NaN, NaN, NaN, NaN, NaN};
        return g;
    }

    if (expiry <= 0.0) {
        // At expiry: intrinsic value, delta is 0 or 1
        if (is_call) {
            g.price = std::max(spot - strike, 0.0);
            g.delta = (spot > strike) ? 1.0 : 0.0;
        } else {
            g.price = std::max(strike - spot, 0.0);
            g.delta = (spot < strike) ? -1.0 : 0.0;
        }
        g.gamma = 0.0;
        g.theta = 0.0;
        g.vega  = 0.0;
        g.rho   = 0.0;
        return g;
    }

    // ── Shared intermediate values ──────────────────────────────────────
    double sqrt_t       = std::sqrt(expiry);
    double vol_sqrt_t   = vol * sqrt_t;
    double discount     = std::exp(-rate * expiry);
    double div_discount = std::exp(-div_yield * expiry);
    double log_SK       = std::log(spot / strike);
    double drift        = (rate - div_yield + 0.5 * vol * vol) * expiry;

    double d1 = (log_SK + drift) / vol_sqrt_t;
    double d2 = d1 - vol_sqrt_t;

    double nd1  = norm_cdf(d1);
    double nd2  = norm_cdf(d2);
    double nmd1 = norm_cdf(-d1);
    double nmd2 = norm_cdf(-d2);
    double pd1  = norm_pdf(d1);   // n(d1), shared for gamma/vega/theta

    // ── Price ───────────────────────────────────────────────────────────
    if (is_call) {
        g.price = spot * div_discount * nd1 - strike * discount * nd2;
    } else {
        g.price = strike * discount * nmd2 - spot * div_discount * nmd1;
    }

    // ── Delta ───────────────────────────────────────────────────────────
    // Call delta = exp(-q*T) * N(d1)
    // Put  delta = exp(-q*T) * (N(d1) - 1) = -exp(-q*T) * N(-d1)
    if (is_call) {
        g.delta = div_discount * nd1;
    } else {
        g.delta = -div_discount * nmd1;
    }

    // ── Gamma ───────────────────────────────────────────────────────────
    // Gamma = exp(-q*T) * n(d1) / (S * sigma * sqrt(T))
    // Same for call and put
    g.gamma = div_discount * pd1 / (spot * vol_sqrt_t);

    // ── Theta ───────────────────────────────────────────────────────────
    // Theta (annualized) then divided by 365 for per-day
    double theta_common = -(spot * div_discount * pd1 * vol) / (2.0 * sqrt_t);

    if (is_call) {
        double theta_annual = theta_common
            + div_yield * spot * div_discount * nd1
            - rate * strike * discount * nd2;
        g.theta = theta_annual / 365.0;  // per calendar day
    } else {
        double theta_annual = theta_common
            - div_yield * spot * div_discount * nmd1
            + rate * strike * discount * nmd2;
        g.theta = theta_annual / 365.0;  // per calendar day
    }

    // ── Vega ────────────────────────────────────────────────────────────
    // Vega = S * exp(-q*T) * n(d1) * sqrt(T)
    // Divide by 100 for "per 1% vol move" convention
    double vega_annual = spot * div_discount * pd1 * sqrt_t;
    g.vega = vega_annual / 100.0;  // per 1% vol move

    // ── Rho ─────────────────────────────────────────────────────────────
    // Call rho = K * T * exp(-r*T) * N(d2)
    // Put  rho = -K * T * exp(-r*T) * N(-d2)
    // Divide by 100 for "per 1% rate move" convention
    if (is_call) {
        g.rho = strike * expiry * discount * nd2 / 100.0;
    } else {
        g.rho = -strike * expiry * discount * nmd2 / 100.0;
    }

    return g;
}

// ============================================================================
// Batch computation
// ============================================================================

void compute_greeks_batch(
    const double* spot, const double* strike, const double* expiry,
    double rate,
    const double* vol,
    double div_yield,
    const bool* is_call,
    double* out_price,
    double* out_delta,
    double* out_gamma,
    double* out_theta,
    double* out_vega,
    double* out_rho,
    size_t n
) noexcept {
    for (size_t i = 0; i < n; ++i) {
        auto g = compute_greeks(spot[i], strike[i], expiry[i],
                                rate, vol[i], div_yield, is_call[i]);
        out_price[i] = g.price;
        out_delta[i] = g.delta;
        out_gamma[i] = g.gamma;
        out_theta[i] = g.theta;
        out_vega[i]  = g.vega;
        out_rho[i]   = g.rho;
    }
}

// ============================================================================
// Individual Greeks (convenience wrappers)
// ============================================================================

double bsm_delta(double spot, double strike, double expiry,
    double rate, double vol, double div_yield, bool is_call) noexcept {
    return compute_greeks(spot, strike, expiry, rate, vol, div_yield, is_call).delta;
}

double bsm_gamma(double spot, double strike, double expiry,
    double rate, double vol, double div_yield) noexcept {
    return compute_greeks(spot, strike, expiry, rate, vol, div_yield, true).gamma;
}

double bsm_theta(double spot, double strike, double expiry,
    double rate, double vol, double div_yield, bool is_call) noexcept {
    return compute_greeks(spot, strike, expiry, rate, vol, div_yield, is_call).theta;
}

double bsm_vega(double spot, double strike, double expiry,
    double rate, double vol, double div_yield) noexcept {
    return compute_greeks(spot, strike, expiry, rate, vol, div_yield, true).vega;
}

double bsm_rho(double spot, double strike, double expiry,
    double rate, double vol, double div_yield, bool is_call) noexcept {
    return compute_greeks(spot, strike, expiry, rate, vol, div_yield, is_call).rho;
}

} // namespace opticore
