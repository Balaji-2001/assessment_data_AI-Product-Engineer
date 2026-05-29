"""
config.py
---------
Central configuration for the weather pipeline.
All parameters live here — nothing is hardcoded in the pipeline logic.
Change values here without touching any other file.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# API Settings — Open-Meteo (no API key required)
# ---------------------------------------------------------------------------

API_BASE_URL = "https://api.open-meteo.com/v1/forecast"

# The cities we want to track. Extend this list to add more locations.
# Format: { "name": str, "latitude": float, "longitude": float, "timezone": str }
LOCATIONS = [
    {"name": "London",    "latitude": 51.5074,  "longitude": -0.1278,  "timezone": "Europe/London"},
    {"name": "Manchester","latitude": 53.4808,  "longitude": -2.2426,  "timezone": "Europe/London"},
    {"name": "Mumbai",    "latitude": 19.0760,  "longitude": 72.8777,  "timezone": "Asia/Kolkata"},
    {"name": "Delhi",     "latitude": 28.6139,  "longitude": 77.2090,  "timezone": "Asia/Kolkata"},
    {"name": "New York",  "latitude": 40.7128,  "longitude": -74.0060, "timezone": "America/New_York"},
]

# Which hourly fields to pull from the API
HOURLY_VARIABLES = [
    "temperature_2m",
    "apparent_temperature",
    "precipitation",
    "windspeed_10m",
    "weathercode",
    "relativehumidity_2m",
    "cloudcover",
    "uv_index",
]

# How many past days of data to fetch per run
PAST_DAYS = 1

# Timeout for API requests in seconds
REQUEST_TIMEOUT_SECONDS = 30

# How many times to retry a failed API request before giving up
MAX_RETRIES = 3

# Seconds to wait between retries
RETRY_BACKOFF_SECONDS = 5

# ---------------------------------------------------------------------------
# BigQuery Settings
# ---------------------------------------------------------------------------

GCP_PROJECT_ID      = os.getenv("GCP_PROJECT_ID", "your-project-id")
BIGQUERY_DATASET    = os.getenv("BIGQUERY_DATASET", "marketing_weather")
BIGQUERY_TABLE      = os.getenv("BIGQUERY_TABLE", "hourly_conditions")

# Full table reference: project.dataset.table
BQ_TABLE_FULL_ID = f"{GCP_PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}"

# Write mode: "WRITE_APPEND" adds rows, "WRITE_TRUNCATE" replaces the table each run
# For daily incremental loads, WRITE_APPEND is correct
BQ_WRITE_DISPOSITION = "WRITE_APPEND"

# ---------------------------------------------------------------------------
# Derived Field Thresholds
# ---------------------------------------------------------------------------

# Campaign Viability Score: a simple 0–10 score for outdoor marketing suitability
# based on temperature, precipitation, and windspeed.
# These thresholds can be tuned once the team knows their markets.

IDEAL_TEMP_MIN = 15.0    # °C  — below this starts getting uncomfortable
IDEAL_TEMP_MAX = 28.0    # °C  — above this starts getting uncomfortable
RAIN_THRESHOLD = 1.0     # mm  — above this is "rainy" and drops score
WIND_THRESHOLD = 30.0    # km/h — above this is "windy" and drops score
UV_HIGH_THRESHOLD = 6    # UV index above this = sunburn risk

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
