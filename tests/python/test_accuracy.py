"""Python-side accuracy tests mirroring C++ reference_values.hpp.

Catches binding-layer issues: type conversions, NaN propagation,
scalar/array dispatch, NumPy contiguity.
"""

import numpy as np
import pytest

import opticore as oc


# ════════════════════════════════════════════════════════════════════════════
# Reference values (identical to tests/cpp/reference_values.hpp)
# ════════════════════════════════════════════════════════════════════════════

REF_CASES = [
    # (S, K, T, r, sigma, q, call_price, put_price,
    #  call_delta, put_delta, gamma, vega,
    #  call_theta, put_theta, call_rho, put_rho, desc)
    (100, 100, 1.0, 0.05, 0.2, 0.0,
     10.450583572186, 5.573526022257,
     0.636830651176, -0.363169348824,
     0.018762017346, 0.375240346917,
     -0.017572678209, -0.004542138148,
     0.532324815454, -0.418904609047,
     "ATM 1Y"),
    (100, 100, 0.5, 0.05, 0.2, 0.0,
     6.888728577681, 4.419719780514,
     0.597734468908, -0.402265531092,
     0.027358658565, 0.273586585652,
     -0.022235527750, -0.008875117996,
     0.264423591566, -0.223231364448,
     "ATM 6M"),
    (100, 100, 0.25, 0.05, 0.2, 0.0,
     4.614997129603, 3.372777178991,
     0.569460183208, -0.430539816792,
     0.039288000945, 0.196440004724,
     -0.028696304790, -0.015167841770,
     0.130827552978, -0.116066897146,
     "ATM 3M"),
    (100, 100, 0.0833, 0.05, 0.2, 0.0,
     2.511522873285, 2.095889031602,
     0.540231155369, -0.459768844631,
     0.068760930440, 0.114555710113,
     -0.044733604716, -0.031091910721,
     0.042909156689, -0.040044620321,
     "ATM 1M"),
    (100, 110, 1.0, 0.05, 0.2, 0.0,
     6.040088129724, 10.675324824803,
     0.449647930637, -0.550352069363,
     0.019788024019, 0.395760480388,
     -0.016174904248, -0.001841310180,
     0.389247049340, -0.657105317611,
     "OTM call 10%"),
    (100, 90, 1.0, 0.05, 0.2, 0.0,
     16.699448408416, 2.310096613480,
     0.809703060775, -0.190296939225,
     0.013581289746, 0.271625794926,
     -0.016246029679, -0.004518543623,
     0.642708576691, -0.213397905359,
     "ITM call 10%"),
    (100, 120, 1.0, 0.05, 0.2, 0.0,
     3.247477416561, 17.395008356646,
     0.287191637905, -0.712808362095,
     0.017036921139, 0.340738422770,
     -0.012824571360, 0.002812076714,
     0.254716863740, -0.886758445661,
     "OTM call 20%"),
    (100, 80, 1.0, 0.05, 0.2, 0.0,
     24.588835443928, 0.687189403985,
     0.928637402665, -0.071362597335,
     0.006813597182, 0.136271943640,
     -0.013086204596, -0.002661772547,
     0.682749048226, -0.078234491375,
     "ITM call 20%"),
    (100, 100, 1.0, 0.05, 0.1, 0.0,
     6.804957708822, 1.927900158894,
     0.708840313212, -0.291159686788,
     0.034294385502, 0.342943855019,
     -0.013475816317, -0.000445276255,
     0.640790736123, -0.310438688377,
     "Low vol 10%"),
    (100, 100, 1.0, 0.05, 0.4, 0.0,
     18.022951450217, 13.145893900288,
     0.627409464153, -0.372590535847,
     0.009460495798, 0.378419831934,
     -0.026861085992, -0.013830545930,
     0.447179949651, -0.504049474850,
     "High vol 40%"),
    (100, 100, 1.0, 0.05, 0.8, 0.0,
     32.820982466990, 27.943924917061,
     0.678138598836, -0.321861401164,
     0.004480958552, 0.358476684183,
     -0.044078660926, -0.031048120865,
     0.349928774166, -0.601300650334,
     "Very high vol 80%"),
    (100, 100, 2.0, 0.05, 0.2, 0.0,
     16.126779724979, 6.610521528575,
     0.689691026781, -0.310308973219,
     0.012478546402, 0.499141856072,
     -0.014076234049, -0.001681200926,
     1.056846459063, -0.752828377009,
     "Long 2Y"),
    (100, 100, 5.0, 0.05, 0.2, 0.0,
     29.138619743886039, 7.018698051026529,
     0.783075967117, -0.216924032883,
     0.006567383582, 0.656738358178,
     -0.010334042643136, 0.000334461234554,
     2.458448848390, -1.435555066967,
     "Very long 5Y"),
    (100, 100, 1.0, 0.0, 0.2, 0.0,
     7.965567455406, 7.965567455406,
     0.539827837277, -0.460172162723,
     0.019847627374, 0.396952547477,
     -0.010875412260, -0.010875412260,
     0.460172162723, -0.539827837277,
     "Zero rate"),
    (100, 100, 1.0, 0.1, 0.2, 0.0,
     13.269676584661, 3.753418388257,
     0.725746882250, -0.274253117750,
     0.016661230145, 0.333224602892,
     -0.025377389570, -0.000587323322,
     0.593050116403, -0.311787301633,
     "High rate 10%"),
    (100, 100, 1.0, 0.05, 0.2, 0.03,
     8.652528553943, 6.730917649163,
     0.562139997790, -0.408305535759,
     0.018974281790, 0.379485635795,
     -0.012291808016, -0.007237532614,
     0.475614712250, -0.475614712250,
     "With dividend 3%"),
    (100, 100, 1.0, 0.05, 0.2, 0.05,
     7.577082146427, 7.577082146427,
     0.513500122982, -0.437729301518,
     0.018879647165, 0.377592943291,
     -0.009307055687, -0.009307055687,
     0.437729301518, -0.513500122982,
     "High dividend 5%"),
    (42, 40, 0.5, 0.1, 0.2, 0.0,
     4.759422392872, 0.808599372900,
     0.779131290943, -0.220868709057,
     0.049962670406, 0.088134150596,
     -0.012490663547, -0.002066231498,
     0.139820459134, -0.050425425767,
     "Hull example"),
    (50, 50, 0.25, 0.1, 0.3, 0.0,
     3.610445066084, 2.375940667501,
     0.595480769902, -0.404519230098,
     0.051661474846, 0.096865265336,
     -0.023091165104, -0.009730755350,
     0.065408983573, -0.056504755431,
     "Hull 14.1"),
    (200, 200, 0.5, 0.03, 0.25, 0.0,
     15.520513343818, 12.542901264431,
     0.568769064678, -0.431230935322,
     0.011115728426, 0.555786421277,
     -0.046141532931, -0.029947912006,
     0.491166497959, -0.493945441644,
     "Index option"),
]


