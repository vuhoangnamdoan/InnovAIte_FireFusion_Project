# Open-Meteo Weather Data Pipeline (MVP)

This pipeline fetches and processes weather data from Open-Meteo API.

## Steps
1. Fetch hourly weather data
2. Store raw data as CSV
3. Clean and preprocess data
4. Generate cleaned CSV

## Files
- fetch_open_meteo.py → fetches data
- clean_open_meteo.py → cleans data

## Output
- melbourne_weather_raw.csv
- melbourne_weather_cleaned.csv

## Purpose
This pipeline is part of FireFusion MVP to support weather-based fire prediction models.
