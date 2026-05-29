"""
transform.py
------------
Cleans and enriches raw Open-Meteo API responses.

What this does:
1.  Flattens nested hourly JSON arrays into one row per hour
2.  Adds city name and metadata
3.  Handles nulls and type coercions cleanly
4.  Adds derived fields that provide analytical value beyond raw API data

The most important derived field is `campaign_viability_score` — a 0–10
score indicating how suitable outdoor conditions are for marketing events
or activations. This is the kind of thing a martech team could actually
use to plan campaign timing.
"""

import logging
from datetime import datetime
from typing import Any, Optional

import pandas as pd

from config import (
    IDEAL_TEMP_MAX,
    IDEAL_TEMP_MIN,
    RAIN_THRESHOLD,
    UV_HIGH_THRESHOLD,
    WIND_THRESHOLD,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WMO Weather Code Descriptions
# Open-Meteo uses WMO codes. Map the most common ones to human-readable labels.
# Full reference: https://open-meteo.com/en/docs#weathervariables
# ---------------------------------------------------------------------------

WMO_CODE_DESCRIPTIONS = {
    0:  "Clear sky",
    1:  "Mainly clear",
    2:  "Partly cloudy",
    3:  "Overcast",
    45: "Foggy",
    48: "Icy fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Slight showers",
    81: "Moderate showers",
    82: "Violent showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with heavy hail",
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Convert a value to float, returning default if null or unconvertible."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    """Convert a value to int, returning default if null or unconvertible."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_season(month: int, hemisphere: str = "north") -> str:
    """
    Return season name based on month and hemisphere.
    Used as a grouping dimension in downstream analysis.
    """
    if hemisphere == "north":
        if month in (12, 1, 2):
            return "Winter"
        elif month in (3, 4, 5):
            return "Spring"
        elif month in (6, 7, 8):
            return "Summer"
        else:
            return "Autumn"
    else:
        # Southern hemisphere: flip summer/winter
        if month in (12, 1, 2):
            return "Summer"
        elif month in (3, 4, 5):
            return "Autumn"
        elif month in (6, 7, 8):
            return "Winter"
        else:
            return "Spring"


def _campaign_viability_score(
    temp: float,
    apparent_temp: float,
    precipitation: float,
    windspeed: float,
    uv_index: float,
    weathercode: int,
) -> float:
    """
    Calculate a 0–10 campaign viability score for outdoor marketing events.

    This is the primary derived field. It answers the question:
    "How suitable are outdoor conditions for a marketing activation right now?"

    Scoring logic:
    - Start at 10 (perfect conditions)
    - Deduct for temperature outside the comfortable range
    - Deduct heavily for rain
    - Deduct for high wind
    - Deduct for extreme UV
    - Thunderstorm or heavy weather codes floor the score at 0

    This is intentionally simple and explainable. The team can tune thresholds
    in config.py once they understand their markets better.
    """
    score = 10.0

    # Temperature penalty — the further from ideal range, the bigger the hit
    if temp < IDEAL_TEMP_MIN:
        score -= min(4.0, (IDEAL_TEMP_MIN - temp) * 0.2)
    elif temp > IDEAL_TEMP_MAX:
        score -= min(4.0, (temp - IDEAL_TEMP_MAX) * 0.2)

    # Precipitation penalty
    if precipitation >= RAIN_THRESHOLD:
        score -= min(5.0, precipitation * 2.0)

    # Wind penalty
    if windspeed > WIND_THRESHOLD:
        score -= min(3.0, (windspeed - WIND_THRESHOLD) * 0.1)

    # High UV penalty (campaigns with outdoor staff need to consider this)
    if uv_index > UV_HIGH_THRESHOLD:
        score -= 1.0

    # Severe weather codes are immediate disqualifiers
    if weathercode in (95, 96, 99):  # Thunderstorm
        score = 0.0
    elif weathercode in (65, 75, 82):  # Heavy rain/snow/showers
        score = max(0.0, score - 4.0)

    return round(max(0.0, min(10.0, score)), 2)


def _classify_viability(score: float) -> str:
    """Human-readable label for the campaign viability score."""
    if score >= 8.0:
        return "Excellent"
    elif score >= 6.0:
        return "Good"
    elif score >= 4.0:
        return "Fair"
    elif score >= 2.0:
        return "Poor"
    else:
        return "Unsuitable"


def transform_location(location_config: dict, raw_data: dict) -> pd.DataFrame:
    """
    Transform raw API response for one location into a clean DataFrame.

    Each row represents one hour of weather data for one city.

    Args:
        location_config: The location dict from config.py (name, lat, lon, etc.)
        raw_data: Raw JSON response from Open-Meteo API

    Returns:
        pd.DataFrame with one row per hour, cleaned and enriched
    """
    city = location_config["name"]
    hourly = raw_data.get("hourly", {})

    # Validate that we have the time column — without it nothing works
    if "time" not in hourly:
        logger.error(f"No 'time' field in hourly data for {city}. Skipping.")
        return pd.DataFrame()

    times = hourly["time"]
    n = len(times)
    logger.info(f"Transforming {n} hourly records for {city}")

    # Build records list — one dict per hour
    records = []

    for i in range(n):
        try:
            timestamp_str = times[i]
            dt = datetime.fromisoformat(timestamp_str)

            # Raw fields — use safe getters to handle nulls
            temp              = _safe_float(hourly.get("temperature_2m",       [None]*n)[i])
            apparent_temp     = _safe_float(hourly.get("apparent_temperature",  [None]*n)[i])
            precipitation     = _safe_float(hourly.get("precipitation",         [None]*n)[i])
            windspeed         = _safe_float(hourly.get("windspeed_10m",         [None]*n)[i])
            weathercode       = _safe_int  (hourly.get("weathercode",           [None]*n)[i])
            humidity          = _safe_float(hourly.get("relativehumidity_2m",   [None]*n)[i])
            cloudcover        = _safe_float(hourly.get("cloudcover",            [None]*n)[i])
            uv_index          = _safe_float(hourly.get("uv_index",              [None]*n)[i])

            # Derived field 1: human-readable weather description
            weather_description = WMO_CODE_DESCRIPTIONS.get(weathercode, f"WMO code {weathercode}")

            # Derived field 2: season
            hemisphere = "south" if location_config["latitude"] < 0 else "north"
            season = _get_season(dt.month, hemisphere)

            # Derived field 3: day type (weekday vs. weekend — relevant for campaign planning)
            day_type = "Weekend" if dt.weekday() >= 5 else "Weekday"

            # Derived field 4: time of day bucket
            hour = dt.hour
            if 6 <= hour < 12:
                time_of_day = "Morning"
            elif 12 <= hour < 17:
                time_of_day = "Afternoon"
            elif 17 <= hour < 21:
                time_of_day = "Evening"
            else:
                time_of_day = "Night"

            # Derived field 5: campaign viability score (primary derived field)
            viability_score = _campaign_viability_score(
                temp, apparent_temp, precipitation, windspeed, uv_index, weathercode
            )

            # Derived field 6: viability label
            viability_label = _classify_viability(viability_score)

            # Derived field 7: temperature feel label
            if apparent_temp < 0:
                temp_feel = "Freezing"
            elif apparent_temp < 10:
                temp_feel = "Cold"
            elif apparent_temp < 18:
                temp_feel = "Cool"
            elif apparent_temp < 25:
                temp_feel = "Comfortable"
            elif apparent_temp < 32:
                temp_feel = "Warm"
            else:
                temp_feel = "Hot"

            records.append({
                # Identifiers
                "city":                   city,
                "latitude":               location_config["latitude"],
                "longitude":              location_config["longitude"],
                "timezone":               location_config["timezone"],
                # Timestamps
                "timestamp":              timestamp_str,
                "date":                   dt.strftime("%Y-%m-%d"),
                "hour":                   hour,
                "day_of_week":            dt.strftime("%A"),
                "day_type":               day_type,
                "season":                 season,
                "time_of_day":            time_of_day,
                # Raw weather metrics
                "temperature_c":          temp,
                "apparent_temperature_c": apparent_temp,
                "precipitation_mm":       precipitation,
                "windspeed_kmh":          windspeed,
                "humidity_pct":           humidity,
                "cloudcover_pct":         cloudcover,
                "uv_index":               uv_index,
                "weathercode":            weathercode,
                "weather_description":    weather_description,
                # Derived fields
                "temp_feel":              temp_feel,
                "campaign_viability_score": viability_score,
                "campaign_viability_label": viability_label,
                # Pipeline metadata
                "ingested_at":            datetime.utcnow().isoformat(),
            })

        except Exception as e:
            logger.warning(f"Skipping row {i} for {city} due to error: {e}")
            continue

    df = pd.DataFrame(records)
    logger.info(f"Transformation complete for {city}: {len(df)} rows, {len(df.columns)} columns")
    return df


def transform_all(fetched_results: list[dict]) -> pd.DataFrame:
    """
    Transform all fetched location results into a single combined DataFrame.

    Args:
        fetched_results: Output from fetch.fetch_all_locations()

    Returns:
        pd.DataFrame with all locations combined, ready for BigQuery load
    """
    all_frames = []

    for result in fetched_results:
        df = transform_location(result["location"], result["data"])
        if not df.empty:
            all_frames.append(df)

    if not all_frames:
        logger.error("No data to transform — all locations failed or returned empty results")
        return pd.DataFrame()

    combined = pd.concat(all_frames, ignore_index=True)
    logger.info(
        f"Combined dataset: {len(combined)} rows across {combined['city'].nunique()} cities"
    )
    return combined