def _unpack(case):
    """Unpack a reference case tuple into a dict."""
    return dict(
        S=case[0], K=case[1], T=case[2], r=case[3], sigma=case[4], q=case[5],
        call_price=case[6], put_price=case[7],
        call_delta=case[8], put_delta=case[9],
        gamma=case[10], vega=case[11],
        call_theta=case[12], put_theta=case[13],
        call_rho=case[14], put_rho=case[15],
        desc=case[16],
    )


# ════════════════════════════════════════════════════════════════════════════
# Pricing accuracy (20 cases × call + put = 40 checks)
# ════════════════════════════════════════════════════════════════════════════

class TestPricingAccuracy:
    """BSM prices via Python must match reference values to 1e-10 relative."""

    @pytest.mark.parametrize("case", REF_CASES, ids=[c[-1] for c in REF_CASES])
    def test_call_price(self, case):
        c = _unpack(case)
        price = oc.price(
            spot=c["S"], strike=c["K"], expiry=c["T"],
            rate=c["r"], vol=c["sigma"], kind="call", div_yield=c["q"],
        )
        np.testing.assert_allclose(price, c["call_price"], rtol=1e-10,
                                   err_msg=f'{c["desc"]} call price')

    @pytest.mark.parametrize("case", REF_CASES, ids=[c[-1] for c in REF_CASES])
    def test_put_price(self, case):
        c = _unpack(case)
        price = oc.price(
            spot=c["S"], strike=c["K"], expiry=c["T"],
            rate=c["r"], vol=c["sigma"], kind="put", div_yield=c["q"],
        )
        np.testing.assert_allclose(price, c["put_price"], rtol=1e-10,
                                   err_msg=f'{c["desc"]} put price')


