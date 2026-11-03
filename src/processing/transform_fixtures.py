""" Transform the latest Bronze fixtures into Silver Parquet file. """

import io
import json
import logging
import sys
import os

import boto3
import pandas as pd
from data_quality import validate_fixtures
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

load_dotenv()

BUCKET = os.environ["S3_BUCKET"]

LEAGUE_ID = int(os.environ["LEAGUE_ID"])
SEASON = int(os.environ["SEASON"])

BRONZE_PREFIX = (
    f"bronze/api_football/league_{LEAGUE_ID}/"
    f"season_{SEASON}/"
)

SILVER_KEY = (
    f"silver/api_football/league_{LEAGUE_ID}/"
    f"season_{SEASON}/"
    "fixtures.parquet"
)

# RustFS is S3-compatible, so boto3 works with a custom endpoint
s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["S3_ENDPOINT"],
    aws_access_key_id=os.environ["RUSTFS_ACCESS_KEY"],
    aws_secret_access_key=os.environ["RUSTFS_SECRET_KEY"],
    region_name="us-east-1",
)

# Find the Bronze files
objects = []

paginator = s3.get_paginator("list_objects_v2")

for page in paginator.paginate(
    Bucket=BUCKET,
    Prefix=BRONZE_PREFIX,
):
    objects.extend(
        obj for obj in page.get("Contents", [])
        if obj["Key"].endswith(".json")
    )

if not objects:
    raise RuntimeError("No Bronze files found for the specified league and season.")

latest = max(objects, key=lambda obj: obj["LastModified"])
bronze_key = latest["Key"]

logger.info("Reading Bronze file: %s", bronze_key)

response = s3.get_object(
    Bucket=BUCKET,
    Key=bronze_key,
)

data = json.loads(
    response["Body"].read().decode("utf-8")
)

matches = data["response"]

# Flatten the nested structure into a list of dictionaries
rows = []

for match in matches:
    fixture = match["fixture"]
    league = match["league"]
    teams = match["teams"]
    goals = match["goals"]

    rows.append({
        "fixture_id": fixture["id"],
        "date": fixture["date"],
        "league_id": league["id"],
        "season": league["season"],
        "round": league.get("round"),
        "home_team_id": teams["home"]["id"],
        "home_team": teams["home"]["name"],
        "away_team_id": teams["away"]["id"],
        "away_team": teams["away"]["name"],
        "home_goals": goals["home"],
        "away_goals": goals["away"],
        "status": fixture["status"]["short"],
    })

df = pd.DataFrame(rows)

if df.empty:
    raise RuntimeError("Brak meczów do przetworzenia.")

df["date"] = pd.to_datetime(
    df["date"],
    utc=True,
)

df = df.drop_duplicates(
    subset=["fixture_id"]
)

df = df.sort_values("date")

validate_fixtures(df)
logger.info("Validation passed")

# Write Parquet to a memory, so no temporary file is needed
buffer = io.BytesIO()

df.to_parquet(
    buffer,
    engine="pyarrow",
    index=False,
)

s3.put_object(
    Bucket=BUCKET,
    Key=SILVER_KEY,
    Body=buffer.getvalue(),
    ContentType="application/octet-stream",
)

logger.info(
    "Transformation finished: %d fixtures, %d columns, saved to Silver: %s",
    len(df),
    len(df.columns),
    SILVER_KEY
)

logger.info(
    "Sample data from Silver file:\n%s",
    df[[
        "date",
        "home_team",
        "away_team",
        "home_goals",
        "away_goals",
        "status"
        ]
    ].head(10).to_string(),
)