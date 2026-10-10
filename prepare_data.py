"""Clean the enriched CSV (quick_comm2.csv) and write the two parquet files the project uses.

    python scripts/prepare_data.py path/to/quick_comm2.csv

Outputs
    data/orders_clean.parquet  all cleaned columns, snake_case  -> load into BigQuery
    data/orders_clean.csv      same, for PostgreSQL \\copy (sql/quick_comm_postgres.sql)
    data/orders.parquet        slim table the Streamlit app reads (fallback when BigQuery is off)

Fails loudly (non-zero exit) if the data breaks any invariant the analysis relies on.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

CITY_FIX = {"Bengluru": "Bengaluru"}          # spelling in the source file
RENAME = {"Distance_time_bucket": "Delivery_Time_Bucket"}   # it is a *time* bucket
SLIM = ["order_id", "company", "city", "product_category", "order_value", "distance_km",
        "delivery_time_min", "discount_applied", "delivery_cost", "discount_amt", "profit"]
REQUIRED = ["Order_ID", "Company", "City", "Order_Value", "Distance_Km", "Delivery_Time_Min",
            "Delivery_Cost", "Discount_Amt", "Discount_Applied", "Profit", "In_Loss", "Product_Category"]


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.loc[:, ~raw.columns.str.contains(r"^Unnamed")].copy()
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        sys.exit(f"Missing columns {missing}. This script expects the enriched file "
                 "(with Delivery_Cost, Discount_Amt, Profit, In_Loss), not the raw Kaggle CSV.")
    df = df.rename(columns=RENAME)
    df["City"] = df["City"].str.strip().str.title().replace(CITY_FIX)
    df["Company"] = df["Company"].str.strip()
    df = df.astype({"Order_ID": "int64", "Customer_Age": "int64"}, errors="ignore")
    df.columns = [c.lower() for c in df.columns]
    return df


def validate(df: pd.DataFrame) -> list[str]:
    problems = []
    if df["order_id"].duplicated().any():
        problems.append("duplicate order_id")
    for col in ["order_value", "distance_km", "delivery_time_min", "delivery_cost"]:
        if (df[col] <= 0).any():
            problems.append(f"{col} has non-positive values")
    if (df["discount_amt"] < 0).any():
        problems.append("negative discount_amt")
    err = (df["order_value"] - df["delivery_cost"] - df["discount_amt"] - df["profit"]).abs().max()
    if err > 0.11:
        problems.append(f"profit != order_value - delivery_cost - discount_amt (max err {err:.3f})")
    if ((df["profit"] < 0).astype(int) != df["in_loss"]).any():
        problems.append("in_loss disagrees with profit < 0")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--out", default="data")
    a = ap.parse_args()

    df = clean(pd.read_csv(a.csv))
    problems = validate(df)
    slope, intercept = np.polyfit(df["distance_km"], df["delivery_cost"], 1)
    rate = (df.loc[df.discount_applied == 1, "discount_amt"] / df.loc[df.discount_applied == 1, "order_value"])

    print(f"rows: {len(df):,}   loss-making: {100 * df.in_loss.mean():.2f}%")
    print(f"delivery_cost ~ {intercept:.2f} + {slope:.2f} * km   (a modelled cost, not observed)")
    print("discount as % of order value on discounted orders:")
    print(rate.describe(percentiles=[.05, .5, .95]).round(4).to_string())
    if rate.std() > 0.02:
        print("  ! discount rate is not constant -> document the rule that produced Discount_Amt")

    if problems:
        sys.exit("VALIDATION FAILED: " + "; ".join(problems))

    out = Path(a.out)
    out.mkdir(exist_ok=True)
    df.to_parquet(out / "orders_clean.parquet", index=False)
    df.to_csv(out / "orders_clean.csv", index=False)          # for Postgres \\copy
    df[SLIM].to_parquet(out / "orders.parquet", index=False)
    print(f"wrote {out/'orders_clean.parquet'} and {out/'orders.parquet'}")


if __name__ == "__main__":
    main()