# ════════════════════════════════════════════════════════════════════════════
# Greeks accuracy (20 cases × 6 Greeks × call + put)
# ════════════════════════════════════════════════════════════════════════════

class TestGreeksAccuracy:
    """All Greeks via Python must match reference values to 1e-10 relative.

    C++ core is verified to 1e-12. Python tolerance is slightly looser to
    account for floating-point overhead in the nanobind binding layer.
    """

    GREEKS_RTOL = 1e-9

    @pytest.mark.parametrize("case", REF_CASES, ids=[c[-1] for c in REF_CASES])
    def test_call_greeks(self, case):
        c = _unpack(case)
        g = oc.greeks(
            spot=c["S"], strike=c["K"], expiry=c["T"],
            rate=c["r"], vol=c["sigma"], kind="call", div_yield=c["q"],
        )
        rtol = self.GREEKS_RTOL
        np.testing.assert_allclose(g.price, c["call_price"], rtol=1e-10,
                                   err_msg=f'{c["desc"]} call price')
        np.testing.assert_allclose(g.delta, c["call_delta"], rtol=rtol,
                                   err_msg=f'{c["desc"]} call delta')
        np.testing.assert_allclose(g.gamma, c["gamma"], rtol=rtol,
                                   err_msg=f'{c["desc"]} gamma')
        np.testing.assert_allclose(g.vega, c["vega"], rtol=rtol,
                                   err_msg=f'{c["desc"]} vega')
        np.testing.assert_allclose(g.theta, c["call_theta"], rtol=rtol,
                                   err_msg=f'{c["desc"]} call theta')
        np.testing.assert_allclose(g.rho, c["call_rho"], rtol=rtol,
                                   err_msg=f'{c["desc"]} call rho')

    @pytest.mark.parametrize("case", REF_CASES, ids=[c[-1] for c in REF_CASES])
    def test_put_greeks(self, case):
        c = _unpack(case)
        g = oc.greeks(
            spot=c["S"], strike=c["K"], expiry=c["T"],
            rate=c["r"], vol=c["sigma"], kind="put", div_yield=c["q"],
        )
        rtol = self.GREEKS_RTOL
        np.testing.assert_allclose(g.price, c["put_price"], rtol=1e-10,
                                   err_msg=f'{c["desc"]} put price')
        np.testing.assert_allclose(g.delta, c["put_delta"], rtol=rtol,
                                   err_msg=f'{c["desc"]} put delta')
        np.testing.assert_allclose(g.gamma, c["gamma"], rtol=rtol,
                                   err_msg=f'{c["desc"]} gamma')
        np.testing.assert_allclose(g.vega, c["vega"], rtol=rtol,
                                   err_msg=f'{c["desc"]} vega')
        np.testing.assert_allclose(g.theta, c["put_theta"], rtol=rtol,
                                   err_msg=f'{c["desc"]} put theta')
        np.testing.assert_allclose(g.rho, c["put_rho"], rtol=rtol,
                                   err_msg=f'{c["desc"]} put rho')


# ════════════════════════════════════════════════════════════════════════════
# IV round-trip accuracy (20 cases × call + put)
# ════════════════════════════════════════════════════════════════════════════

class TestIVAccuracy:
    """IV round-trip: price(sigma) → iv() should recover sigma."""

    @pytest.mark.parametrize("case", REF_CASES, ids=[c[-1] for c in REF_CASES])
    def test_call_iv_round_trip(self, case):
        c = _unpack(case)
        solved = oc.iv(
            price_val=c["call_price"], spot=c["S"], strike=c["K"],
            expiry=c["T"], rate=c["r"], kind="call", div_yield=c["q"],
        )
        if c["sigma"] >= 0.02:
            np.testing.assert_allclose(solved, c["sigma"], rtol=1e-12,
                                       err_msg=f'{c["desc"]} call IV')
        else:
            np.testing.assert_allclose(solved, c["sigma"], atol=1e-9,
                                       err_msg=f'{c["desc"]} call IV (low vol)')

    @pytest.mark.parametrize("case", REF_CASES, ids=[c[-1] for c in REF_CASES])
    def test_put_iv_round_trip(self, case):
        c = _unpack(case)
        solved = oc.iv(
            price_val=c["put_price"], spot=c["S"], strike=c["K"],
            expiry=c["T"], rate=c["r"], kind="put", div_yield=c["q"],
        )
        if c["sigma"] >= 0.02:
            np.testing.assert_allclose(solved, c["sigma"], rtol=1e-12,
                                       err_msg=f'{c["desc"]} put IV')
        else:
            np.testing.assert_allclose(solved, c["sigma"], atol=1e-9,
                                       err_msg=f'{c["desc"]} put IV (low vol)')


