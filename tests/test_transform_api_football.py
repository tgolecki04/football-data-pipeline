
"""Unit tests for API-Football Bronze-to-Silver transformation."""

import pandas as pd
import pytest

from src.processing.transform_api_football import transform_matches
from src.processing.silver_schema import validate_silver_schema


def make_bronze():
    return {
        "response": [
            {
                "fixture": {
                    "id": 101,
                    "date": "2023-08-12T15:00:00+00:00",
                    "status": {"short": "FT"},
                },
                "league": {
                    "id": 39,
                    "season": 2023,
                    "round": "Regular Season - 1",
                },
                "teams": {
                    "home": {"id": 1, "name": "Team A"},
                    "away": {"id": 2, "name": "Team B"},
                },
                "goals": {
                    "home": 2,
                    "away": 1,
                },
            }
        ]
    }


def test_transform_api_football():
    df = transform_matches(make_bronze())

    assert len(df) == 1
    assert df.iloc[0]["source"] == "api_football"
    assert df.iloc[0]["fixture_id"] == 101
    assert df.iloc[0]["home_goals"] == 2
    assert df.iloc[0]["away_goals"] == 1
    assert isinstance(df["date"].dtype, pd.DatetimeTZDtype)
    assert str(df["date"].dt.tz) == "UTC"

    validate_silver_schema(df, "api_football")


def test_empty_response_is_rejected():
    with pytest.raises(ValueError, match="No API-Football matches"):
        transform_matches({"response": []})


def test_duplicate_fixtures_are_deduplicated():
    bronze = make_bronze()
    bronze["response"].append(bronze["response"][0].copy())

    df = transform_matches(bronze)

    assert len(df) == 1
    assert df["fixture_id"].tolist() == [101]


def test_unplayed_fixture_has_null_scores():
    bronze = make_bronze()
    match = bronze["response"][0]

    match["fixture"]["status"]["short"] = "NS"
    match["goals"] = {"home": None, "away": None}

    df = transform_matches(bronze)

    assert pd.isna(df.iloc[0]["home_goals"])
    assert pd.isna(df.iloc[0]["away_goals"])

    validate_silver_schema(df, "api_football")
