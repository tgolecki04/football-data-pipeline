
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


@pytest.mark.integration
@pytest.mark.requires_pipeline_data
def test_gold_team_statistics():
    
    if os.getenv("TEST_DATABASE_SEEDED") != "true":
        pytest.skip("Requires the seeded CI test database")
    
    expected_stats = {
        "Alpha FC": (2, 2, 0, 0, 6, 4, 2, 2),
        "Beta FC": (2, 1, 0, 1, 3, 4, 3, 1),
        "Gamma FC": (2, 0, 1, 1, 1, 1, 3, -2),
        "Delta FC": (2, 0, 1, 1, 1, 1, 2, -1),
    }

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
                SELECT
                    team_name,
                    played,
                    wins,
                    draws,
                    losses,
                    points,
                    goals_for,
                    goals_against,
                    goal_difference
                FROM gold_team_stats
                WHERE league_id = 39
                  AND season = 2023
                """
            )
            rows = cursor.fetchall()

    actual_stats = {
        row[0]: tuple(row[1:])
        for row in rows
    }

    assert actual_stats == expected_stats
