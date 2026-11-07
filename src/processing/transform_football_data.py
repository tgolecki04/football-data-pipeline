"""Transform football-data.org Bronze matches into a Silver DataFrame."""

import pandas as pd
import io
import json
import logging
import os

import boto3
from dotenv import load_dotenv
from src.processing.data_quality import validate_fixtures

logger = logging.getLogger(__name__)


def transform_matches(data: dict) -> pd.DataFrame:
    """Convert football-data.org matches to the common fixtures schema."""

    rows = []

    for match in data["matches"]:
        rows.append({
            "source": "football_data",
            "fixture_id": match["id"],
            "date": match["utcDate"],
            "league_id": match["competition"]["id"],
            "season": int(match["season"]["startDate"][:4]),
            "round": str(match.get("matchday") or ""),
            "home_team_id": match["homeTeam"]["id"],
            "home_team": match["homeTeam"]["name"],
            "away_team_id": match["awayTeam"]["id"],
            "away_team": match["awayTeam"]["name"],
            "home_goals": match["score"]["fullTime"]["home"],
            "away_goals": match["score"]["fullTime"]["away"],
            "status": match["status"],
        })

    df = pd.DataFrame(rows)

    if df.empty:
        raise ValueError("No matches to transform.")

    df["date"] = pd.to_datetime(df["date"], utc=True)

    df = df.drop_duplicates(subset=["source", "fixture_id"])
    df = df.sort_values("date").reset_index(drop=True)

    return df

def read_bronze(competition: str, season: int) -> dict:
    """Read the latest football-data.org Bronze JSON."""

    load_dotenv()

    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ["RUSTFS_ACCESS_KEY"],
        aws_secret_access_key=os.environ["RUSTFS_SECRET_KEY"],
        region_name="us-east-1",
    )

    prefix = (
        f"bronze/football_data/competition_{competition}/"
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
            f"No Bronze files found for {competition}, season {season}."
        )

    latest = max(objects, key=lambda obj: obj["LastModified"])

    logger.info("Reading Bronze file: %s", latest["Key"])

    response = s3.get_object(
        Bucket=os.environ["S3_BUCKET"],
        Key=latest["Key"],
    )

    return json.loads(response["Body"].read().decode("utf-8"))

def save_to_silver(
    df: pd.DataFrame,
    competition: str,
    season: int,
) -> str:
    """Save transformed fixtures as Silver Parquet."""

    load_dotenv()

    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ["RUSTFS_ACCESS_KEY"],
        aws_secret_access_key=os.environ["RUSTFS_SECRET_KEY"],
        region_name="us-east-1",
    )

    object_key = (
        f"silver/football_data/competition_{competition}/"
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
        Key=object_key,
        Body=buffer.getvalue(),
        ContentType="application/octet-stream",
    )

    logger.info(
        "Saved %d fixtures to Silver: %s",
        len(df),
        object_key,
    )

    return object_key

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    load_dotenv()
    competition = os.environ["COMPETITION_CODE"].strip().upper()
    season = int(os.environ["SEASON"])

    data = read_bronze(competition, season)

    df = transform_matches(data)
    validate_fixtures(df)

    logger.info(
        "Silver validation passed: %d fixtures",
        len(df),
    )

    # Verify that Bronze contains the requested season and competition.
    if not (
        df["season"].eq(season).all()
        and df["league_id"].eq(2014).all()
    ):
        raise ValueError("Bronze data does not match the requested season or La Liga.")

    object_key = save_to_silver(df, competition, season)

    logger.info("Transformation completed: %s", object_key)


if __name__ == "__main__":
    main()