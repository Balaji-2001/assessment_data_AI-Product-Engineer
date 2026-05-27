SELECT
  city,
  temp_band,
  COUNT(*) AS hour_count,
  AVG(temperature_2m) AS avg_temperature,
  MAX(wind_speed_10m) AS max_wind_speed
FROM `your-project.your_dataset.weather_forecast`
GROUP BY city, temp_band
ORDER BY city, temp_band;
