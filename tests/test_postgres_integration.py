
import os

import psycopg
import pytest
from dotenv import load_dotenv


load_dotenv()


@pytest.mark.integration
def test_postgres_connection():
    with psycopg.connect(
        host="localhost",
        port=5432,
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()

    assert result == (1,)


@pytest.mark.integration
@pytest.mark.requires_pipeline_data
def test_fixtures_and_gold_consistency():
    with psycopg.connect(
        host="localhost",
        port=5432,
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM fixtures
                """
            )
            fixture_count = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM fixtures
                WHERE status IN ('FT', 'AET', 'PEN')
                  AND home_goals IS NOT NULL
                  AND away_goals IS NOT NULL
                """
            )
            finished_count = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT COALESCE(SUM(played), 0)
                FROM gold_team_stats
                """
            )
            team_appearances = cursor.fetchone()[0]

    assert fixture_count > 0
    assert finished_count > 0
    assert team_appearances == finished_count * 2
