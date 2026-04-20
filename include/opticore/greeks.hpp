#pragma once

#include "opticore/math.hpp"

namespace opticore {

// ============================================================================
// Analytic Greeks for BSM
//
// All Greeks are computed from shared d1/d2 values for efficiency.
// A single call computes price + all 5 first-order Greeks.
// ============================================================================

/// Container for all BSM Greeks computed in a single pass.
struct GreeksResult {
    double price;
    double delta;
    double gamma;
    double theta;   // per calendar day (divide annual by 365)
    double vega;    // per 1% vol move (multiply by 0.01)
    double rho;     // per 1% rate move (multiply by 0.01)
};

/// Compute price + all first-order Greeks in a single pass.
///
/// This is more efficient than calling each Greek individually because
/// d1, d2, N(d1), N(d2), n(d1) are computed once and shared.
///
/// @param spot       Current underlying price
/// @param strike     Strike price
/// @param expiry     Time to expiration in years
/// @param rate       Risk-free rate (continuous)
/// @param vol        Annualized volatility
/// @param div_yield  Continuous dividend yield
/// @param is_call    true for call, false for put
/// @return           GreeksResult with all values populated
[[nodiscard]] GreeksResult compute_greeks(
    double spot, double strike, double expiry,
    double rate, double vol, double div_yield,
    bool is_call
) noexcept;

/// Batch Greeks: compute for n options. All arrays must have length n.
void compute_greeks_batch(
    const double* spot, const double* strike, const double* expiry,
    double rate,
    const double* vol,
    double div_yield,
    const bool* is_call,
    // Output arrays (all length n):
    double* out_price,
    double* out_delta,
    double* out_gamma,
    double* out_theta,
    double* out_vega,
    double* out_rho,
    size_t n
) noexcept;

// ── Individual Greeks (convenience, less efficient) ─────────────────────

[[nodiscard]] double bsm_delta(double spot, double strike, double expiry,
    double rate, double vol, double div_yield, bool is_call) noexcept;

[[nodiscard]] double bsm_gamma(double spot, double strike, double expiry,
    double rate, double vol, double div_yield) noexcept;

[[nodiscard]] double bsm_theta(double spot, double strike, double expiry,
    double rate, double vol, double div_yield, bool is_call) noexcept;

[[nodiscard]] double bsm_vega(double spot, double strike, double expiry,
    double rate, double vol, double div_yield) noexcept;

[[nodiscard]] double bsm_rho(double spot, double strike, double expiry,
    double rate, double vol, double div_yield, bool is_call) noexcept;

} // namespace opticore
