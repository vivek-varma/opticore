#include "opticore/bsm.hpp"
#include <cmath>

namespace opticore {

// ============================================================================
// BSMParams
// ============================================================================

BSMParams BSMParams::compute(
    double spot, double strike, double expiry,
    double rate, double vol, double div_yield
) noexcept {
    BSMParams p{};

    // Handle degenerate cases
    if (spot <= 0.0 || strike <= 0.0 || vol < 0.0) {
        p.d1 = NaN;
        p.d2 = NaN;
        return p;
    }

    // At expiry: return intrinsic value params
    if (expiry <= 0.0 || !std::isfinite(expiry)) {
        p.d1 = (spot > strike) ? INF : -INF;
        p.d2 = p.d1;
        p.discount = 1.0;
        p.div_discount = 1.0;
        p.sqrt_t = 0.0;
        return p;
    }

    // Zero vol: deterministic payoff
    if (vol == 0.0) {
        double forward = spot * std::exp((rate - div_yield) * expiry);
        p.d1 = (forward > strike) ? INF : -INF;
        p.d2 = p.d1;
        p.discount = std::exp(-rate * expiry);
        p.div_discount = std::exp(-div_yield * expiry);
        p.sqrt_t = 0.0;
        return p;
    }

    p.sqrt_t = std::sqrt(expiry);
    p.discount = std::exp(-rate * expiry);
    p.div_discount = std::exp(-div_yield * expiry);

    double vol_sqrt_t = vol * p.sqrt_t;
    double log_moneyness = std::log(spot / strike);
    double drift = (rate - div_yield + 0.5 * vol * vol) * expiry;

    p.d1 = (log_moneyness + drift) / vol_sqrt_t;
    p.d2 = p.d1 - vol_sqrt_t;

    return p;
}

// ============================================================================
// Scalar pricing
// ============================================================================

double bsm_call(
    double spot, double strike, double expiry,
    double rate, double vol, double div_yield
) noexcept {
    auto p = BSMParams::compute(spot, strike, expiry, rate, vol, div_yield);

    if (!is_valid(p.d1)) return NaN;

    // At or past expiry
    if (expiry <= 0.0) {
        return std::max(spot - strike, 0.0);
    }

    double nd1 = norm_cdf(p.d1);
    double nd2 = norm_cdf(p.d2);

    return spot * p.div_discount * nd1 - strike * p.discount * nd2;
}

double bsm_put(
    double spot, double strike, double expiry,
    double rate, double vol, double div_yield
) noexcept {
    auto p = BSMParams::compute(spot, strike, expiry, rate, vol, div_yield);

    if (!is_valid(p.d1)) return NaN;

    // At or past expiry
    if (expiry <= 0.0) {
        return std::max(strike - spot, 0.0);
    }

    double nmd1 = norm_cdf(-p.d1);
    double nmd2 = norm_cdf(-p.d2);

    return strike * p.discount * nmd2 - spot * p.div_discount * nmd1;
}

double bsm_price(
    double spot, double strike, double expiry,
    double rate, double vol, double div_yield,
    bool is_call
) noexcept {
    if (is_call) {
        return bsm_call(spot, strike, expiry, rate, vol, div_yield);
    } else {
        return bsm_put(spot, strike, expiry, rate, vol, div_yield);
    }
}

// ============================================================================
// Batch pricing
// ============================================================================

void bsm_price_batch(
    const double* spot, const double* strike, const double* expiry,
    double rate,
    const double* vol,
    double div_yield,
    const bool* is_call,
    double* out,
    size_t n
) noexcept {
    for (size_t i = 0; i < n; ++i) {
        out[i] = bsm_price(spot[i], strike[i], expiry[i],
                           rate, vol[i], div_yield, is_call[i]);
    }
}

void bsm_price_batch_strikes(
    double spot,
    const double* strike,
    const double* expiry,
    double rate, double vol, double div_yield,
    bool is_call,
    double* out,
    size_t n
) noexcept {
    for (size_t i = 0; i < n; ++i) {
        out[i] = bsm_price(spot, strike[i], expiry[i],
                           rate, vol, div_yield, is_call);
    }
}

} // namespace opticore