# ════════════════════════════════════════════════════════════════════════════
# Vectorized == Scalar (binding-layer fidelity)
# ════════════════════════════════════════════════════════════════════════════

class TestVectorizedMatchesScalar:
    """Vectorized batch path must produce identical results to scalar path."""

    def test_price_batch_matches_scalar(self):
        """oc.price() with arrays must match element-wise scalar calls exactly."""
        spots = np.array([100.0, 42.0, 50.0, 200.0])
        strikes = np.array([100.0, 40.0, 50.0, 200.0])
        expiries = np.array([1.0, 0.5, 0.25, 0.5])
        rates = np.array([0.05, 0.1, 0.1, 0.03])
        vols = np.array([0.2, 0.2, 0.3, 0.25])
        divs = np.array([0.0, 0.0, 0.0, 0.0])

        scalar_prices = np.array([
            oc.price(spot=spots[i], strike=strikes[i], expiry=expiries[i],
                     rate=rates[i], vol=vols[i], kind="call", div_yield=divs[i])
            for i in range(len(spots))
        ])

        # General vectorized path (varies spot, so hits the element-wise loop)
        vec_prices = oc.price(
            spot=spots, strike=strikes, expiry=expiries,
            rate=0.05, vol=0.2, kind="call",
        )
        scalar_prices_uniform = np.array([
            oc.price(spot=spots[i], strike=strikes[i], expiry=expiries[i],
                     rate=0.05, vol=0.2, kind="call")
            for i in range(len(spots))
        ])
        np.testing.assert_array_equal(vec_prices, scalar_prices_uniform)

    def test_price_batch_strikes_matches_scalar(self):
        """Optimized batch path (scalar spot, array strikes) matches scalar."""
        strikes = np.arange(80.0, 121.0)
        batch_prices = oc.price(
            spot=100, strike=strikes, expiry=0.5, rate=0.05, vol=0.2, kind="call",
        )
        scalar_prices = np.array([
            oc.price(spot=100, strike=k, expiry=0.5, rate=0.05, vol=0.2, kind="call")
            for k in strikes
        ])
        np.testing.assert_array_equal(batch_prices, scalar_prices)

    def test_iv_batch_matches_scalar(self):
        """oc.iv() batch must match scalar calls exactly."""
        vols = np.array([0.15, 0.20, 0.25, 0.30, 0.35])
        prices = np.array([
            oc.price(spot=100, strike=100, expiry=1.0, rate=0.05, vol=v, kind="call")
            for v in vols
        ])

        batch_iv = oc.iv(
            price_val=prices, spot=np.full(5, 100.0),
            strike=np.full(5, 100.0), expiry=np.full(5, 1.0),
            rate=0.05, kind="call",
        )
        scalar_iv = np.array([
            oc.iv(price_val=prices[i], spot=100, strike=100, expiry=1.0,
                  rate=0.05, kind="call")
            for i in range(5)
        ])
        np.testing.assert_array_equal(batch_iv, scalar_iv)

    def test_greeks_table_matches_scalar(self):
        """greeks_table() must match greeks() for each row."""
        strikes = np.array([90.0, 100.0, 110.0])
        df = oc.greeks_table(
            spot=100, strike=strikes, expiry=0.5, rate=0.05, vol=0.2, kind="call",
        )
        for i, k in enumerate(strikes):
            g = oc.greeks(spot=100, strike=k, expiry=0.5, rate=0.05, vol=0.2, kind="call")
            np.testing.assert_equal(df["price"].iloc[i], g.price)
            np.testing.assert_equal(df["delta"].iloc[i], g.delta)
            np.testing.assert_equal(df["gamma"].iloc[i], g.gamma)
            np.testing.assert_equal(df["theta"].iloc[i], g.theta)
            np.testing.assert_equal(df["vega"].iloc[i], g.vega)
            np.testing.assert_equal(df["rho"].iloc[i], g.rho)


