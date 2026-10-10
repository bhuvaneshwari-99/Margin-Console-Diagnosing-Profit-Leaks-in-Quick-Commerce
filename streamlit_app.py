"""Margin Console - what-if tool for a minimum-order-value / small-order-fee policy."""
from __future__ import annotations

import dataclasses

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from margin_console import ab_design as ab
from margin_console.data import load_orders
from margin_console.model import (Policy, breakeven_max_abandon, breakeven_table,
                                  fit_cost_model, sensitivity_grid, simulate, sweep_threshold)

st.set_page_config(page_title="Margin Console", page_icon="📉", layout="wide")


# ----------------------------------------------------------------------------- helpers
def inr(x: float, signed: bool = False) -> str:
    """Indian-style short currency: 4.2L, 1.3Cr."""
    sign = ("+" if x > 0 else "-" if x < 0 else "") if signed else ("-" if x < 0 else "")
    v = abs(x)
    if v >= 1e7:
        s = f"{v / 1e7:.2f} Cr"
    elif v >= 1e5:
        s = f"{v / 1e5:.2f} L"
    else:
        s = f"{v:,.0f}"
    return f"{sign}₹{s}"


@st.cache_data(show_spinner=False, max_entries=64)
def _sim(_df, key, pd_, by=None):
    return simulate(_df, Policy(**pd_), by)


@st.cache_data(show_spinner=False, max_entries=64)
def _be(_df, key, pd_):
    return breakeven_max_abandon(_df, Policy(**pd_))


@st.cache_data(show_spinner="Sweeping thresholds...", max_entries=16)
def _sweep(_df, key, pd_, ths):
    return sweep_threshold(_df, Policy(**pd_), ths)


@st.cache_data(show_spinner="Building sensitivity grid...", max_entries=16)
def _grid(_df, key, pd_, ths, tops):
    return sensitivity_grid(_df, Policy(**pd_), ths, tops)


@st.cache_data(show_spinner=False, max_entries=16)
def _cost_fit(_df, key):
    return fit_cost_model(_df)


@st.cache_data(show_spinner=False, max_entries=32)
def _betable(_df, key, by, margin):
    return breakeven_table(_df, by, margin)


# ----------------------------------------------------------------------------- data
df, source, warn = load_orders()
st.title("📉 Margin Console")
st.caption("Set a minimum basket or small-order fee. See the expected change in profit, "
           "loss-making orders and lost orders - overall, by city and by platform.")
if source == "Synthetic demo":
    st.warning("**Demo data.** No BigQuery connection or `data/orders.parquet` found, so this runs on "
               "synthetic orders. Numbers below are illustrative, not the project's findings.")
if warn:
    st.warning(warn)

# ----------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("1 · Policy")
    lever = st.radio("Lever", ["Minimum order value", "Small-order fee"],
                     help="Minimum order value blocks small baskets: customers top up or leave. "
                          "A fee lets them order but charges extra.")
    mode = "mov" if lever == "Minimum order value" else "fee"
    threshold = st.slider("Small-basket threshold (₹)", 0, 500, 150, 10,
                          help="Baskets below this are 'small'. Set 0 to see today's baseline.")
    fee_flat = fee_km = 0.0
    if mode == "fee":
        fee_flat = st.slider("Flat fee (₹)", 0, 60, 15, 1)
        fee_km = st.slider("Extra fee per km (₹)", 0.0, 5.0, 0.0, 0.5)

    st.header("2 · Customer response")
    st.caption("Assumptions - the data cannot tell us these. An A/B test can (see the Experiment tab).")
    topup = st.slider("Small baskets that top up to the threshold", 0, 100, 40, 5, format="%d%%") / 100
    abandon = 1 - topup
    if mode == "fee":
        abandon = st.slider("Small baskets that abandon", 0, 100, 25, 5, format="%d%%") / 100
        if topup + abandon > 1:
            st.info("Top-up + abandon exceed 100%; abandon is capped.")

    st.header("3 · Economics")
    margin = st.slider("Contribution per ₹ of basket", 5, 100, 100, 5, format="%d%%",
                       help="100% reproduces the dataset's Profit (= order value - delivery - discount, "
                            "i.e. before product cost). Lower it to stress-test with product cost.") / 100
    cost_scale = st.slider("Delivery cost vs dataset assumption", 50, 150, 100, 5, format="%d%%",
                           help="Delivery cost in the dataset is modelled, not observed. Stress-test it.") / 100

    st.header("4 · Scope")
    companies = st.multiselect("Platforms", sorted(df.company.unique()), default=sorted(df.company.unique()))
    cities = st.multiselect("Cities", sorted(df.city.unique()), default=sorted(df.city.unique()))
    st.caption(f"Data source: **{source}** · {len(df):,} orders")

