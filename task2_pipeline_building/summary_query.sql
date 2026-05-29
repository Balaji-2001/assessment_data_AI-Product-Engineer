-- summary.sql
-- -----------
-- Extracts a meaningful daily summary from the marketing_weather.hourly_conditions table.
-- Run this in BigQuery after the pipeline has loaded at least one day of data.
--
-- What this shows:
--   For each city and date, the daily average conditions plus the
--   number of "good" hours (campaign viability score >= 6.0).
--   This is the kind of summary a campaign planner would actually use
--   to decide whether to run an outdoor activation on a given day.


-- ============================================================
-- Query 1: Daily Campaign Viability Summary by City
-- ============================================================

SELECT
    city,
    date,
    season,

    -- Temperature summary
    ROUND(AVG(temperature_c), 1)           AS avg_temp_c,
    ROUND(MIN(temperature_c), 1)           AS min_temp_c,
    ROUND(MAX(temperature_c), 1)           AS max_temp_c,

    -- Conditions
    ROUND(SUM(precipitation_mm), 2)        AS total_precipitation_mm,
    ROUND(AVG(windspeed_kmh), 1)           AS avg_windspeed_kmh,
    ROUND(AVG(humidity_pct), 1)            AS avg_humidity_pct,

    -- Campaign viability: the derived field doing real work
    ROUND(AVG(campaign_viability_score), 2)  AS avg_viability_score,
    ROUND(MAX(campaign_viability_score), 2)  AS peak_viability_score,

    -- How many hours in the day were actually "good" for outdoor campaigns?
    COUNTIF(campaign_viability_score >= 6.0) AS good_hours_count,
    COUNTIF(campaign_viability_score >= 8.0) AS excellent_hours_count,

    -- Most common viability label for the day
    (
        SELECT label
        FROM UNNEST(ARRAY_AGG(campaign_viability_label)) AS label
        GROUP BY label
        ORDER BY COUNT(*) DESC
        LIMIT 1
    ) AS dominant_viability_label,

    -- Most common weather description for the day
    (
        SELECT desc
        FROM UNNEST(ARRAY_AGG(weather_description)) AS desc
        GROUP BY desc
        ORDER BY COUNT(*) DESC
        LIMIT 1
    ) AS dominant_weather_description

FROM `your-project-id.marketing_weather.hourly_conditions`

-- Filter to the last 7 days to keep the summary fresh
WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)

GROUP BY
    city,
    date,
    season

ORDER BY
    date DESC,
    avg_viability_score DESC;


-- ============================================================
-- Query 2: Best Hours to Run Outdoor Campaigns (Top 10 globally)
-- ============================================================

SELECT
    city,
    date,
    hour,
    time_of_day,
    day_type,
    temperature_c,
    apparent_temperature_c,
    precipitation_mm,
    windspeed_kmh,
    weather_description,
    campaign_viability_score,
    campaign_viability_label
FROM `your-project-id.marketing_weather.hourly_conditions`
WHERE
    date >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
    AND campaign_viability_score >= 7.0
ORDER BY campaign_viability_score DESC
LIMIT 10;


-- ============================================================
-- Query 3: City Rankings by Average Viability (last 7 days)
-- ============================================================

SELECT
    city,
    COUNT(*) AS total_hours,
    ROUND(AVG(campaign_viability_score), 2)              AS avg_score,
    COUNTIF(campaign_viability_label = 'Excellent')      AS excellent_hours,
    COUNTIF(campaign_viability_label = 'Good')           AS good_hours,
    COUNTIF(campaign_viability_label IN ('Poor', 'Unsuitable')) AS bad_hours,
    ROUND(
        100.0 * COUNTIF(campaign_viability_score >= 6.0) / COUNT(*),
        1
    ) AS pct_usable_hours
FROM `your-project-id.marketing_weather.hourly_conditions`
WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
GROUP BY city
ORDER BY avg_score DESC;
