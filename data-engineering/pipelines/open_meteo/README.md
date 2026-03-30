# FireFusion Data Engineering MVP

This folder contains a basic MVP data pipeline for FireFusion using Open-Meteo weather data.

## Pipeline
Open-Meteo API → ingestion script → raw CSV → cleaning script → cleaned CSV → validation → processed storage

## Files
- scripts/fetch_open_meteo.py
- scripts/clean_open_meteo.py
- data/melbourne_weather_raw.csv
- data/melbourne_weather_cleaned.csv
- scripts/validate_open_meteo.py
- scripts/store_processed_data.py
- processed/weather_data_final.csv

## Purpose
To test weather data ingestion and preprocessing for the FireFusion MVP pipeline.
