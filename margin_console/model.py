"""What-if engine: expected profit under a minimum-order-value / small-order-fee policy.

Everything is vectorised NumPy over the order table and deterministic (expected
values, no random sampling), so it is fast enough to re-run on every slider move.

Definitions (match the notebook / dataset):
    profit_i = margin * order_value_i - delivery_cost_i - discount_i
With margin = 1.0 this reproduces the dataset's `Profit` column exactly.

Behavioural model for an order with order_value < threshold T
    top-up  (share a): customer adds items until basket == T
    abandon (share b): order is lost (profit 0)
    pay     (share 1-a-b): order proceeds unchanged and pays a fee (fee mode only)
`mov` mode is a hard block: pay = 0 and b = 1 - a.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Policy:
    mode: str = "mov"            # "mov" (hard minimum) | "fee" (small-order fee)
    threshold: float = 0.0       # rupees; orders below this are "small baskets"
    fee_flat: float = 0.0        # fee mode: flat fee on small baskets
    fee_per_km: float = 0.0      # fee mode: distance-tiered add-on
    topup_rate: float = 0.4      # share of small baskets that top up to threshold
    abandon_rate: float = 0.25   # fee mode only: share that abandon
    margin: float = 1.0          # share of order value that is contribution (1.0 = dataset def.)

    def shares(self) -> tuple[float, float, float]:
        a = float(np.clip(self.topup_rate, 0, 1))
        if self.mode == "mov":
            return a, 1.0 - a, 0.0
        b = float(np.clip(self.abandon_rate, 0, 1 - a))
        return a, b, 1.0 - a - b


# --------------------------------------------------------------------------- core
def _arrays(df: pd.DataFrame, p: Policy) -> dict[str, np.ndarray]:
    ov = df["order_value"].to_numpy(float)
    km = df["distance_km"].to_numpy(float)
    cost = df["delivery_cost"].to_numpy(float)
    disc = df["discount_amt"].to_numpy(float)
    T, m = p.threshold, p.margin
    a, b, pay = p.shares()

    base = m * ov - cost - disc
    small = ov < T
    rate = np.divide(disc, ov, out=np.zeros_like(ov), where=ov > 0)
    topped = (m - rate) * T - cost                       # profit after top-up to T
    fee = (p.fee_flat + p.fee_per_km * km) if p.mode == "fee" else np.zeros_like(ov)

    profit = np.where(small, a * topped + pay * (base + fee), base)
    kept = np.where(small, a + pay, 1.0)
    gmv = np.where(small, a * T + pay * ov, ov)
    loss = np.where(small, a * (topped < 0) + pay * ((base + fee) < 0), base < 0)

    return dict(
        small=small.astype(float), base=base, profit=profit, kept=kept, gmv=gmv,
        loss=loss.astype(float), base_loss=(base < 0).astype(float), base_gmv=ov,
        fee_income=np.where(small, pay * fee, 0.0),
        d_topup=np.where(small, a * (topped - base), 0.0),
        d_fee=np.where(small, pay * fee, 0.0),
        d_loss_avoided=np.where(small, b * np.maximum(-base, 0), 0.0),
        d_forgone=np.where(small, -b * np.maximum(base, 0), 0.0),
    )


def group_codes(df: pd.DataFrame, by: list[str] | None):
    if not by:
        return np.zeros(len(df), dtype=np.int64), pd.DataFrame(index=[0]), 1
    codes = np.zeros(len(df), dtype=np.int64)
    uniques = []
    for col in by:
        c, u = pd.factorize(df[col], sort=True)
        codes = codes * len(u) + c
        uniques.append(u)
    sizes = [len(u) for u in uniques]
    labels = pd.MultiIndex.from_product(uniques, names=by).to_frame(index=False)
    return codes, labels, int(np.prod(sizes))


def simulate(df: pd.DataFrame, p: Policy, by: list[str] | None = None) -> pd.DataFrame:
    """Baseline vs scenario metrics, overall (by=None) or per group."""
    arr = _arrays(df, p)
    codes, labels, n = group_codes(df, by)

    def agg(x):
        return np.bincount(codes, weights=x, minlength=n)

    out = labels.copy()
    out["orders"] = np.bincount(codes, minlength=n)
    out["small_baskets"] = agg(arr["small"])
    out["base_profit"] = agg(arr["base"])
    out["profit"] = agg(arr["profit"])
    out["delta_profit"] = out["profit"] - out["base_profit"]
    out["base_loss_orders"] = agg(arr["base_loss"])
    out["loss_orders"] = agg(arr["loss"])
    out["orders_lost"] = out["orders"] - agg(arr["kept"])
    out["base_gmv"] = agg(arr["base_gmv"])
    out["gmv"] = agg(arr["gmv"])
    out["fee_income"] = agg(arr["fee_income"])
    for k in ("d_topup", "d_fee", "d_loss_avoided", "d_forgone"):
        out[k] = agg(arr[k])
    out = out[out["orders"] > 0].reset_index(drop=True)
    kept = out["orders"] - out["orders_lost"]
    out["base_loss_pct"] = 100 * out["base_loss_orders"] / out["orders"]
    out["loss_pct"] = 100 * out["loss_orders"] / kept.replace(0, np.nan)
    out["delta_pct"] = 100 * out["delta_profit"] / out["base_profit"].abs().replace(0, np.nan)
    return out


# ----------------------------------------------------------------- break-even maths
def breakeven_max_abandon(df: pd.DataFrame, p: Policy) -> float | None:
    """Largest share of small-basket customers who may abandon while the policy
    still does no worse than doing nothing. None => cannot break even at any rate.

    mov : Delta = a*sum(topped) - sum(base)           -> a* = sum(base)/sum(topped)
    fee : Delta = a*sum(topped-base-f) - b*sum(base+f) + sum(f)   (linear in b)
    """
    ar = _arrays(df, p)
    s = ar["small"] > 0
    if not s.any() or p.threshold <= 0:
        return None
    base = ar["base"][s]
    a, _, _ = p.shares()
    ov = df["order_value"].to_numpy(float)[s]
    cost = df["delivery_cost"].to_numpy(float)[s]
    disc = df["discount_amt"].to_numpy(float)[s]
    rate = np.divide(disc, ov, out=np.zeros_like(ov), where=ov > 0)
    topped = (p.margin - rate) * p.threshold - cost
    if p.mode == "mov":
        if base.sum() <= 0:
            return 1.0
        if topped.sum() <= 0:
            return None
        a_star = base.sum() / topped.sum()
        return None if a_star > 1 else float(1 - a_star)
    fee = p.fee_flat + p.fee_per_km * df["distance_km"].to_numpy(float)[s]
    denom = (base + fee).sum()
    numer = a * (topped - base - fee).sum() + fee.sum()
    if denom <= 0:
        return float(1 - a)
    b_star = numer / denom
    return float(np.clip(b_star, 0, 1 - a)) if b_star >= 0 else None


def sweep_threshold(df, p: Policy, thresholds) -> pd.DataFrame:
    """Delta-profit curve over thresholds. Only rows below max(threshold) can change,
    so we simulate that subset and add back the untouched baseline."""
    tmax = float(max(thresholds))
    sub = df[df["order_value"] < tmax]
    tot_loss = float(((df["order_value"] * p.margin - df["delivery_cost"] - df["discount_amt"]) < 0).sum())
    sub_base_loss = float(((sub["order_value"] * p.margin - sub["delivery_cost"] - sub["discount_amt"]) < 0).sum())
    rows = []
    for t in thresholds:
        r = simulate(sub, Policy(**{**p.__dict__, "threshold": float(t)})).iloc[0]
        loss_total = tot_loss - sub_base_loss + r.loss_orders
        kept_total = len(df) - r.orders_lost
        rows.append(dict(threshold=t, delta_profit=r.delta_profit,
                         loss_pct=100 * loss_total / kept_total, orders_lost=r.orders_lost))
    return pd.DataFrame(rows)


def sensitivity_grid(df, p: Policy, thresholds, topups) -> pd.DataFrame:
    sub = df[df["order_value"] < float(max(thresholds))]
    rows = []
    for t in thresholds:
        for a in topups:
            q = Policy(**{**p.__dict__, "threshold": float(t), "topup_rate": float(a)})
            rows.append(dict(threshold=t, topup=a, delta_profit=simulate(sub, q).iloc[0].delta_profit))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ cost structure
def fit_cost_model(df: pd.DataFrame) -> dict:
    """Least-squares Delivery_Cost ~ a + b*km. r2 ~ 1 means cost is a pure function of distance."""
    km, cost = df["distance_km"].to_numpy(float), df["delivery_cost"].to_numpy(float)
    slope, intercept = np.polyfit(km, cost, 1)
    r2 = float(np.corrcoef(km, cost)[0, 1] ** 2)
    return dict(intercept=float(intercept), per_km=float(slope), r2=r2)


def breakeven_table(df: pd.DataFrame, by: str, margin: float = 1.0) -> pd.DataFrame:
    """Break-even basket at each group's average trip: cost / (margin - discount rate)."""
    d = df.assign(_loss=(margin * df["order_value"] - df["delivery_cost"] - df["discount_amt"]) < 0)
    t = d.groupby(by, observed=True).agg(
        orders=("order_value", "size"), avg_order_value=("order_value", "mean"),
        avg_km=("distance_km", "mean"), avg_cost=("delivery_cost", "mean"),
        disc=("discount_amt", "sum"), gmv=("order_value", "sum"), loss_share=("_loss", "mean"))
    t["break_even_basket"] = t["avg_cost"] / (margin - t["disc"] / t["gmv"]).clip(lower=0.01)
    t["base_loss_pct"] = 100 * t["loss_share"]
    return t.drop(columns=["disc", "gmv", "loss_share"]).reset_index()
