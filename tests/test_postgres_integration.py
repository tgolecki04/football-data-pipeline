
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
    ) as conn, conn.cursor() as cursor:
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
    ) as conn, conn.cursor() as cursor:
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
                WHERE status IN ('FT', 'AET', 'PEN', 'FINISHED')
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
    ) as conn, conn.cursor() as cursor:
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


@pytest.mark.integration
def test_gold_team_recent_form_limits_to_five_matches():
    with psycopg.connect(
        host="localhost",
        port=5432,
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    ) as conn:
        with conn.cursor() as cursor:
            # Start a transaction that will be rolled back.
            cursor.execute("SAVEPOINT recent_form_test")

            # Insert six finished matches for one team.
            cursor.execute(
                """
                INSERT INTO fixtures (
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
                VALUES
                    ('api_football', 990001, '2024-01-01', 999, 2024, 'Round 1',
                     990, 'Recent Form FC', 991, 'Opponent 1', 1, 0, 'FT'),

                    ('api_football', 990002, '2024-01-02', 999, 2024, 'Round 2',
                     990, 'Recent Form FC', 992, 'Opponent 2', 2, 0, 'FT'),

                    ('api_football', 990003, '2024-01-03', 999, 2024, 'Round 3',
                     990, 'Recent Form FC', 993, 'Opponent 3', 0, 0, 'FT'),

                    ('api_football', 990004, '2024-01-04', 999, 2024, 'Round 4',
                     990, 'Recent Form FC', 994, 'Opponent 4', 0, 1, 'FT'),

                    ('api_football', 990005, '2024-01-05', 999, 2024, 'Round 5',
                     990, 'Recent Form FC', 995, 'Opponent 5', 3, 1, 'FT'),

                    ('api_football', 990006, '2024-01-06', 999, 2024, 'Round 6',
                     990, 'Recent Form FC', 996, 'Opponent 6', 4, 0, 'FT')
                """
            )

            cursor.execute(
                """
                SELECT
                    played,
                    wins,
                    draws,
                    losses,
                    goals_for,
                    goals_against,
                    goal_difference,
                    points
                FROM gold_team_recent_form
                WHERE league_id = 999
                  AND season = 2024
                  AND team_id = 990
                """
            )
            result = cursor.fetchone()

            # Remove test data before the connection commits.
            cursor.execute("ROLLBACK TO SAVEPOINT recent_form_test")

    assert result == (5, 3, 1, 1, 9, 2, 7, 10)



@pytest.mark.integration
def test_gold_team_recent_form_separates_leagues_and_seasons():
    with psycopg.connect(
        host="localhost",
        port=5432,
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SAVEPOINT recent_form_scope_test")

            cursor.execute(
                """
                INSERT INTO fixtures (
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
                VALUES
                    ('api_football', 991001, '2024-01-01', 998, 2024, 'Round 1',
                     990, 'Scope Test FC', 997, 'Opponent A', 2, 0, 'FT'),

                    ('api_football', 991002, '2024-01-02', 998, 2025, 'Round 1',
                     990, 'Scope Test FC', 997, 'Opponent B', 0, 1, 'FT'),

                    ('api_football', 991003, '2024-01-03', 999, 2024, 'Round 1',
                     990, 'Scope Test FC', 997, 'Opponent C', 1, 1, 'FT')
                """
            )

            cursor.execute(
                """
                SELECT league_id, season, played, wins, draws, losses, points
                FROM gold_team_recent_form
                WHERE team_id = 990
                  AND league_id IN (998, 999)
                ORDER BY league_id, season
                """
            )
            results = cursor.fetchall()

            cursor.execute("ROLLBACK TO SAVEPOINT recent_form_scope_test")

    assert results == [
        (998, 2024, 1, 1, 0, 0, 3),
        (998, 2025, 1, 0, 0, 1, 0),
        (999, 2024, 1, 0, 1, 0, 1),
    ]


@pytest.mark.integration
@pytest.mark.requires_pipeline_data
def test_gold_separates_data_sources():
    with psycopg.connect(
        host="localhost",
        port=5432,
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    ) as conn, conn.cursor() as cursor:

        for view in ("gold_team_stats", "gold_team_recent_form"):
            cursor.execute(
                f"""
                SELECT source, COUNT(*)
                FROM {view}
                WHERE season = 2024
                  AND (
                      (source = 'api_football' AND league_id = 140)
                      OR
                      (source = 'football_data' AND league_id = 2014)
                  )
                GROUP BY source
                """
            )

            results = dict(cursor.fetchall())

            assert results == {
                "api_football": 20,
                "football_data": 20,
            }, f"Unexpected provider statistics in {view}: {results}"
            
@pytest.mark.integration
def test_fixtures_primary_key_is_source_aware():
    with psycopg.connect(
        host="localhost",
        port=5432,
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    ) as conn, conn.cursor() as cursor:
        cursor.execute("""
            SELECT column_name
            FROM information_schema.key_column_usage
            WHERE table_schema = 'public'
              AND table_name = 'fixtures'
              AND constraint_name = (
                  SELECT constraint_name
                  FROM information_schema.table_constraints
                  WHERE table_schema = 'public'
                    AND table_name = 'fixtures'
                    AND constraint_type = 'PRIMARY KEY'
              )
            ORDER BY ordinal_position;
        """)

        primary_key_columns = [
            row[0] for row in cursor.fetchall()
        ]

    assert primary_key_columns == ["source", "fixture_id"]