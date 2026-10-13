"""Sample-size / duration maths for the minimum-order-value experiment (no results, only design)."""
from __future__ import annotations

import math

from scipy.stats import norm


def _z(alpha: float, power: float, two_sided: bool = True) -> tuple[float, float]:
    return norm.ppf(1 - alpha / (2 if two_sided else 1)), norm.ppf(power)


def n_per_arm_mean(sigma: float, mde: float, alpha=0.05, power=0.8, two_sided=True, deff=1.0) -> int:
    """Two-sample comparison of means. mde is an ABSOLUTE difference (same unit as sigma)."""
    za, zb = _z(alpha, power, two_sided)
    return math.ceil(deff * 2 * ((za + zb) * sigma / mde) ** 2)


def n_per_arm_prop(p0: float, mde: float, alpha=0.05, power=0.8, two_sided=True, deff=1.0) -> int:
    """Two-proportion test. mde is an ABSOLUTE change in the proportion (e.g. -0.02)."""
    p1, za_zb = p0 + mde, _z(alpha, power, two_sided)
    za, zb = za_zb
    pbar = (p0 + p1) / 2
    num = (za * math.sqrt(2 * pbar * (1 - pbar)) + zb * math.sqrt(p0 * (1 - p0) + p1 * (1 - p1))) ** 2
    return math.ceil(deff * num / (mde ** 2))


def session_profit_sigma(sigma_order: float, mu_order: float, conversion: float) -> tuple[float, float]:
    """Mean and SD of profit PER ELIGIBLE CART when a share `conversion` become orders
    (non-converters contribute 0):  Var = c(s^2 + mu^2) - (c*mu)^2."""
    mean = conversion * mu_order
    var = conversion * (sigma_order ** 2 + mu_order ** 2) - mean ** 2
    return mean, math.sqrt(max(var, 0.0))


def duration_days(n_per_arm: int, eligible_carts_per_day: float, arms: int = 2,
                  min_days: int = 14) -> int:
    """Days to reach n in every arm, rounded UP to whole weeks (weekday/weekend cycles)."""
    raw = math.ceil(n_per_arm * arms / max(eligible_carts_per_day, 1))
    return int(math.ceil(max(raw, min_days) / 7) * 7)
