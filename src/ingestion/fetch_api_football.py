"""Download fixtures from API-FOOTBALL and store the raw response in the Bronze layer."""

import json
import logging
import os
import sys
from datetime import UTC, datetime


import boto3
import requests
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)

load_dotenv()

API_URL = "https://v3.football.api-sports.io/fixtures"

API_KEY = os.environ["API_FOOTBALL_KEY"]
BUCKET = os.environ["S3_BUCKET"]

LEAGUE_ID = int(os.environ["LEAGUE_ID"])
SEASON = int(os.environ["SEASON"])

params = {
    "league": LEAGUE_ID,
    "season": SEASON,
}

headers = {
    "x-apisports-key": API_KEY,
}

logger.info("Fetching fixtures from API-FOOTBALL: league=%s, season=%s",
            LEAGUE_ID,
            SEASON)

response = requests.get(
    API_URL,
    headers=headers,
    params=params,
    timeout=30,
)

response.raise_for_status()

data = response.json()

# The API can report errors even with HTTP 200
if data.get("errors"):
    raise RuntimeError(f"Błąd API: {data['errors']}")

matches = data.get("response", [])

logger.info("Fetched %d fixtures", len(matches))

# Do not store empty responses 
if not matches:
    raise RuntimeError("API nie zwróciło meczów.")

# RustFS is S3-compatible, so boto3 works with a custom endpoint 
s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["S3_ENDPOINT"],
    aws_access_key_id=os.environ["RUSTFS_ACCESS_KEY"],
    aws_secret_access_key=os.environ["RUSTFS_SECRET_KEY"],
    region_name="us-east-1",
)

timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

object_key = (
    f"bronze/api_football/league_{LEAGUE_ID}/"
    f"season_{SEASON}/"
    f"fixtures_{timestamp}.json"
)

# Store the full API response unchanged so it can be reprocessed later
s3.put_object(
    Bucket=BUCKET,
    Key=object_key,
    Body=json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8"),
    ContentType="application/json",
)

logger.info("Saved raw data to RustFS: bucket=%s, key=%s",BUCKET,object_key)