if not companies or not cities:
    st.error("Select at least one platform and one city.")
    st.stop()

dff = df[df.company.isin(companies) & df.city.isin(cities)]
if cost_scale != 1.0:
    dff = dff.assign(delivery_cost=dff.delivery_cost * cost_scale)
key = f"{source}|{len(df)}|{','.join(sorted(companies))}|{','.join(sorted(cities))}|{cost_scale}"

policy = Policy(mode=mode, threshold=float(threshold), fee_flat=float(fee_flat), fee_per_km=float(fee_km),
                topup_rate=float(topup), abandon_rate=float(abandon), margin=float(margin))
pd_ = dataclasses.asdict(policy)
r = _sim(dff, key, pd_).iloc[0]
be = _be(dff, key, pd_)

# ----------------------------------------------------------------------------- headline
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Expected profit", inr(r.profit), f"{r.delta_pct:+.1f}% vs today" if threshold else "baseline")
c2.metric("Change in profit", inr(r.delta_profit, signed=True))
c3.metric("Loss-making orders", f"{r.loss_pct:.1f}%",
          f"{r.loss_pct - r.base_loss_pct:+.1f} pts" if threshold else f"{r.base_loss_pct:.1f}% today",
          delta_color="inverse")
c4.metric("Orders lost", f"{r.orders_lost:,.0f}", f"{100 * r.orders_lost / r.orders:.1f}% of orders",
          delta_color="off")
if threshold == 0:
    c5.metric("Break-even", "-", "set a threshold", delta_color="off")
elif be is None:
    c5.metric("Break-even", "never", "loses money at any response", delta_color="off")
else:
    c5.metric("Break-even", f"≤ {be:.0%} abandon",
              "of small baskets, then policy stops paying", delta_color="off")

if threshold:
    verdict = "adds" if r.delta_profit >= 0 else "removes"
    st.markdown(
        f"**{lever} at {inr(threshold)}** affects **{r.small_baskets:,.0f}** of {r.orders:,.0f} orders "
        f"({100 * r.small_baskets / r.orders:.1f}%). Under the response assumptions it {verdict} "
        f"**{inr(abs(r.delta_profit))}** of profit and cuts loss-making orders from "
        f"**{r.base_loss_pct:.1f}% to {r.loss_pct:.1f}%**. *Expected values under stated assumptions, not a forecast.*")
if margin == 1.0:
    st.caption("ℹ️ Contribution is 100% of basket value (the dataset's Profit definition). "
               "Real grocery margins are far lower - use slider 3 to see how conclusions change.")

tab_imp, tab_seg, tab_sweep, tab_be, tab_exp, tab_method = st.tabs(
    ["Impact", "By city & platform", "Threshold sweep", "Break-even", "Experiment design", "Method & caveats"])

# ----------------------------------------------------------------------------- Impact
with tab_imp:
    if threshold == 0:
        st.info("Choose a threshold above ₹0 in the sidebar to see where the profit change comes from.")
    else:
        parts = pd.DataFrame({
            "driver": ["Top-ups add basket value", "Fees collected", "Loss-making orders shed",
                       "Profitable orders forgone"],
            "value": [r.d_topup, r.d_fee, r.d_loss_avoided, r.d_forgone]})
        parts["sign"] = np.where(parts.value >= 0, "gain", "cost")
        ch = alt.Chart(parts).mark_bar().encode(
            y=alt.Y("driver:N", sort=None, title=None),
            x=alt.X("value:Q", title="Change in profit (₹)"),
            color=alt.Color("sign:N", scale=alt.Scale(domain=["gain", "cost"], range=["#0F766E", "#B91C1C"]),
                            legend=None),
            tooltip=["driver", alt.Tooltip("value:Q", format=",.0f")])
        st.subheader("Where the change comes from")
        st.altair_chart(ch, width="stretch")
        st.caption(f"Sum = {inr(r.delta_profit, signed=True)}. 'Shed' = expected loss removed when loss-making "
                   "small baskets leave; 'forgone' = profit lost when profitable small baskets leave.")
        st.dataframe(pd.DataFrame({
            "": ["Orders", "Loss-making orders", "GMV (order value)", "Profit"],
            "Today": [f"{r.orders:,.0f}", f"{r.base_loss_orders:,.0f}", inr(r.base_gmv), inr(r.base_profit)],
            "With policy": [f"{r.orders - r.orders_lost:,.0f}", f"{r.loss_orders:,.0f}", inr(r.gmv), inr(r.profit)],
        }), hide_index=True, width="stretch")

