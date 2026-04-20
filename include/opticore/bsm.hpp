#pragma once

#include "opticore/math.hpp"

namespace opticore {

// ============================================================================
// Black-Scholes-Merton European Option Pricing
// ============================================================================

/// Internal: compute d1 and d2 for BSM
struct BSMParams {
    double d1;
    double d2;
    double discount;     // exp(-r * T)
    double div_discount; // exp(-q * T)
    double sqrt_t;       // sqrt(T)

    /// Construct BSM intermediate parameters.
    /// Returns invalid (NaN) params if inputs are degenerate.
    [[nodiscard]] static BSMParams compute(
        double spot, double strike, double expiry,
        double rate, double vol, double div_yield
    ) noexcept;
};

/// Price a European call option using BSM.
///
/// @param spot         Current price of the underlying
/// @param strike       Strike price
/// @param expiry       Time to expiration in years
/// @param rate         Risk-free interest rate (continuous)
/// @param vol          Annualized volatility
/// @param div_yield    Continuous dividend yield (default: 0)
/// @return             Call option price, or NaN on invalid inputs
[[nodiscard]] double bsm_call(
    double spot, double strike, double expiry,
    double rate, double vol, double div_yield = 0.0
) noexcept;

/// Price a European put option using BSM.
[[nodiscard]] double bsm_put(
    double spot, double strike, double expiry,
    double rate, double vol, double div_yield = 0.0
) noexcept;

/// Price a European option (call or put).
///
/// @param is_call  true for call, false for put
[[nodiscard]] double bsm_price(
    double spot, double strike, double expiry,
    double rate, double vol, double div_yield,
    bool is_call
) noexcept;

// ============================================================================
// Vectorized versions (operate on contiguous arrays)
// ============================================================================

/// Batch price: all arrays must be the same length.
/// Results are written into `out` which must be pre-allocated.
void bsm_price_batch(
    const double* spot, const double* strike, const double* expiry,
    double rate,
    const double* vol,
    double div_yield,
    const bool* is_call,
    double* out,
    size_t n
) noexcept;

/// Batch price with scalar spot, rate, vol, div_yield, is_call
/// and array of strikes and expiries.
void bsm_price_batch_strikes(
    double spot,
    const double* strike,
    const double* expiry,
    double rate, double vol, double div_yield,
    bool is_call,
    double* out,
    size_t n
) noexcept;

} // namespace opticore
