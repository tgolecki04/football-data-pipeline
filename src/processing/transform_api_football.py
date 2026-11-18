
"""Transform API-Football Bronze JSON into Silver Parquet."""

import io
import json
import logging
import os

import boto3
import pandas as pd
from dotenv import load_dotenv

from src.processing.data_quality import validate_fixtures
from src.processing.silver_schema import validate_silver_schema

logger = logging.getLogger(__name__)

SOURCE = "api_football"


def create_s3_client():
    """Create an S3-compatible RustFS client."""
    return boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ["RUSTFS_ACCESS_KEY"],
        aws_secret_access_key=os.environ["RUSTFS_SECRET_KEY"],
        region_name="us-east-1",
    )


def read_bronze(league_id: int, season: int) -> dict:
    """Read the latest API-Football Bronze JSON."""

    s3 = create_s3_client()

    prefix = (
        f"bronze/{SOURCE}/league_{league_id}/"
        f"season_{season}/"
    )

    objects = []

    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(
        Bucket=os.environ["S3_BUCKET"],
        Prefix=prefix,
    ):
        objects.extend(
            obj
            for obj in page.get("Contents", [])
            if obj["Key"].endswith(".json")
        )

    if not objects:
        raise RuntimeError(
            f"No Bronze files found for league={league_id}, "
            f"season={season}."
        )

    latest = max(
        objects,
        key=lambda obj: obj["LastModified"],
    )

    logger.info("Reading Bronze: %s", latest["Key"])

    response = s3.get_object(
        Bucket=os.environ["S3_BUCKET"],
        Key=latest["Key"],
    )

    return json.loads(response["Body"].read().decode("utf-8"))


def transform_matches(data: dict) -> pd.DataFrame:
    """Convert API-Football response into the common Silver schema."""

    rows = []

    for match in data["response"]:
        fixture = match["fixture"]
        league = match["league"]
        teams = match["teams"]
        goals = match["goals"]

        rows.append({
            "source": SOURCE,
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
        raise ValueError("No API-Football matches to transform.")

    df["date"] = pd.to_datetime(df["date"], utc=True)

    original_count = len(df)

    df = df.drop_duplicates(
        subset=["source", "fixture_id"]
    )

    removed_count = original_count - len(df)

    if removed_count:
        logger.warning(
            "Removed %d duplicate fixtures",
            removed_count,
        )

    return df.sort_values("date").reset_index(drop=True)


def save_to_silver(
    df: pd.DataFrame,
    league_id: int,
    season: int,
) -> str:
    """Save validated fixtures to Silver Parquet."""

    s3 = create_s3_client()

    key = (
        f"silver/{SOURCE}/league_{league_id}/"
        f"season_{season}/fixtures.parquet"
    )

    buffer = io.BytesIO()

    df.to_parquet(
        buffer,
        engine="pyarrow",
        index=False,
    )

    s3.put_object(
        Bucket=os.environ["S3_BUCKET"],
        Key=key,
        Body=buffer.getvalue(),
        ContentType="application/octet-stream",
    )

    logger.info(
        "Saved %d fixtures to Silver: %s",
        len(df),
        key,
    )

    return key


def main() -> None:
    """Run the API-Football Bronze-to-Silver stage."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    load_dotenv()

    league_id = int(os.environ["LEAGUE_ID"])
    season = int(os.environ["SEASON"])

    data = read_bronze(league_id, season)
    df = transform_matches(data)

    if not df["league_id"].eq(league_id).all():
        raise ValueError(
            "Bronze league does not match requested league."
        )

    if not df["season"].eq(season).all():
        raise ValueError(
            "Bronze season does not match requested season."
        )

    validate_silver_schema(df, SOURCE)
    validate_fixtures(df)

    logger.info("Silver validation passed: %d fixtures", len(df))

    save_to_silver(df, league_id, season)


if __name__ == "__main__":
    main()
