#pragma once

#include "opticore/math.hpp"

namespace opticore {

// ============================================================================
// Implied Volatility Solver
// Based on Peter Jaeckel's "Let's Be Rational" (2013)
//
// Achieves full 64-bit machine precision in at most 2 Householder(4)
// iterations for ALL possible inputs. This is the gold standard.
//
// Reference: http://www.jaeckel.org/LetsBeRational.pdf
// ============================================================================

/// Compute Black-Scholes implied volatility from an option price.
///
/// @param price      Observed market price of the option
/// @param spot       Current underlying price
/// @param strike     Strike price
/// @param expiry     Time to expiration in years
/// @param rate       Risk-free rate (continuous compounding)
/// @param div_yield  Continuous dividend yield
/// @param is_call    true for call, false for put
/// @return           Implied volatility, or NaN if no valid solution
[[nodiscard]] double implied_vol(
    double price, double spot, double strike, double expiry,
    double rate, double div_yield, bool is_call
) noexcept;

/// Batch implied volatility: solve for IV across an array of options.
/// All arrays must have length n. Results written to `out`.
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
) noexcept;

// ============================================================================
// Internal: Normalised Black function and its inverse
// These operate in "normalised" coordinates where forward=1.
// ============================================================================
namespace detail {

/// Normalised Black call price: b(x, s) where x = ln(F/K), s = sigma*sqrt(T)
[[nodiscard]] double normalised_black_call(double x, double s) noexcept;

/// Normalised Black function (call or put via sign of theta)
/// theta = +1 for call, -1 for put
[[nodiscard]] double normalised_black(double x, double s, double theta) noexcept;

/// Normalised vega: the derivative of normalised_black w.r.t. s
[[nodiscard]] double normalised_vega(double x, double s) noexcept;

/// Inverse: find s given normalised Black price beta
/// This is the core of Jaeckel's algorithm.
[[nodiscard]] double normalised_implied_volatility(
    double beta, double x, double theta
) noexcept;

} // namespace detail

} // namespace opticore
