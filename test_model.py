import numpy as np
import pytest

from margin_console import ab_design as ab
from margin_console.demo_data import make_demo_orders
from margin_console.model import (Policy, breakeven_max_abandon, breakeven_table,
                                  fit_cost_model, simulate, sweep_threshold)


@pytest.fixture(scope="module")
def df():
    return make_demo_orders(60_000, seed=1)


def test_baseline_matches_dataset_profit(df):
    r = simulate(df, Policy(threshold=0)).iloc[0]
    assert abs(r.base_profit - df.profit.sum()) < 0.06 * len(df)   # profit is rounded to 0.1
    assert r.delta_profit == 0 and r.orders_lost == 0


def test_cost_is_pure_function_of_distance(df):
    m = fit_cost_model(df)
    assert m["r2"] > 0.999 and abs(m["intercept"] - 29) < 1e-6 and abs(m["per_km"] - 8) < 1e-6


def test_everyone_tops_up(df):
    p = Policy(mode="mov", threshold=200, topup_rate=1.0)
    r = simulate(df, p).iloc[0]
    assert r.orders_lost == 0 and r.loss_pct < 1.0 and r.delta_profit > 0


def test_everyone_abandons_removes_small_baskets(df):
    p = Policy(mode="mov", threshold=200, topup_rate=0.0)
    r = simulate(df, p).iloc[0]
    small = df[df.order_value < 200]
    assert r.orders_lost == pytest.approx(len(small))
    assert r.profit == pytest.approx(r.base_profit - (small.order_value - small.delivery_cost - small.discount_amt).sum())


def test_decomposition_sums_to_delta(df):
    for p in (Policy(mode="mov", threshold=180, topup_rate=.3),
              Policy(mode="fee", threshold=180, fee_flat=15, fee_per_km=1, topup_rate=.3, abandon_rate=.2)):
        r = simulate(df, p).iloc[0]
        parts = r.d_topup + r.d_fee + r.d_loss_avoided + r.d_forgone
        assert parts == pytest.approx(r.delta_profit, rel=1e-9)


def test_group_totals_equal_overall(df):
    p = Policy(threshold=150)
    by_city = simulate(df, p, ["city"])
    total = simulate(df, p).iloc[0]
    assert by_city.delta_profit.sum() == pytest.approx(total.delta_profit)
    both = simulate(df, p, ["city", "company"])
    assert both.orders.sum() == len(df)


@pytest.mark.parametrize("p", [
    Policy(mode="mov", threshold=150),
    Policy(mode="fee", threshold=300, fee_flat=0, fee_per_km=0, topup_rate=0.2),     # interior solution
    Policy(mode="fee", threshold=150, fee_flat=12, fee_per_km=0.5, topup_rate=0.2),  # always pays
])
def test_breakeven_is_really_break_even(df, p):
    b = breakeven_max_abandon(df, p)
    assert b is not None
    a = p.topup_rate if p.mode == "fee" else 1 - b
    q = Policy(**{**p.__dict__, "topup_rate": a, "abandon_rate": b})
    delta = simulate(df, q).iloc[0].delta_profit
    if p.mode == "fee" and b >= 1 - p.topup_rate - 1e-9:
        assert delta >= 0                       # policy pays off even if everyone else leaves
    else:
        assert delta == pytest.approx(0, abs=50)  # exactly break-even


def test_sweep_matches_full_simulation(df):
    p = Policy(threshold=0, topup_rate=.5)
    sw = sweep_threshold(df, p, [0, 100, 250]).set_index("threshold")
    for t in (100, 250):
        full = simulate(df, Policy(**{**p.__dict__, "threshold": t})).iloc[0]
        assert sw.loc[t, "delta_profit"] == pytest.approx(full.delta_profit)
        assert sw.loc[t, "loss_pct"] == pytest.approx(full.loss_pct)


def test_lower_margin_creates_more_losses(df):
    hi = simulate(df, Policy(margin=1.0)).iloc[0].base_loss_pct
    lo = simulate(df, Policy(margin=0.25)).iloc[0].base_loss_pct
    assert lo > hi


def test_breakeven_table_grows_with_distance(df):
    assert (breakeven_table(df, "city").break_even_basket > 29).all()


def test_ab_sample_size_known_values():
    assert 3800 <= ab.n_per_arm_prop(0.10, 0.02) <= 3900     # textbook ~3,839/arm
    assert 1560 <= ab.n_per_arm_mean(100, 10) <= 1575        # 2*(1.96+0.84)^2*100 ~ 1,568
    assert ab.duration_days(1000, 10_000) == 14              # floor: two full weeks
    assert ab.duration_days(100_000, 5_000) % 7 == 0
    m, s = ab.session_profit_sigma(50, 100, 1.0)
    assert m == 100 and s == pytest.approx(50)
