--
-- PostgreSQL database dump
--

-- Dumped from database version 18.1 (Homebrew)
-- Dumped by pg_dump version 18.1 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', 'public', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';
SET default_table_access_method = heap;


CREATE TABLE at_risk_infrastructure (
    facility_id integer NOT NULL,
    facility_name text,
    category text,
    latitude real,
    longitude real,
    lga text
);

CREATE TABLE fire_events (
    event_id integer NOT NULL,
    weather_id integer,
    topo_id integer,
    fuel_id integer,
    facility_id integer,
    latitude real,
    longitude real,
    event_date date,
    confidence_score integer,
    source_system text
);

CREATE TABLE fuel_and_vegetation (
    fuel_id integer NOT NULL,
    latitude real,
    longitude real,
    record_date date,
    vegetation_class text,
    dryness_index real,
    soil_moisture real
);

CREATE TABLE topography (
    topo_id integer NOT NULL,
    latitude real,
    longitude real,
    elevation_meters real,
    slope_angle real
);

CREATE TABLE weather_conditions (
    weather_id integer NOT NULL,
    latitude real,
    longitude real,
    record_date timestamp without time zone,
    temperature_c real,
    wind_speed_kmh real,
    relative_humidity real
);


ALTER TABLE ONLY at_risk_infrastructure
    ADD CONSTRAINT at_risk_infrastructure_pkey PRIMARY KEY (facility_id);

ALTER TABLE ONLY fire_events
    ADD CONSTRAINT fire_events_pkey PRIMARY KEY (event_id);

ALTER TABLE ONLY fuel_and_vegetation
    ADD CONSTRAINT fuel_and_vegetation_pkey PRIMARY KEY (fuel_id);

ALTER TABLE ONLY topography
    ADD CONSTRAINT topography_pkey PRIMARY KEY (topo_id);


ALTER TABLE ONLY weather_conditions
    ADD CONSTRAINT weather_conditions_pkey PRIMARY KEY (weather_id);


ALTER TABLE ONLY fire_events
    ADD CONSTRAINT fire_events_facility_id_fkey FOREIGN KEY (facility_id) REFERENCES at_risk_infrastructure(facility_id);


ALTER TABLE ONLY fire_events
    ADD CONSTRAINT fire_events_fuel_id_fkey FOREIGN KEY (fuel_id) REFERENCES fuel_and_vegetation(fuel_id);

ALTER TABLE ONLY fire_events
    ADD CONSTRAINT fire_events_topo_id_fkey FOREIGN KEY (topo_id) REFERENCES topography(topo_id);

ALTER TABLE ONLY fire_events
    ADD CONSTRAINT fire_events_weather_id_fkey FOREIGN KEY (weather_id) REFERENCES weather_conditions(weather_id);

CREATE VIEW fire_events_full AS
SELECT
    fire_events.event_id,
    fire_events.latitude,
    fire_events.longitude,
    fire_events.event_date,
    fire_events.confidence_score,
    weather_conditions.temperature_c,
    weather_conditions.wind_speed_kmh,
    weather_conditions.relative_humidity,
    topography.elevation_meters,
    topography.slope_angle,
    fuel_and_vegetation.vegetation_class,
    fuel_and_vegetation.dryness_index,
    fuel_and_vegetation.soil_moisture,
    at_risk_infrastructure.facility_name,
    at_risk_infrastructure.category
FROM fire_events
LEFT JOIN weather_conditions ON fire_events.weather_id = weather_conditions.weather_id
LEFT JOIN topography ON fire_events.topo_id = topography.topo_id
LEFT JOIN fuel_and_vegetation ON fire_events.fuel_id = fuel_and_vegetation.fuel_id
LEFT JOIN at_risk_infrastructure ON fire_events.facility_id = at_risk_infrastructure.facility_id;
