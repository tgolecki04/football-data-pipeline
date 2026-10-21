# Real-Time Football Data Pipeline :soccer::oil_drum::hammer_and_wrench:


An end-to-end data engineering and machine learning project focused on building a data platform for football analytics and in-play match predictions. The system integrates historical match data with live updates, processes the data through a structured pipeline, and uses machine learning models to estimate match outcome probabilities as the game progresses.

### Pipeline Overview

Data Ingestion → Data Lake → Data Processing → Data Warehouse → Machine Learning → Prediction 

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Technologies](#technologies)
- [Data Pipeline](#data-pipeline)
- [Machine Learning](#machine-learning)
- [Project Structure](#project-structure)
- [Setup](#setup)
- [Authors](#authors)

## Overview

This project aims to build an <b>end-to-end</b> football analytics platform that combines historical match data with live updates from external football APIs.

Raw data is ingested and stored in a data lake, then cleaned, transformed, and organized into analytical datasets for machine learning. These datasets are used to train and evaluate models that estimate match outcome probabilities and update predictions as new match information becomes available.

The final goal is to deliver a complete data pipeline, from raw data ingestion to model inference through a prediction API, with a focus on data quality, reproducibility, and reliable model evaluation.

## Architecture

## Technologies

## Data Pipeline

## Machine Learning

## Project Structure
```
football-data-pipeline/
├── sql/
│   └── gold_team_stats.sql          # Gold layer: team standings view
├── src/
│   ├── ingestion/
│   │   └── fetch_api_football.py    # API-Football to Bronze (raw JSON)
│   ├── processing/
│   │   └── transform_fixtures.py    # Bronze to Silver (Parquet)
│   ├── storage/
│   │   ├── ensure_bucket.py         # Creates the bucket if missing
│   │   └── test_s3_connection.py    # Checks the connection to RustFS
│   └── warehouse/
│       └── load_fixtures.py         # Silver to PostgreSQL
├── .env.example                     # Template for local configuration
├── compose.yaml                     # RustFS and PostgreSQL containers
├── requirements.txt                 # Python dependencies
└── run_pipeline.py                  # Runs the whole pipeline
```

## Setup

### Prerequisites

- Docker with Docker Compose
- Python 3.12.3
- A free API key from [API-Football](https://dashboard.api-football.com)
### Installation

1. Clone the repository and go to its folder.

2. Create your configuration file and set your `API_FOOTBALL_KEY` in it.

```bash
   cp .env.example .env
```

3. Start RustFS and PostgreSQL.

```bash
   docker compose up -d
```

4. Create a virtual environment and install the dependencies.

```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
```

### Running the pipeline

The first run needs `--fetch` to download data from the API:

```bash
python run_pipeline.py --fetch
```

Later runs reuse the data already stored in RustFS, so they do not use your API request limit:

```bash
python run_pipeline.py
```

The bucket is created automatically, so no manual setup in RustFS is needed.

### Checking the result

```bash
docker compose exec postgres psql -U db_user -d db -c "SELECT * FROM gold_team_stats ORDER BY points DESC LIMIT 5;"
```
Use your own values if you changed `POSTGRES_USER` or `POSTGRES_DB` in `.env`.


## Authors
  <table>
    <tr>
      <td align="center">
        <a href="https://github.com/tgolecki04">
          <img src="https://github.com/tgolecki04.png" width="100px;" alt="Tomasz Golecki"/><br />
          <sub><b>Tomasz Golecki</b></sub>
        </a>
      </td>
      <td align="center">
        <a href="https://github.com/MikolajZagojski">
          <img src="https://github.com/MikolajZagojski.png" width="100px;" alt="Mikołaj Zagojski"/><br />
          <sub><b>Mikołaj Zagojski</b></sub>
        </a>
      </td>
    </tr>
  </table>
