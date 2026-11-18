
"""Tests for safe replacement of league-season fixtures."""

from unittest.mock import Mock

import pandas as pd
import pytest

from src.warehouse.load_guard import validate_replacement


SOURCE = "api_football"
LEAGUE_ID = 39
SEASON = 2023


def make_silver(ids, league_id=LEAGUE_ID, season=SEASON):
    """Create a small, synthetic Silver dataset."""
    return pd.DataFrame({
        "source": [SOURCE] * len(ids),
        "fixture_id": ids,
        "league_id": [league_id] * len(ids),
        "season": [season] * len(ids),
    })


def make_cursor(existing_ids):
    """Simulate fixture IDs returned from PostgreSQL."""
    cursor = Mock()
    cursor.fetchall.return_value = [
        (fixture_id,) for fixture_id in existing_ids
    ]
    return cursor


def test_first_load_is_allowed():
    df = make_silver([101, 102])
    cursor = make_cursor([])

    validate_replacement(
        cursor, df, SOURCE, LEAGUE_ID, SEASON
    )

    cursor.execute.assert_called_once()


def test_reloading_same_fixtures_is_allowed():
    df = make_silver([101, 102, 103])
    cursor = make_cursor([101, 102, 103])

    validate_replacement(
        cursor, df, SOURCE, LEAGUE_ID, SEASON
    )


def test_adding_new_fixtures_is_allowed():
    df = make_silver([101, 102, 103, 104])
    cursor = make_cursor([101, 102])

    validate_replacement(
        cursor, df, SOURCE, LEAGUE_ID, SEASON
    )


def test_incomplete_season_is_blocked():
    existing_ids = list(range(1, 381))
    incoming_ids = list(range(1, 26))

    df = make_silver(incoming_ids)
    cursor = make_cursor(existing_ids)

    with pytest.raises(
        ValueError, match="Unsafe replacement blocked"
    ):
        validate_replacement(
            cursor, df, SOURCE, LEAGUE_ID, SEASON
        )


def test_duplicate_fixture_ids_are_blocked():
    df = make_silver([101, 101, 102])
    cursor = make_cursor([])

    with pytest.raises(
        ValueError, match="duplicate fixture IDs"
    ):
        validate_replacement(
            cursor, df, SOURCE, LEAGUE_ID, SEASON
        )

    cursor.execute.assert_not_called()


def test_wrong_league_is_blocked():
    df = make_silver([101, 102], league_id=140)
    cursor = make_cursor([])

    with pytest.raises(
        ValueError, match="another league"
    ):
        validate_replacement(
            cursor, df, SOURCE, LEAGUE_ID, SEASON
        )

    cursor.execute.assert_not_called()


def test_wrong_season_is_blocked():
    df = make_silver([101, 102], season=2022)
    cursor = make_cursor([])

    with pytest.raises(
        ValueError, match="another season"
    ):
        validate_replacement(
            cursor, df, SOURCE, LEAGUE_ID, SEASON
        )

    cursor.execute.assert_not_called()


def test_empty_silver_is_blocked():
    df = make_silver([])
    cursor = make_cursor([])

    with pytest.raises(
        ValueError, match="empty Silver"
    ):
        validate_replacement(
            cursor, df, SOURCE, LEAGUE_ID, SEASON
        )

    cursor.execute.assert_not_called()


def test_missing_fixture_ids_are_blocked():
    df = make_silver([101, None])
    cursor = make_cursor([])

    with pytest.raises(
        ValueError, match="NULL fixture IDs"
    ):
        validate_replacement(
            cursor, df, SOURCE, LEAGUE_ID, SEASON
        )

    cursor.execute.assert_not_called()


def test_wrong_source_is_blocked():
    df = make_silver([101, 102])
    df["source"] = "football_data"
    cursor = make_cursor([])

    with pytest.raises(
        ValueError, match="another source"
    ):
        validate_replacement(
            cursor, df, SOURCE, LEAGUE_ID, SEASON
        )

    cursor.execute.assert_not_called()
