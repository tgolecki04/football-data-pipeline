"""Load football-data.org Silver fixtures into PostgreSQL."""

import io
import logging
import os

import boto3
import pandas as pd
import psycopg
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


def read_silver(competition: str, season: int) -> pd.DataFrame:
    """Read football-data.org Silver Parquet from RustFS."""

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

    logger.info("Reading Silver file: %s", object_key)

    response = s3.get_object(
        Bucket=os.environ["S3_BUCKET"],
        Key=object_key,
    )

    df = pd.read_parquet(
        io.BytesIO(response["Body"].read())
    )

    return df

def load_to_postgres(df: pd.DataFrame, season: int) -> None:
    """Replace football-data.org fixtures for one league and season."""

    source = "football_data"

    league_ids = df["league_id"].unique()

    if len(league_ids) != 1:
        raise ValueError("Expected exactly one league in Silver.")

    league_id = int(league_ids[0])

    if not df["source"].eq(source).all():
        raise ValueError("Unexpected source in Silver.")

    if not df["season"].eq(season).all():
        raise ValueError("Unexpected season in Silver.")

    if df.duplicated(subset=["source", "fixture_id"]).any():
        raise ValueError("Duplicate fixture identifiers in Silver.")

    records = []

    for row in df.itertuples(index=False):
        records.append((
            source,
            int(row.fixture_id),
            pd.Timestamp(row.date).to_pydatetime(),
            int(row.league_id),
            int(row.season),
            row.round,
            int(row.home_team_id),
            row.home_team,
            int(row.away_team_id),
            row.away_team,
            None if pd.isna(row.home_goals) else int(row.home_goals),
            None if pd.isna(row.away_goals) else int(row.away_goals),
            row.status,
        ))

    insert_sql = """
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

    with psycopg.connect(
        host="127.0.0.1",
        port=5432,
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=5,
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM public.fixtures
                WHERE source = %s
                  AND league_id = %s
                  AND season = %s;
                """,
                (source, league_id, season),
            )

            cursor.executemany(insert_sql, records)

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM public.fixtures
                WHERE source = %s
                  AND league_id = %s
                  AND season = %s;
                """,
                (source, league_id, season),
            )

            loaded_count = cursor.fetchone()[0]

            if loaded_count != len(df):
                raise RuntimeError(
                    f"Expected {len(df)} fixtures, got {loaded_count}."
                )

    logger.info(
        "PostgreSQL load completed: source=%s, league=%d, "
        "season=%d, fixtures=%d",
        source,
        league_id,
        season,
        loaded_count,
    )

def main() -> None:
    load_dotenv()

    competition = os.environ["COMPETITION_CODE"].strip().upper()
    season = int(os.environ["SEASON"])

    df = read_silver(competition, season)

    if df.empty:
        raise ValueError("Silver DataFrame is empty.")

    if not df["source"].eq("football_data").all():
        raise ValueError("Unexpected data source in Silver.")

    if not df["season"].eq(season).all():
        raise ValueError("Silver season does not match the requested season.")

    logger.info(
        "Silver loaded successfully: %d fixtures",
        len(df),
    )

    logger.info(
        "League IDs: %s",
        sorted(df["league_id"].unique().tolist()),
    )
    load_to_postgres(df, season)

if __name__ == "__main__":
    main()