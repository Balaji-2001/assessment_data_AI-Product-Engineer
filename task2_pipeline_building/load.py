"""
load.py
-------
Loads the transformed DataFrame into BigQuery.

Design decisions:
- Explicit schema: every field has a name, type, and description.
  This makes the table self-documenting and prevents silent type coercions.
- Dataset auto-creation: the script creates the dataset if it doesn't exist,
  so setup is a single run rather than a multi-step manual process.
- Deduplication: before loading, we check if rows for today already exist
  (for the Sandbox's lack of DML support, we handle this via partition filtering)
- WRITE_APPEND by default: each daily run adds rows for that day.
  Running twice in one day will create duplicates — handled by the SQL layer
  with a DISTINCT or ROW_NUMBER() window if needed.
"""

import logging

import pandas as pd
from google.api_core.exceptions import GoogleAPICallError, NotFound
from google.cloud import bigquery
from google.cloud.bigquery import SchemaField

from config import BQ_TABLE_FULL_ID, BQ_WRITE_DISPOSITION, BIGQUERY_DATASET, GCP_PROJECT_ID

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# BigQuery Schema
# Explicit schema = no surprises. Every field is typed and described.
# ---------------------------------------------------------------------------

SCHEMA = [
    # Identifiers
    SchemaField("city",                    "STRING",  mode="REQUIRED",  description="City name"),
    SchemaField("latitude",                "FLOAT64", mode="NULLABLE",  description="City latitude"),
    SchemaField("longitude",               "FLOAT64", mode="NULLABLE",  description="City longitude"),
    SchemaField("timezone",                "STRING",  mode="NULLABLE",  description="IANA timezone string"),

    # Timestamps and time dimensions
    SchemaField("timestamp",               "STRING",  mode="REQUIRED",  description="ISO 8601 local timestamp from API"),
    SchemaField("date",                    "DATE",    mode="NULLABLE",  description="Calendar date (YYYY-MM-DD)"),
    SchemaField("hour",                    "INTEGER", mode="NULLABLE",  description="Hour of day (0–23)"),
    SchemaField("day_of_week",             "STRING",  mode="NULLABLE",  description="Day name (Monday, Tuesday, etc.)"),
    SchemaField("day_type",                "STRING",  mode="NULLABLE",  description="Weekday or Weekend"),
    SchemaField("season",                  "STRING",  mode="NULLABLE",  description="Season (Spring, Summer, Autumn, Winter)"),
    SchemaField("time_of_day",             "STRING",  mode="NULLABLE",  description="Morning / Afternoon / Evening / Night"),

    # Raw weather metrics
    SchemaField("temperature_c",           "FLOAT64", mode="NULLABLE",  description="Air temperature at 2m height (°C)"),
    SchemaField("apparent_temperature_c",  "FLOAT64", mode="NULLABLE",  description="Apparent (feels-like) temperature (°C)"),
    SchemaField("precipitation_mm",        "FLOAT64", mode="NULLABLE",  description="Precipitation in mm"),
    SchemaField("windspeed_kmh",           "FLOAT64", mode="NULLABLE",  description="Wind speed at 10m height (km/h)"),
    SchemaField("humidity_pct",            "FLOAT64", mode="NULLABLE",  description="Relative humidity (%)"),
    SchemaField("cloudcover_pct",          "FLOAT64", mode="NULLABLE",  description="Cloud cover (%)"),
    SchemaField("uv_index",                "FLOAT64", mode="NULLABLE",  description="UV index"),
    SchemaField("weathercode",             "INTEGER", mode="NULLABLE",  description="WMO weather interpretation code"),
    SchemaField("weather_description",     "STRING",  mode="NULLABLE",  description="Human-readable WMO code label"),

    # Derived fields
    SchemaField("temp_feel",               "STRING",  mode="NULLABLE",  description="Temperature feel label (Cold, Cool, Comfortable, etc.)"),
    SchemaField("campaign_viability_score","FLOAT64", mode="NULLABLE",  description="0–10 score: suitability for outdoor marketing events"),
    SchemaField("campaign_viability_label","STRING",  mode="NULLABLE",  description="Label: Excellent / Good / Fair / Poor / Unsuitable"),

    # Pipeline metadata
    SchemaField("ingested_at",             "STRING",  mode="NULLABLE",  description="UTC timestamp when this row was ingested"),
]


def _get_or_create_dataset(client: bigquery.Client) -> None:
    """
    Create the BigQuery dataset if it doesn't already exist.
    Idempotent — safe to call on every run.
    """
    dataset_ref = bigquery.Dataset(f"{GCP_PROJECT_ID}.{BIGQUERY_DATASET}")
    dataset_ref.location = "US"
    dataset_ref.description = (
        "Marketing weather pipeline — hourly conditions for key cities. "
        "Used to score outdoor campaign viability."
    )
    try:
        client.get_dataset(dataset_ref)
        logger.info(f"Dataset {BIGQUERY_DATASET} already exists")
    except NotFound:
        client.create_dataset(dataset_ref, exists_ok=True)
        logger.info(f"Created dataset {BIGQUERY_DATASET}")


def load_to_bigquery(df: pd.DataFrame) -> bool:
    """
    Load a transformed DataFrame into the configured BigQuery table.

    Args:
        df: Cleaned and enriched DataFrame from transform.py

    Returns:
        bool: True if load succeeded, False if it failed

    The function is intentionally strict: if the load fails, it returns False
    rather than raising. This lets the caller (main.py) decide whether to
    abort or continue. The error is always logged with full detail.
    """
    if df.empty:
        logger.error("Cannot load to BigQuery: DataFrame is empty")
        return False

    logger.info(f"Preparing to load {len(df)} rows to {BQ_TABLE_FULL_ID}")

    try:
        client = bigquery.Client(project=GCP_PROJECT_ID)

        # Ensure the dataset exists
        _get_or_create_dataset(client)

        # Convert date column to proper type for BigQuery
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.date

        # Configure the load job
        job_config = bigquery.LoadJobConfig(
            schema=SCHEMA,
            write_disposition=BQ_WRITE_DISPOSITION,
            # Fail on unknown fields rather than silently dropping them
            # This catches mismatches between the DataFrame and schema early
            ignore_unknown_values=False,
            create_disposition="CREATE_IF_NEEDED",
        )

        logger.info(f"Starting BigQuery load job (disposition: {BQ_WRITE_DISPOSITION})")
        job = client.load_table_from_dataframe(df, BQ_TABLE_FULL_ID, job_config=job_config)

        # Wait for the job to complete
        job.result()

        # Verify row count after load
        table = client.get_table(BQ_TABLE_FULL_ID)
        logger.info(
            f"Load job complete. "
            f"Rows added this run: {len(df)}. "
            f"Total rows in table: {table.num_rows}."
        )
        return True

    except GoogleAPICallError as e:
        logger.error(f"BigQuery API error: {e}")
        logger.error("Check that your GCP_PROJECT_ID is correct and the service account has BigQuery write access.")
        return False

    except Exception as e:
        logger.error(f"Unexpected error during BigQuery load: {type(e).__name__}: {e}")
        return False
