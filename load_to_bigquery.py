"""Load data/orders_clean.parquet into BigQuery.

    gcloud auth application-default login          # or set GOOGLE_APPLICATION_CREDENTIALS
    python scripts/load_to_bigquery.py --project my-gcp-project --dataset margin_console

Use --dry-run to print the schema without touching GCP.
Note: BigQuery *sandbox* tables expire after 60 days by default; enable billing on the project
(the free tier still applies) or re-run this script to reload.
"""
from __future__ import annotations

import argparse

import pandas as pd


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=False)
    ap.add_argument("--dataset", default="margin_console")
    ap.add_argument("--table", default="orders")
    ap.add_argument("--file", default="data/orders_clean.parquet")
    ap.add_argument("--location", default="US")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    df = pd.read_parquet(a.file)
    print(f"{len(df):,} rows x {df.shape[1]} cols from {a.file}")
    print(df.dtypes.to_string())
    if a.dry_run:
        return
    if not a.project:
        raise SystemExit("--project is required unless --dry-run")

    from google.cloud import bigquery

    client = bigquery.Client(project=a.project, location=a.location)
    ds = bigquery.Dataset(f"{a.project}.{a.dataset}")
    ds.location = a.location
    client.create_dataset(ds, exists_ok=True)

    table_id = f"{a.project}.{a.dataset}.{a.table}"
    job = client.load_table_from_dataframe(
        df, table_id,
        job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE"))
    job.result()
    t = client.get_table(table_id)
    print(f"loaded {t.num_rows:,} rows into {table_id}")


if __name__ == "__main__":
    main()
