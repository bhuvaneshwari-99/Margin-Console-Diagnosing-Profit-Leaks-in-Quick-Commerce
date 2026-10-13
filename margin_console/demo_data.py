"""Synthetic stand-in data with the SAME schema as the cleaned Kaggle table.

Used only (a) by the test-suite and (b) as the app's last-resort fallback so the
UI always opens. It is NOT the real dataset, and the app says so in a banner.
Structural facts mirrored from the real data: Delivery_Cost = 29 + 8 * km,
Profit = Order_Value - Delivery_Cost - Discount_Amt.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

COMPANIES = ["Amazon Now", "Big Basket", "Blinkit", "Dunzo", "Flipkart Minutes",
             "Jio Mart", "Swiggy Instamart", "Zepto"]
CITIES = ["Amritsar", "Bengaluru", "Chennai", "Delhi", "Gurgaon", "Haridwar",
          "Hyderabad", "Jaipur", "Kolkata", "Mumbai", "Noida", "Pune"]
CATEGORIES = ["Beverages", "Dairy", "Fruits & Vegetables", "Groceries",
              "Household", "Personal Care", "Snacks"]
PAYMENTS = ["Cash on Delivery", "Credit Card", "Debit Card", "UPI", "Wallet"]

COST_INTERCEPT, COST_PER_KM = 29.0, 8.0


def make_demo_orders(n: int = 200_000, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    company = rng.choice(COMPANIES, n)
    city = rng.choice(CITIES, n)
    km = np.round(rng.uniform(0.5, 15.0, n), 1)
    disc = rng.random(n) < 0.40

    city_shift = {c: s for c, s in zip(CITIES, rng.normal(0, 60, len(CITIES)))}
    base = rng.gamma(2.2, 210, n) + np.vectorize(city_shift.get)(city)
    order_value = np.clip(np.round(base * np.where(disc, 1.45, 1.0)), 50, 2500)

    delivery_cost = np.round(COST_INTERCEPT + COST_PER_KM * km, 1)
    discount_amt = np.where(disc, np.round(order_value * 0.10, 1), 0.0)
    profit = np.round(order_value - delivery_cost - discount_amt, 1)
    minutes = np.clip(np.round(5 + km * 1.1 + rng.normal(0, 3, n)), 5, 40).astype(int)

    return pd.DataFrame({
        "order_id": np.arange(1_000_001, 1_000_001 + n),
        "company": company, "city": city,
        "product_category": rng.choice(CATEGORIES, n),
        "payment_method": rng.choice(PAYMENTS, n),
        "customer_age": rng.integers(18, 60, n),
        "order_value": order_value, "distance_km": km,
        "delivery_time_min": minutes,
        "items_count": rng.integers(1, 20, n),
        "customer_rating": rng.integers(1, 6, n).astype(float),
        "discount_applied": disc.astype(int),
        "delivery_partner_rating": rng.integers(2, 6, n).astype(float),
        "delivery_cost": delivery_cost, "discount_amt": discount_amt,
        "profit": profit, "in_loss": (profit < 0).astype(int),
    })