# ----------------------------------------------------------------------------- Segments
with tab_seg:
    if threshold == 0:
        st.info("Choose a threshold above ₹0 to compare segments.")
    else:
        view = st.radio("Group by", ["City", "Platform"], horizontal=True)
        col = "city" if view == "City" else "company"
        seg = _sim(dff, key, pd_, [col])
        be_t = _betable(dff, key, col, margin)[[col, "break_even_basket", "avg_km"]]
        seg = seg.merge(be_t, on=col)
        seg = seg.sort_values("delta_profit", ascending=False)
        ch = alt.Chart(seg).mark_bar(color="#0F766E").encode(
            y=alt.Y(f"{col}:N", sort="-x", title=None),
            x=alt.X("delta_profit:Q", title="Change in profit (₹)"),
            tooltip=[col, alt.Tooltip("delta_profit:Q", format=",.0f"), alt.Tooltip("delta_pct:Q", format=".1f")])
        st.altair_chart(ch, width="stretch")
        st.dataframe(
            seg[[col, "orders", "base_loss_pct", "loss_pct", "delta_profit", "delta_pct", "orders_lost",
                 "avg_km", "break_even_basket"]],
            hide_index=True, width="stretch",
            column_config={
                col: view, "orders": st.column_config.NumberColumn("Orders", format="%d"),
                "base_loss_pct": st.column_config.NumberColumn("Loss % today", format="%.1f"),
                "loss_pct": st.column_config.NumberColumn("Loss % after", format="%.1f"),
                "delta_profit": st.column_config.NumberColumn("Δ profit (₹)", format="%.0f"),
                "delta_pct": st.column_config.NumberColumn("Δ profit %", format="%.1f"),
                "orders_lost": st.column_config.NumberColumn("Orders lost", format="%.0f"),
                "avg_km": st.column_config.NumberColumn("Avg km", format="%.1f"),
                "break_even_basket": st.column_config.NumberColumn("Break-even basket (₹)", format="%.0f"),
            })
        if view == "City" and len(companies) > 1 and len(cities) > 1:
            st.subheader("City × platform: change in profit %")
            hm = _sim(dff, key, pd_, ["city", "company"])
            st.altair_chart(alt.Chart(hm).mark_rect().encode(
                x=alt.X("company:N", title=None), y=alt.Y("city:N", title=None),
                color=alt.Color("delta_pct:Q", title="Δ profit %", scale=alt.Scale(scheme="tealblues")),
                tooltip=["city", "company", alt.Tooltip("delta_pct:Q", format=".1f"),
                         alt.Tooltip("delta_profit:Q", format=",.0f")]), width="stretch")

# ----------------------------------------------------------------------------- Sweep
with tab_sweep:
    ths = tuple(range(0, 501, 25))
    sw = _sweep(dff, key, pd_, ths)
    best = sw.loc[sw.delta_profit.idxmax()]
    st.subheader("Profit change vs threshold")
    st.caption(f"Holding your other settings fixed. Highest expected profit in this range: "
               f"**{inr(best.threshold)}** ({inr(best.delta_profit, signed=True)}).")
    base = alt.Chart(sw).encode(x=alt.X("threshold:Q", title="Threshold (₹)"))
    line = base.mark_line(point=True, color="#0F766E").encode(
        y=alt.Y("delta_profit:Q", title="Change in profit (₹)"),
        tooltip=["threshold", alt.Tooltip("delta_profit:Q", format=",.0f"),
                 alt.Tooltip("loss_pct:Q", format=".2f"), alt.Tooltip("orders_lost:Q", format=",.0f")])
    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="#999", strokeDash=[4, 4]).encode(y="y:Q")
    here = alt.Chart(pd.DataFrame({"x": [threshold]})).mark_rule(color="#B91C1C").encode(x="x:Q")
    st.altair_chart(line + zero + here, width="stretch")

    st.subheader("How sensitive is that to customer behaviour?")
    g_th, g_top = tuple(range(50, 401, 50)), (0.1, 0.3, 0.5, 0.7, 0.9)
    grid = _grid(dff, key, pd_, g_th, g_top)
    grid["label"] = (grid.delta_profit / 1e5).round(1).astype(str) + "L"
    hb = alt.Chart(grid).encode(x=alt.X("threshold:O", title="Threshold (₹)"),
                                y=alt.Y("topup:O", title="Top-up rate", sort="descending"))
    st.altair_chart(hb.mark_rect().encode(
        color=alt.Color("delta_profit:Q", title="Δ profit",
                        scale=alt.Scale(scheme="redyellowgreen", domainMid=0))) +
        hb.mark_text(fontSize=11).encode(text="label:N"), width="stretch")
    st.caption("Red cells lose money versus doing nothing. If your preferred threshold turns red at plausible "
               "top-up rates, that's the argument for testing before rolling out.")

