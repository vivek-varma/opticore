#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/stl/string.h>

#include "opticore/bsm.hpp"
#include "opticore/jaeckel.hpp"
#include "opticore/greeks.hpp"

namespace nb = nanobind;
using namespace nb::literals;

// Helper: convert "call"/"put" string to bool
static bool parse_kind(const std::string& kind) {
    if (kind == "call" || kind == "Call" || kind == "CALL" || kind == "c" || kind == "C")
        return true;
    if (kind == "put" || kind == "Put" || kind == "PUT" || kind == "p" || kind == "P")
        return false;
    throw nb::value_error("kind must be 'call' or 'put'");
}

NB_MODULE(_core, m) {
    m.doc() = "OptiCore C++ core: high-performance options pricing engine";

    // ════════════════════════════════════════════════════════════════════
    // Scalar pricing
    // ════════════════════════════════════════════════════════════════════

    m.def("_bsm_price_scalar",
        [](double spot, double strike, double expiry,
           double rate, double vol, double div_yield, bool is_call) -> double {
            return opticore::bsm_price(spot, strike, expiry, rate, vol, div_yield, is_call);
        },
        "spot"_a, "strike"_a, "expiry"_a, "rate"_a, "vol"_a,
        "div_yield"_a = 0.0, "is_call"_a = true,
        "Price a European option using Black-Scholes-Merton (scalar)."
    );

    // ════════════════════════════════════════════════════════════════════
    // Batch pricing (NumPy arrays)
    // ════════════════════════════════════════════════════════════════════

    m.def("_bsm_price_batch",
        [](double spot,
           nb::ndarray<double, nb::ndim<1>, nb::c_contig> strike,
           nb::ndarray<double, nb::ndim<1>, nb::c_contig> expiry,
           double rate, double vol, double div_yield, bool is_call) {

            size_t n = strike.shape(0);
            if (expiry.shape(0) != n) {
                throw nb::value_error("strike and expiry must have same length");
            }

            // Allocate output
            double* result = new double[n];
            opticore::bsm_price_batch_strikes(
                spot, strike.data(), expiry.data(),
                rate, vol, div_yield, is_call, result, n
            );

            // Return as NumPy array (takes ownership)
            nb::capsule owner(result, [](void* p) noexcept { delete[] static_cast<double*>(p); });
            return nb::ndarray<nb::numpy, double, nb::ndim<1>>(result, {n}, owner);
        },
        "spot"_a, "strike"_a, "expiry"_a, "rate"_a, "vol"_a,
        "div_yield"_a = 0.0, "is_call"_a = true,
        "Batch price with scalar spot/rate/vol and array strike/expiry."
    );

    // ════════════════════════════════════════════════════════════════════
    // Implied volatility
    // ════════════════════════════════════════════════════════════════════

    m.def("_implied_vol_scalar",
        [](double price, double spot, double strike, double expiry,
           double rate, double div_yield, bool is_call) -> double {
            return opticore::implied_vol(price, spot, strike, expiry,
                                         rate, div_yield, is_call);
        },
        "price"_a, "spot"_a, "strike"_a, "expiry"_a, "rate"_a,
        "div_yield"_a = 0.0, "is_call"_a = true,
        "Compute implied volatility using Jaeckel's Let's Be Rational (scalar)."
    );

    m.def("_implied_vol_batch",
        [](nb::ndarray<double, nb::ndim<1>, nb::c_contig> price,
           nb::ndarray<double, nb::ndim<1>, nb::c_contig> spot,
           nb::ndarray<double, nb::ndim<1>, nb::c_contig> strike,
           nb::ndarray<double, nb::ndim<1>, nb::c_contig> expiry,
           double rate, double div_yield,
           nb::ndarray<bool, nb::ndim<1>, nb::c_contig> is_call) {

            size_t n = price.shape(0);
            double* result = new double[n];
            opticore::implied_vol_batch(
                price.data(), spot.data(), strike.data(), expiry.data(),
                rate, div_yield, is_call.data(), result, n
            );

            nb::capsule owner(result, [](void* p) noexcept { delete[] static_cast<double*>(p); });
            return nb::ndarray<nb::numpy, double, nb::ndim<1>>(result, {n}, owner);
        },
        "price"_a, "spot"_a, "strike"_a, "expiry"_a, "rate"_a,
        "div_yield"_a = 0.0, "is_call"_a = true,
        "Batch implied volatility solve."
    );

    // ════════════════════════════════════════════════════════════════════
    // Greeks
    // ════════════════════════════════════════════════════════════════════

    m.def("_greeks_scalar",
        [](double spot, double strike, double expiry,
           double rate, double vol, double div_yield, bool is_call) {
            auto g = opticore::compute_greeks(spot, strike, expiry,
                                               rate, vol, div_yield, is_call);
            return nb::make_tuple(g.price, g.delta, g.gamma,
                                  g.theta, g.vega, g.rho);
        },
        "spot"_a, "strike"_a, "expiry"_a, "rate"_a, "vol"_a,
        "div_yield"_a = 0.0, "is_call"_a = true,
        "Compute all Greeks in a single pass (scalar). Returns (price, delta, gamma, theta, vega, rho)."
    );

    m.def("_greeks_batch",
        [](nb::ndarray<double, nb::ndim<1>, nb::c_contig> spot,
           nb::ndarray<double, nb::ndim<1>, nb::c_contig> strike,
           nb::ndarray<double, nb::ndim<1>, nb::c_contig> expiry,
           double rate,
           nb::ndarray<double, nb::ndim<1>, nb::c_contig> vol,
           double div_yield,
           nb::ndarray<bool, nb::ndim<1>, nb::c_contig> is_call) {

            size_t n = spot.shape(0);

            double* price = new double[n];
            double* delta = new double[n];
            double* gamma = new double[n];
            double* theta = new double[n];
            double* vega  = new double[n];
            double* rho   = new double[n];

            opticore::compute_greeks_batch(
                spot.data(), strike.data(), expiry.data(),
                rate, vol.data(), div_yield, is_call.data(),
                price, delta, gamma, theta, vega, rho, n
            );

            auto make_arr = [&](double* ptr) {
                nb::capsule owner(ptr, [](void* p) noexcept { delete[] static_cast<double*>(p); });
                return nb::ndarray<nb::numpy, double, nb::ndim<1>>(ptr, {n}, owner);
            };

            return nb::make_tuple(
                make_arr(price), make_arr(delta), make_arr(gamma),
                make_arr(theta), make_arr(vega), make_arr(rho)
            );
        },
        "spot"_a, "strike"_a, "expiry"_a, "rate"_a, "vol"_a,
        "div_yield"_a = 0.0, "is_call"_a = true,
        "Batch Greeks computation. Returns tuple of 6 arrays."
    );
}
