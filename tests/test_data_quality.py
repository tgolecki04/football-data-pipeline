import pandas as pd
import pytest

from src.processing.data_quality import validate_fixtures


def test_valid_fixtures():
    df = pd.DataFrame(
        {
            "fixture_id": [1, 2],
            "status": ["FT", "FT"],
            "home_goals": [2, 0],
            "away_goals": [1, 0],
        }
    )

    validate_fixtures(df)


def test_duplicate_fixture_id():
    df = pd.DataFrame(
        {
            "fixture_id": [1, 1],
            "status": ["FT", "FT"],
            "home_goals": [2, 0],
            "away_goals": [1, 0],
        }
    )

    with pytest.raises(ValueError, match="Duplicate"):
        validate_fixtures(df)


def test_missing_fixture_id():
    df = pd.DataFrame(
        {
            "fixture_id": [1, None],
            "status": ["FT", "FT"],
            "home_goals": [2, 0],
            "away_goals": [1, 0],
        }
    )

    with pytest.raises(ValueError, match="identifier"):
        validate_fixtures(df)


def test_negative_goals():
    df = pd.DataFrame(
        {
            "fixture_id": [1],
            "status": ["FT"],
            "home_goals": [-1],
            "away_goals": [2],
        }
    )

    with pytest.raises(ValueError, match="Negative goals"):
        validate_fixtures(df)


def test_missing_final_score():
    df = pd.DataFrame(
        {
            "fixture_id": [1],
            "status": ["FT"],
            "home_goals": [None],
            "away_goals": [2],
        }
    )

    with pytest.raises(ValueError, match="Missing scores"):
        validate_fixtures(df)


def test_empty_dataframe():
    df = pd.DataFrame()

    with pytest.raises(ValueError, match="No matches"):
        validate_fixtures(df)