# ----------------------------------------------------------------------------- Break-even
with tab_be:
    fit = _cost_fit(dff, key)
    if fit["r2"] > 0.999:
        st.success(f"In this table delivery cost is exactly **₹{fit['intercept']:.0f} + ₹{fit['per_km']:.1f} × km** "
                   f"(R² = {fit['r2']:.4f}). It is a formula, so distance alone sets the bar a basket must clear.")
    else:
        st.info(f"Delivery cost ≈ ₹{fit['intercept']:.0f} + ₹{fit['per_km']:.1f} × km (R² = {fit['r2']:.3f}).")
    disc_rate = dff.discount_amt.sum() / dff.order_value.sum()
    kms = np.arange(0.5, 15.01, 0.5)
    curve = pd.DataFrame({"km": kms,
                          "break_even": (fit["intercept"] + fit["per_km"] * kms) / max(margin - disc_rate, 0.01)})
    st.subheader("Smallest basket that doesn't lose money, by trip distance")
    st.altair_chart(alt.Chart(curve).mark_line(color="#0F766E").encode(
        x=alt.X("km:Q", title="Distance (km)"), y=alt.Y("break_even:Q", title="Break-even basket (₹)"),
        tooltip=["km", alt.Tooltip("break_even:Q", format=".0f")]), width="stretch")
    st.caption(f"Uses average discount rate {disc_rate:.1%} of order value and contribution {margin:.0%}. "
               "A distance-tiered fee is the same idea: charge more where the bar is higher.")
    bt = _betable(dff, key, "city", margin).sort_values("base_loss_pct", ascending=False)
    st.dataframe(bt, hide_index=True, width="stretch", column_config={
        "city": "City", "orders": st.column_config.NumberColumn("Orders", format="%d"),
        "avg_order_value": st.column_config.NumberColumn("Avg basket (₹)", format="%.0f"),
        "avg_km": st.column_config.NumberColumn("Avg km", format="%.1f"),
        "avg_cost": st.column_config.NumberColumn("Avg delivery cost (₹)", format="%.0f"),
        "break_even_basket": st.column_config.NumberColumn("Break-even basket (₹)", format="%.0f"),
        "base_loss_pct": st.column_config.NumberColumn("Loss % today", format="%.1f")})

