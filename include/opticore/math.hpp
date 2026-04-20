#pragma once

#include <cmath>
#include <numbers>
#include <limits>
#include <algorithm>
#include <span>
#include <concepts>

namespace opticore {

// ============================================================================
// Constants
// ============================================================================

inline constexpr double PI          = std::numbers::pi;
inline constexpr double SQRT_2PI    = 2.5066282746310002;   // sqrt(2*pi)
inline constexpr double INV_SQRT2   = std::numbers::sqrt2 / 2.0;
inline constexpr double INV_SQRT2PI = 1.0 / SQRT_2PI;
inline constexpr double NaN         = std::numeric_limits<double>::quiet_NaN();
inline constexpr double INF         = std::numeric_limits<double>::infinity();
inline constexpr double DBL_EPS     = std::numeric_limits<double>::epsilon();

// ============================================================================
// Normal distribution functions (high precision)
// ============================================================================

/// Standard normal PDF: phi(x) = exp(-x^2/2) / sqrt(2*pi)
///
/// Note: not `constexpr` because `std::exp` is not constexpr in standard C++20
/// (GCC/Clang accept it as an extension, MSVC does not — see CI build errors
/// on Windows prior to 2026-04). C++26 is expected to make it constexpr.
[[nodiscard]] inline double norm_pdf(double x) noexcept {
    return INV_SQRT2PI * std::exp(-0.5 * x * x);
}

/// Standard normal CDF using the complementary error function.
/// This is accurate to full double precision for all inputs.
/// N(x) = 0.5 * erfc(-x / sqrt(2))
[[nodiscard]] inline double norm_cdf(double x) noexcept {
    return 0.5 * std::erfc(-x * INV_SQRT2);
}

/// Inverse standard normal CDF (quantile function).
/// Uses rational approximation by Peter Acklam (accurate to ~1.15e-9)
/// with a refinement step via Halley's method for full precision.
[[nodiscard]] inline double norm_inv(double p) noexcept {
    if (p <= 0.0) return -INF;
    if (p >= 1.0) return  INF;
    if (p == 0.5) return  0.0;

    // Rational approximation coefficients (Acklam)
    constexpr double a1 = -3.969683028665376e+01;
    constexpr double a2 =  2.209460984245205e+02;
    constexpr double a3 = -2.759285104469687e+02;
    constexpr double a4 =  1.383577518672690e+02;
    constexpr double a5 = -3.066479806614716e+01;
    constexpr double a6 =  2.506628277459239e+00;

    constexpr double b1 = -5.447609879822406e+01;
    constexpr double b2 =  1.615858368580409e+02;
    constexpr double b3 = -1.556989798598866e+02;
    constexpr double b4 =  6.680131188771972e+01;
    constexpr double b5 = -1.328068155288572e+01;

    constexpr double c1 = -7.784894002430293e-03;
    constexpr double c2 = -3.223964580411365e-01;
    constexpr double c3 = -2.400758277161838e+00;
    constexpr double c4 = -2.549732539343734e+00;
    constexpr double c5 =  4.374664141464968e+00;
    constexpr double c6 =  2.938163982698783e+00;

    constexpr double d1 =  7.784695709041462e-03;
    constexpr double d2 =  3.224671290700398e-01;
    constexpr double d3 =  2.445134137142996e+00;
    constexpr double d4 =  3.754408661907416e+00;

    constexpr double p_low  = 0.02425;
    constexpr double p_high = 1.0 - p_low;

    double x;
    if (p < p_low) {
        double q = std::sqrt(-2.0 * std::log(p));
        x = (((((c1*q+c2)*q+c3)*q+c4)*q+c5)*q+c6) /
            ((((d1*q+d2)*q+d3)*q+d4)*q+1.0);
    } else if (p <= p_high) {
        double q = p - 0.5;
        double r = q * q;
        x = (((((a1*r+a2)*r+a3)*r+a4)*r+a5)*r+a6) * q /
            (((((b1*r+b2)*r+b3)*r+b4)*r+b5)*r+1.0);
    } else {
        double q = std::sqrt(-2.0 * std::log(1.0 - p));
        x = -(((((c1*q+c2)*q+c3)*q+c4)*q+c5)*q+c6) /
             ((((d1*q+d2)*q+d3)*q+d4)*q+1.0);
    }

    // Halley refinement for full precision
    double e = 0.5 * std::erfc(-x * INV_SQRT2) - p;
    double u = e * SQRT_2PI * std::exp(0.5 * x * x);
    x -= u / (1.0 + x * u / 2.0);

    return x;
}

// ============================================================================
// Utility
// ============================================================================

/// Clamp a value; useful for ensuring numerical stability.
template <typename T>
[[nodiscard]] inline constexpr T clamp(T val, T lo, T hi) noexcept {
    return std::max(lo, std::min(val, hi));
}

/// Check if a double is valid (not NaN).
///
/// Note: not `constexpr` because `std::isnan` is not constexpr in standard C++20
/// (GCC/Clang accept it as an extension, MSVC does not).
[[nodiscard]] inline bool is_valid(double x) noexcept {
    return !std::isnan(x);
}

} // namespace opticore