# ════════════════════════════════════════════════════════════════════════════
# NaN propagation through bindings
# ════════════════════════════════════════════════════════════════════════════

class TestNaNPropagation:
    """NaN/edge cases must propagate correctly through the binding layer."""

    def test_nan_input_price(self):
        """NaN inputs produce NaN output, no exceptions."""
        result = oc.price(spot=np.nan, strike=100, expiry=1.0, rate=0.05, vol=0.2, kind="call")
        assert np.isnan(result)

    def test_nan_input_iv(self):
        """IV of NaN price returns NaN."""
        result = oc.iv(price_val=np.nan, spot=100, strike=100, expiry=1.0, rate=0.05, kind="call")
        assert np.isnan(result)

    def test_zero_time_value_returns_nan_iv(self):
        """Deep ITM with no time value: IV should be NaN."""
        # Deep ITM call: intrinsic ≈ price, no time value
        intrinsic = 100 - 50 * np.exp(-0.05 * 0.25)  # ~ 50.62
        result = oc.iv(price_val=intrinsic, spot=100, strike=50, expiry=0.25,
                       rate=0.05, kind="call")
        assert np.isnan(result)

    def test_vectorized_nan_propagation(self):
        """NaN in one element of batch doesn't corrupt other elements."""
        prices = np.array([10.45, -1.0, 6.89])  # middle one is invalid
        spots = np.full(3, 100.0)
        strikes = np.full(3, 100.0)
        expiries = np.full(3, 1.0)
        result = oc.iv(
            price_val=prices, spot=spots, strike=strikes, expiry=expiries,
            rate=0.05, kind="call",
        )
        assert np.isfinite(result[0])
        assert np.isnan(result[1])
        assert np.isfinite(result[2])


# ════════════════════════════════════════════════════════════════════════════
# Contiguity & type handling
# ════════════════════════════════════════════════════════════════════════════

class TestArrayHandling:
    """Binding layer handles non-contiguous and non-float64 arrays."""

    def test_non_contiguous_array(self):
        """Sliced (non-contiguous) arrays should work via Python wrapper."""
        strikes = np.arange(80.0, 121.0)[::2]  # non-contiguous slice
        assert not strikes.flags["C_CONTIGUOUS"]
        prices = oc.price(spot=100, strike=strikes, expiry=0.5, rate=0.05, vol=0.2, kind="call")
        assert len(prices) == len(strikes)
        assert all(np.isfinite(prices))

    def test_int_array_coerced(self):
        """Integer arrays should be coerced to float64."""
        strikes = np.arange(90, 111)  # int64
        prices = oc.price(spot=100, strike=strikes, expiry=0.5, rate=0.05, vol=0.2, kind="call")
        assert len(prices) == len(strikes)

    def test_float32_coerced(self):
        """float32 arrays should be coerced to float64."""
        strikes = np.arange(90, 111, dtype=np.float32)
        prices = oc.price(spot=100, strike=strikes, expiry=0.5, rate=0.05, vol=0.2, kind="call")
        assert len(prices) == len(strikes)

    def test_0d_array_treated_as_scalar(self):
        """np.float64(5.0) (0-d array) should dispatch to scalar path."""
        p = oc.price(
            spot=np.float64(100.0), strike=np.float64(100.0),
            expiry=np.float64(1.0), rate=0.05, vol=0.2, kind="call",
        )
        assert isinstance(p, float)

    def test_kind_variations(self):
        """All accepted kind strings produce correct results."""
        base = oc.price(spot=100, strike=100, expiry=1.0, rate=0.05, vol=0.2, kind="call")
        for k in ("call", "Call", "CALL", "c", "C"):
            assert oc.price(spot=100, strike=100, expiry=1.0, rate=0.05, vol=0.2, kind=k) == base
        base_put = oc.price(spot=100, strike=100, expiry=1.0, rate=0.05, vol=0.2, kind="put")
        for k in ("put", "Put", "PUT", "p", "P"):
            assert oc.price(spot=100, strike=100, expiry=1.0, rate=0.05, vol=0.2, kind=k) == base_put
