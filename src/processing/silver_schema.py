
"""Shared Silver fixtures schema for all data providers."""

import pandas as pd


SILVER_COLUMNS = (
    "source",
    "fixture_id",
    "date",
    "league_id",
    "season",
    "round",
    "home_team_id",
    "home_team",
    "away_team_id",
    "away_team",
    "home_goals",
    "away_goals",
    "status",
)

SUPPORTED_SOURCES = {
    "api_football",
    "football_data",
}


def validate_silver_schema(df: pd.DataFrame, source: str) -> None:
    """Validate the common structure before writing or loading Silver."""

    if source not in SUPPORTED_SOURCES:
        raise ValueError(f"Unsupported source: {source}")

    missing_columns = set(SILVER_COLUMNS) - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing Silver columns: {sorted(missing_columns)}"
        )

    if df.empty:
        raise ValueError("Silver fixtures cannot be empty.")

    if not df["source"].eq(source).all():
        raise ValueError("Unexpected source in Silver fixtures.")

    if df["fixture_id"].isna().any():
        raise ValueError("Fixture IDs cannot be NULL.")

    if df.duplicated(subset=["source", "fixture_id"]).any():
        raise ValueError("Duplicate fixture IDs in Silver.")

    if df["date"].isna().any():
        raise ValueError("Fixture dates cannot be NULL.")

    if df["league_id"].isna().any():
        raise ValueError("League IDs cannot be NULL.")

    if df["season"].isna().any():
        raise ValueError("Seasons cannot be NULL.")

    for column in ("home_team_id", "away_team_id"):
        if df[column].isna().any():
            raise ValueError(f"{column} cannot be NULL.")

    if df["status"].isna().any():
        raise ValueError("Fixture status cannot be NULL.")

    if df["status"].astype(str).str.strip().eq("").any():
        raise ValueError("Fixture status cannot be empty.")
