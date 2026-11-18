
"""Unit tests for the shared PostgreSQL loader."""

import pandas as pd
import pytest

from src.warehouse.load_to_postgres import (
    silver_key,
    to_records,
)


def test_api_football_silver_key():
    key = silver_key(
        source="api_football",
        league_id=39,
        season=2023,
    )

    assert key == (
        "silver/api_football/league_39/"
        "season_2023/fixtures.parquet"
    )


def test_football_data_silver_key():
    key = silver_key(
        source="football_data",
        competition="pl",
        season=2023,
    )

    assert key == (
        "silver/football_data/competition_PL/"
        "season_2023/fixtures.parquet"
    )


def test_missing_league_id_is_rejected():
    with pytest.raises(ValueError, match="requires league_id"):
        silver_key(source="api_football", season=2023)


def test_missing_competition_is_rejected():
    with pytest.raises(ValueError, match="requires competition"):
        silver_key(source="football_data", season=2023)


def test_unknown_source_is_rejected():
    with pytest.raises(ValueError, match="Unsupported source"):
        silver_key(source="unknown", season=2023)


def test_to_records_converts_values():
    df = pd.DataFrame([{
        "source": "api_football",
        "fixture_id": 101,
        "date": pd.Timestamp("2023-08-12T15:00:00Z"),
        "league_id": 39,
        "season": 2023,
        "round": "Regular Season - 1",
        "home_team_id": 1,
        "home_team": "Team A",
        "away_team_id": 2,
        "away_team": "Team B",
        "home_goals": 2,
        "away_goals": 1,
        "status": "FT",
    }])

    records = to_records(df)

    assert len(records) == 1
    assert len(records[0]) == 13
    assert records[0][0] == "api_football"
    assert records[0][1] == 101
    assert records[0][10] == 2
    assert records[0][11] == 1
    assert records[0][12] == "FT"


def test_to_records_handles_unplayed_fixture():
    df = pd.DataFrame([{
        "source": "football_data",
        "fixture_id": 201,
        "date": pd.Timestamp("2024-01-10T18:00:00Z"),
        "league_id": 2021,
        "season": 2023,
        "round": None,
        "home_team_id": 11,
        "home_team": "Team C",
        "away_team_id": 12,
        "away_team": "Team D",
        "home_goals": None,
        "away_goals": None,
        "status": "SCHEDULED",
    }])

    records = to_records(df)

    assert records[0][5] is None
    assert records[0][10] is None
    assert records[0][11] is None
