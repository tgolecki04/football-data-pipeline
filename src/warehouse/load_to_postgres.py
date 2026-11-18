
"""Load fixtures from Silver Parquet into PostgreSQL."""

import argparse
import io
import logging
import os
from pathlib import Path

import boto3
import pandas as pd
import psycopg
from dotenv import load_dotenv

from src.processing.silver_schema import (
    SILVER_COLUMNS,
    validate_silver_schema,
)
from src.warehouse.load_guard import validate_replacement


logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]


def silver_key(
    source: str,
    season: int,
    league_id: int | None = None,
    competition: str | None = None,
) -> str:
    """Build the Silver object key for the selected provider."""

    if source == "api_football":
        if league_id is None:
            raise ValueError("API-Football requires league_id.")

        return (
            f"silver/api_football/league_{league_id}/"
            f"season_{season}/fixtures.parquet"
        )

    if source == "football_data":
        if not competition:
            raise ValueError("football-data.org requires competition.")

        competition = competition.strip().upper()

        return (
            f"silver/football_data/competition_{competition}/"
            f"season_{season}/fixtures.parquet"
        )

    raise ValueError(f"Unsupported source: {source}")


def read_silver(key: str) -> pd.DataFrame:
    """Read Silver Parquet from S3-compatible storage."""

    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ["RUSTFS_ACCESS_KEY"],
        aws_secret_access_key=os.environ["RUSTFS_SECRET_KEY"],
        region_name="us-east-1",
    )

    logger.info("Reading Silver: %s", key)

    response = s3.get_object(
        Bucket=os.environ["S3_BUCKET"],
        Key=key,
    )

    return pd.read_parquet(
        io.BytesIO(response["Body"].read())
    )


def to_records(df: pd.DataFrame) -> list[tuple]:
    """Convert validated Silver rows into PostgreSQL parameters."""

    records = []

    for row in df[list(SILVER_COLUMNS)].itertuples(
        index=False, name=None
    ):
        values = list(row)

        # Convert date to a Python datetime.
        values[2] = pd.Timestamp(values[2]).to_pydatetime()

        # Convert nullable scores to SQL NULL.
        for index in (10, 11):
            if pd.isna(values[index]):
                values[index] = None
            else:
                values[index] = int(values[index])

        # Convert optional round to SQL NULL.
        if pd.isna(values[5]):
            values[5] = None

        # Convert identifiers to ordinary Python integers.
        for index in (1, 3, 4, 6, 8):
            values[index] = int(values[index])

        records.append(tuple(values))

    return records


INSERT_SQL = """
    INSERT INTO public.fixtures (
        source,
        fixture_id,
        date,
        league_id,
        season,
        round,
        home_team_id,
        home_team,
        away_team_id,
        away_team,
        home_goals,
        away_goals,
        status
    )
    VALUES (
        %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s
    )
    ON CONFLICT (source, fixture_id)
    DO UPDATE SET
        date = EXCLUDED.date,
        league_id = EXCLUDED.league_id,
        season = EXCLUDED.season,
        round = EXCLUDED.round,
        home_team_id = EXCLUDED.home_team_id,
        home_team = EXCLUDED.home_team,
        away_team_id = EXCLUDED.away_team_id,
        away_team = EXCLUDED.away_team,
        home_goals = EXCLUDED.home_goals,
        away_goals = EXCLUDED.away_goals,
        status = EXCLUDED.status;
"""


def load_to_postgres(
    df: pd.DataFrame,
    source: str,
    season: int,
    league_id: int | None = None,
) -> int:
    """Safely replace one source/league/season dataset."""

    validate_silver_schema(df, source)

    if not df["season"].eq(season).all():
        raise ValueError("Silver season does not match requested season.")

    unique_leagues = df["league_id"].unique()

    if len(unique_leagues) != 1:
        raise ValueError("Expected exactly one league in Silver.")

    actual_league_id = int(unique_leagues[0])

    if league_id is not None and actual_league_id != league_id:
        raise ValueError("Silver league does not match requested league.")

    records = to_records(df)

    with psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=5,
    ) as conn:
        with conn.cursor() as cursor:

            # Retain existing initialization behavior.
            schema_path = ROOT / "sql" / "create_fixtures.sql"
            cursor.execute(
                schema_path.read_text(encoding="utf-8")
            )

            # Validate before any existing rows are deleted.
            validate_replacement(
                cursor,
                df,
                source,
                actual_league_id,
                season,
            )

            cursor.execute(
                """
                DELETE FROM public.fixtures
                WHERE source = %s
                  AND league_id = %s
                  AND season = %s
                """,
                (source, actual_league_id, season),
            )

            cursor.executemany(INSERT_SQL, records)

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM public.fixtures
                WHERE source = %s
                  AND league_id = %s
                  AND season = %s
                """,
                (source, actual_league_id, season),
            )

            loaded_count = cursor.fetchone()[0]

            if loaded_count != len(records):
                raise RuntimeError(
                    f"Expected {len(records)} fixtures, "
                    f"got {loaded_count}."
                )

    logger.info(
        "PostgreSQL load completed: source=%s, "
        "league=%d, season=%d, fixtures=%d",
        source,
        actual_league_id,
        season,
        loaded_count,
    )

    return loaded_count


def main() -> None:
    load_dotenv(ROOT / ".env")

    parser = argparse.ArgumentParser(
        description="Load Silver fixtures into PostgreSQL."
    )

    parser.add_argument(
        "--source",
        required=True,
        choices=("api_football", "football_data"),
    )
    parser.add_argument("--league-id", type=int)
    parser.add_argument("--competition")
    parser.add_argument("--season", type=int)

    args = parser.parse_args()

    season = args.season
    if season is None:
        season = int(os.environ["SEASON"])

    league_id = args.league_id
    if args.source == "api_football" and league_id is None:
        league_id = int(os.environ["LEAGUE_ID"])

    competition = args.competition
    if args.source == "football_data" and not competition:
        competition = os.environ["COMPETITION_CODE"]

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    key = silver_key(
        source=args.source,
        season=season,
        league_id=league_id,
        competition=competition,
    )

    df = read_silver(key)

    load_to_postgres(
        df=df,
        source=args.source,
        season=season,
        league_id=league_id,
    )


if __name__ == "__main__":
    main()
