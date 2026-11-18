
"""Tests for the shared Silver fixtures schema."""

import pandas as pd
import pytest

from src.processing.silver_schema import (
    SILVER_COLUMNS,
    validate_silver_schema,
)


def make_fixture(source="api_football"):
    return pd.DataFrame([{
        "source": source,
        "fixture_id": 101,
        "date": pd.Timestamp("2024-01-01", tz="UTC"),
        "league_id": 39,
        "season": 2023,
        "round": "Round 1",
        "home_team_id": 1,
        "home_team": "Team A",
        "away_team_id": 2,
        "away_team": "Team B",
        "home_goals": 2,
        "away_goals": 1,
        "status": "FT",
    }])


@pytest.mark.parametrize(
    "source", ["api_football", "football_data"]
)
def test_both_sources_use_shared_schema(source):
    df = make_fixture(source)

    validate_silver_schema(df, source)

    assert set(df.columns) == set(SILVER_COLUMNS)


def test_missing_column_is_rejected():
    df = make_fixture().drop(columns=["fixture_id"])

    with pytest.raises(ValueError, match="Missing Silver columns"):
        validate_silver_schema(df, "api_football")


def test_wrong_source_is_rejected():
    df = make_fixture("football_data")

    with pytest.raises(ValueError, match="Unexpected source"):
        validate_silver_schema(df, "api_football")


def test_duplicate_fixtures_are_rejected():
    df = pd.concat([make_fixture(), make_fixture()])

    with pytest.raises(ValueError, match="Duplicate fixture IDs"):
        validate_silver_schema(df, "api_football")


def test_empty_silver_is_rejected():
    df = make_fixture().iloc[0:0]

    with pytest.raises(ValueError, match="cannot be empty"):
        validate_silver_schema(df, "api_football")


def test_missing_date_is_rejected():
    df = make_fixture()
    df.loc[0, "date"] = pd.NaT

    with pytest.raises(ValueError, match="dates cannot be NULL"):
        validate_silver_schema(df, "api_football")
