"""Data access for the app: BigQuery -> local parquet -> synthetic demo (in that order).

The source actually used is always returned so the UI can show it; a failure in a
configured source is surfaced as a warning rather than silently hidden.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from .demo_data import make_demo_orders

COLUMNS = ["order_id", "company", "city", "product_category", "order_value", "distance_km",
           "delivery_time_min", "discount_applied", "delivery_cost", "discount_amt", "profit"]
LOCAL = Path(__file__).resolve().parent.parent / "data" / "orders.parquet"


def _secrets_get(key):
    try:
        return st.secrets[key]
    except Exception:
        return None


def _from_bigquery() -> pd.DataFrame:
    from google.cloud import bigquery
    from google.oauth2 import service_account

    cfg, sa = _secrets_get("bigquery"), _secrets_get("gcp_service_account")
    creds = service_account.Credentials.from_service_account_info(dict(sa))
    client = bigquery.Client(credentials=creds, project=cfg["project"])
    table = f"`{cfg['project']}.{cfg['dataset']}.{cfg.get('table', 'orders')}`"
    return client.query(f"SELECT {', '.join(COLUMNS)} FROM {table}").to_dataframe()


@st.cache_data(ttl=3600, show_spinner="Loading orders...")
def load_orders() -> tuple[pd.DataFrame, str, str | None]:
    """Returns (dataframe, source_label, warning_or_None)."""
    warning = None
    if _secrets_get("bigquery") and _secrets_get("gcp_service_account"):
        try:
            return _from_bigquery(), "BigQuery", None
        except Exception as e:  # noqa: BLE001 - show any failure, then fall back
            warning = f"BigQuery is configured but the query failed ({type(e).__name__}: {e}). Falling back."
    if LOCAL.exists():
        return pd.read_parquet(LOCAL, columns=COLUMNS), "Local parquet", warning
    return make_demo_orders(200_000)[COLUMNS], "Synthetic demo", warning
