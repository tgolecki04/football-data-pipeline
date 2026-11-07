"""Download fixtures from football-data.org into the Bronze layer."""

import logging
import os

import requests
from dotenv import load_dotenv

import json
from datetime import UTC, datetime

import boto3

load_dotenv()

logger = logging.getLogger(__name__)

API_BASE_URL = "https://api.football-data.org/v4"


def fetch_matches(competition: str, season: int) -> dict:
    """Fetch matches for a competition and season."""

    api_key = os.environ["FOOTBALL_DATA_API_KEY"]

    url = f"{API_BASE_URL}/competitions/{competition}/matches"

    headers = {
        "X-Auth-Token": api_key,
    }

    params = {
        "season": season,
    }

    logger.info(
        "Fetching matches from football-data.org: competition=%s, season=%s",
        competition,
        season,
    )

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    matches = data.get("matches", [])

    if not matches:
        raise RuntimeError(
            "football-data.org returned no matches."
        )

    logger.info("Fetched %d matches", len(matches))

    return data

def save_to_bronze(data: dict, competition: str, season: int) -> str:
    """Store the original football-data.org response in RustFS."""

    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ["RUSTFS_ACCESS_KEY"],
        aws_secret_access_key=os.environ["RUSTFS_SECRET_KEY"],
        region_name="us-east-1",
    )

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    object_key = (
        f"bronze/football_data/competition_{competition}/"
        f"season_{season}/"
        f"matches_{timestamp}.json"
    )

    s3.put_object(
        Bucket=os.environ["S3_BUCKET"],
        Key=object_key,
        Body=json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8"),
        ContentType="application/json",
    )

    logger.info(
        "Saved raw data to RustFS: bucket=%s, key=%s",
        os.environ["S3_BUCKET"],
        object_key,
    )

    return object_key

def main() -> None:
    """Run football-data.org ingestion."""

    competition = os.environ["COMPETITION_CODE"].strip().upper()
    season = int(os.environ["SEASON"])

    data = fetch_matches(
        competition=competition,
        season=season,
    )

    object_key = save_to_bronze(
        data=data,
        competition=competition,
        season=season,
    )

    logger.info(
        "Ingestion completed successfully: %s",
        object_key,
    )


if __name__ == "__main__":
    main()