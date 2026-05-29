import logging

import pandas as pd
from google.api_core.exceptions import GoogleAPICallError, NotFound
from google.cloud import bigquery
from google.cloud.bigquery import SchemaField

from config import (
    BQ_TABLE_FULL_ID,
    BQ_WRITE_DISPOSITION,
    BIGQUERY_DATASET,
    GCP_PROJECT_ID,
)

logger = logging.getLogger(__name__)

SCHEMA = [
    SchemaField("city",                     "STRING",  mode="REQUIRED"),
    SchemaField("latitude",                 "FLOAT64", mode="NULLABLE"),
    SchemaField("longitude",                "FLOAT64", mode="NULLABLE"),
    SchemaField("timezone",                 "STRING",  mode="NULLABLE"),
    SchemaField("timestamp",                "STRING",  mode="REQUIRED"),
    SchemaField("date",                     "DATE",    mode="NULLABLE"),
    SchemaField("hour",                     "INTEGER", mode="NULLABLE"),
    SchemaField("day_of_week",              "STRING",  mode="NULLABLE"),
    SchemaField("day_type",                 "STRING",  mode="NULLABLE"),
    SchemaField("season",                   "STRING",  mode="NULLABLE"),
    SchemaField("time_of_day",              "STRING",  mode="NULLABLE"),
    SchemaField("temperature_c",            "FLOAT64", mode="NULLABLE"),
    SchemaField("apparent_temperature_c",   "FLOAT64", mode="NULLABLE"),
    SchemaField("precipitation_mm",         "FLOAT64", mode="NULLABLE"),
    SchemaField("windspeed_kmh",            "FLOAT64", mode="NULLABLE"),
    SchemaField("humidity_pct",             "FLOAT64", mode="NULLABLE"),
    SchemaField("cloudcover_pct",           "FLOAT64", mode="NULLABLE"),
    SchemaField("uv_index",                 "FLOAT64", mode="NULLABLE"),
    SchemaField("weathercode",              "INTEGER", mode="NULLABLE"),
    SchemaField("weather_description",      "STRING",  mode="NULLABLE"),
    SchemaField("temp_feel",                "STRING",  mode="NULLABLE"),
    SchemaField("campaign_viability_score", "FLOAT64", mode="NULLABLE"),
    SchemaField("campaign_viability_label", "STRING",  mode="NULLABLE"),
    SchemaField("ingested_at",              "STRING",  mode="NULLABLE"),
]


def _get_or_create_dataset(client: bigquery.Client) -> None:
    dataset_ref             = bigquery.Dataset(f"{GCP_PROJECT_ID}.{BIGQUERY_DATASET}")
    dataset_ref.location    = "US"
    dataset_ref.description = "Marketing weather pipeline — hourly conditions for key cities."
    try:
        client.get_dataset(dataset_ref)
        logger.info(f"Dataset '{BIGQUERY_DATASET}' already exists")
    except NotFound:
        client.create_dataset(dataset_ref, exists_ok=True)
        logger.info(f"Created dataset '{BIGQUERY_DATASET}' ")


def load_to_bigquery(df: pd.DataFrame) -> bool:
    if df.empty:
        logger.error("DataFrame is empty — nothing to load")
        return False

    logger.info(f"Loading {len(df)} rows to {BQ_TABLE_FULL_ID}")

    try:
        client = bigquery.Client(project=GCP_PROJECT_ID)
        _get_or_create_dataset(client)

        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.date

        job_config = bigquery.LoadJobConfig(
            schema=SCHEMA,
            write_disposition=BQ_WRITE_DISPOSITION,
            ignore_unknown_values=False,
            create_disposition="CREATE_IF_NEEDED",
        )

        job = client.load_table_from_dataframe(df, BQ_TABLE_FULL_ID, job_config=job_config)
        job.result()

        table = client.get_table(BQ_TABLE_FULL_ID)
        logger.info(f"Load complete  | Rows this run: {len(df)} | Total in table: {table.num_rows}")
        return True

    except GoogleAPICallError as e:
        logger.error(f"BigQuery API error: {e}")
        return False

    except Exception as e:
        logger.error(f"Unexpected load error: {type(e).__name__}: {e}")
        return False
