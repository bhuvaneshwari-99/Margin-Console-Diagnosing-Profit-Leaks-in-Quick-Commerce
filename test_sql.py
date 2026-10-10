"""Executes every statement in sql/quick_comm_postgres.sql (DuckDB shares the dialect features used)
and cross-checks the SQL what-if against the Python engine."""
import re
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from margin_console.demo_data import make_demo_orders
from margin_console.model import Policy, simulate

SQL = (Path(__file__).resolve().parent.parent / "sql" / "quick_comm_postgres.sql").read_text()


@pytest.fixture(scope="module")
def con_df():
    d = make_demo_orders(40_000, seed=5)
    d["age_bucket"] = pd.cut(d.customer_age, [0, 24, 34, 44, 54, 99],
                             labels=["Under 25", "25-34", "35-44", "45-54", "55+"]).astype(str)
    d["delivery_time_bucket"] = pd.cut(d.delivery_time_min, [0, 15, 30, 45],
                                       labels=["0-15 Mins", "16-30 Mins", "31-45 Mins"]).astype(str)
    d["distance_bucket"] = pd.cut(d.distance_km, [0, 2, 5, 8, 99],
                                  labels=["0-2 KM", "2-5 KM", "5-8 KM", "8+ KM"]).astype(str)
    d["loss_driver"] = np.where(d.order_value < 300, "Low Value Order", "Normal")
    con = duckdb.connect()
    con.register("quick_comm", d)
    return con, d


def statements():
    body = re.sub(r"--[^\n]*", "", SQL)
    for s in body.split(";"):
        s = s.strip()
        if s and not s.upper().startswith("CREATE TABLE"):
            yield s


def test_every_statement_executes(con_df):
    con, _ = con_df
    n = 0
    for s in statements():
        con.execute(s).fetchall()
        n += 1
    assert n >= 25


def test_sanity_checks_are_clean(con_df):
    con, d = con_df
    first = next(s for s in statements() if "duplicate_ids" in s)
    row = con.execute(first).fetchone()
    assert row[0] == len(d) and row[1:] == (0, 0, 0, 0)


def test_sql_whatif_matches_python_engine(con_df):
    con, d = con_df
    s = next(x for x in statements() if "profit_with_policy" in x)
    today, with_policy, delta, lost, small = con.execute(s).fetchone()
    r = simulate(d, Policy(mode="mov", threshold=150, topup_rate=0.4, margin=1.0)).iloc[0]
    assert float(delta) == pytest.approx(r.delta_profit, abs=1)
    assert float(today) == pytest.approx(r.base_profit, abs=1)
    assert float(lost) == pytest.approx(r.orders_lost, abs=1)
    assert small == r.small_baskets


def test_cost_model_query_recovers_formula(con_df):
    con, _ = con_df
    s = next(x for x in statements() if "regr_intercept" in x)
    intercept, slope, corr = con.execute(s).fetchone()
    assert float(intercept) == pytest.approx(29, abs=1e-3) and float(slope) == pytest.approx(8, abs=1e-3)
    assert float(corr) == pytest.approx(1.0, abs=1e-6)