# ----------------------------------------------------------------------------- Experiment
with tab_exp:
    st.subheader("How I would test this before rolling it out")
    st.markdown(
        "The sliders in *Customer response* are guesses. The order table has no sessions, carts or timestamps, "
        "so it **cannot** tell us how many small-basket customers top up versus leave. A randomised test can. "
        "This tab sizes that test - it contains **no results**, only a design.")
    t_exp = float(threshold or 150)
    small = dff[dff.order_value < t_exp]
    prof = margin * small.order_value - small.delivery_cost - small.discount_amt
    if len(small) < 2:
        st.warning("No small baskets at this threshold - raise it.")
    else:
        mu_o, sd_o = float(prof.mean()), float(prof.std())
        a1, a2, a3 = st.columns(3)
        alpha = a1.select_slider("Significance level (α)", [0.01, 0.05, 0.10], value=0.05)
        power = a2.select_slider("Power", [0.7, 0.8, 0.9], value=0.8)
        deff = a3.number_input("Design effect (1 = user-level randomisation)", 1.0, 5.0, 1.0, 0.1)
        b1, b2, b3 = st.columns(3)
        conv = b1.slider("Cart→order conversion, eligible carts (assumed)", 0.1, 1.0, 0.6, 0.05,
                         help="Not in the dataset - replace with your own funnel number.")
        per_day = b2.number_input("Eligible carts / day (assumed)", 1_000, 5_000_000, 20_000, 1_000,
                                  help="Carts below the threshold, across the test population.")
        pred = (r.delta_profit / r.small_baskets) if r.small_baskets else 0.0
        mde = b3.number_input("Smallest effect worth detecting (₹ per eligible cart)", 0.5, 500.0,
                              float(max(1.0, round(abs(pred) * 0.5, 1))), 0.5,
                              help="Default: half of what the model above predicts.")
        mean_c, sd_c = ab.session_profit_sigma(sd_o, mu_o, conv)
        n_prim = ab.n_per_arm_mean(sd_c, mde, alpha, power, deff=deff)
        gm = st.slider("Guardrail: largest acceptable drop in cart→order conversion (pts)", 0.5, 10.0, 3.0, 0.5)
        n_guard = ab.n_per_arm_prop(conv, -gm / 100, alpha, power, two_sided=False, deff=deff)
        n_arm = max(n_prim, n_guard)
        days = ab.duration_days(n_arm, per_day)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Per arm (primary metric)", f"{n_prim:,}")
        k2.metric("Per arm (conversion guardrail)", f"{n_guard:,}")
        k3.metric("Total eligible carts", f"{2 * n_arm:,}")
        k4.metric("Run for", f"{days} days")
        st.caption(f"Primary-metric σ is estimated from this table's small baskets (mean ₹{mu_o:.1f}, SD ₹{sd_o:.1f}), "
                   f"then adjusted for {conv:.0%} conversion: per-cart mean ₹{mean_c:.1f}, SD ₹{sd_c:.1f}. "
                   "Duration is rounded up to whole weeks to cover weekday/weekend cycles.")

    st.markdown(f"""
| | |
|---|---|
| **Hypothesis** | A ₹{t_exp:.0f} minimum basket raises contribution profit per eligible cart without cutting conversion by more than the guardrail. |
| **Unit & assignment** | Customer, sticky random assignment (hash of user id), stratified by city. If spill-over between neighbours is a concern, randomise by dark store and inflate the design effect. |
| **Arms** | Control: no minimum. Treatment: minimum ₹{t_exp:.0f}. Optional third arm: small-order fee, to compare levers head-to-head. |
| **Primary metric** | Contribution profit per eligible cart (₹) - abandoned carts count as ₹0, so lost orders are priced in. |
| **Guardrails** | Cart→order conversion (non-inferiority), 28-day repeat-order rate, delivery-partner and customer rating. |
| **Decision rule** | Ship if the 95% CI on the primary metric excludes 0 on the upside **and** no guardrail breaches its margin. Analysis fixed in advance; no peeking (or use a sequential design with α-spending). |
| **Duration** | Whole weeks; never stop early on a good-looking day. |
| **Needs instrumenting** | cart created → threshold shown → item added → checkout → order, with timestamp, city, dark store. |
""")
    st.caption("Once the test reads out, its top-up and abandon rates replace the sliders 1-for-1 and this tool "
               "re-computes the city/platform impact from real behaviour.")

# ----------------------------------------------------------------------------- Method
with tab_method:
    st.markdown(f"""
### Model
For every order: `profit = margin × order_value − delivery_cost − discount`. With margin 100% this equals the
dataset's `Profit`. Orders with `order_value < threshold` are **small baskets**. Each small basket, in expectation:

* **tops up** (share *a*) → basket becomes the threshold; delivery cost is unchanged; discount scales with basket
* **abandons** (share *b*) → order and its profit disappear
* **pays the fee** (share 1−a−b, fee mode only) → order unchanged, plus `flat + per_km × km`

Minimum-order-value mode is a hard block: *b* = 1 − *a*. Everything is an expected value - no random draws -
so results are deterministic and the same on every run. Unit tests check the arithmetic, the decomposition and the
break-even formula (`tests/test_model.py`).

**Break-even.** In MOV mode the policy pays off when the top-up share exceeds Σ(profit of small baskets today) ÷
Σ(profit of those baskets after topping up); the app shows the mirror image as the maximum tolerable abandon rate.

### Caveats worth reading
* **Delivery cost is modelled.** The source Kaggle table has no cost fields; `Delivery_Cost`, `Discount_Amt` and
  `Profit` were derived. Cost is a straight line in distance, so *distance sets the bar and basket size decides
  whether it's cleared*. Use slider 3 (cost) to stress-test it.
* **"Profit" is before product cost.** At 100% contribution, any basket above roughly the trip cost is profitable.
  Real quick-commerce contribution margins are much lower, which would make far more orders loss-making.
* **Customer response is assumed**, not estimated. That's what the experiment is for.
* **Static.** No repeat-purchase, competitor, basket-mix or long-term retention effects.
* **The dataset looks simulated** (near-perfectly balanced platforms, cities and categories; a deterministic cost
  formula). Treat platform/city rankings as a demonstration of method, not as facts about real companies.
* Data source now: **{source}**.
""")
