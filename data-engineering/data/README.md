# FireFusion: Data Engineering Pipeline

## Overview
This repository contains the data engineering pipelines and database architecture for the FireFusion bushfire forecasting project. 

Our primary goal in this stream is to extract historical fire data, weather conditions, topography, vegetation health, and infrastructure risk data, and format it into a unified database structure for the AI modeling team.

## Repository Structure
To keep our work organized and prevent merge conflicts, this repository follows a strict directory structure:

* **`/architecture`**: Contains the official database design, including the Star Schema Entity Relationship Diagram (ERD) and table documentation. This is our single source of truth for column names and data types.
* **`/data`**: The local storage for our datasets. 
  * `/raw`: Unmodified files downloaded directly from APIs or government portals.
  * `/processed`: Cleaned datasets formatted to match our Star Schema architecture.
  * `/data_dictionaries`: Markdown files explaining the variables and sources of each dataset.
* **`/notebooks`**: Jupyter Notebooks used for Exploratory Data Analysis (EDA), testing, and creating visual charts (e.g., soil moisture mapping).
* **`/pipelines`**: The core Python extraction and transformation scripts. Each data source (e.g., Open-Meteo, NASA FIRMS) has its own dedicated subfolder here.

## Environment Setup
Before running any extraction scripts, ensure your local environment is configured correctly.

1. **Clone the repository:**
   git clone [Insert Your Repository URL Here]
   cd data-engineering

2. **Install Required Libraries:**
   Ensure you have Python installed. We recommend using a virtual environment.
   pip install -r requirements.txt

3. **Set Up API Keys (Security):**
   Never hardcode API keys or passwords directly into your Python scripts. 
   * Create a file named `.env` in the root folder.
   * Add your keys to this file (e.g., `NASA_API_KEY=your_key_here`).
   * The `.env` file is already included in our `.gitignore` to prevent it from being uploaded to GitHub.

## Data Storage Rules
GitHub is for version control of our code, not for storing massive datasets. 

* **Do not push `.csv`, `.zip`, or `.json` data files to GitHub.**
* Our `.gitignore` file is configured to block files in the `data/raw/` and `data/processed/` folders. Keep your data on your local machine.
