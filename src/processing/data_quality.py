import pandas as pd


def validate_fixtures(df: pd.DataFrame) -> None:
    if df.empty:
        raise ValueError("No matches found")

    if df["fixture_id"].isna().any():
        raise ValueError("Missing fixture identifier")

    if df["fixture_id"].duplicated().any():
        raise ValueError("Duplicate matches found")

    finished = df[
        df["status"].isin(["FT", "AET", "PEN", "FINISHED"])
    ]   

    if finished["home_goals"].isna().any() or finished["away_goals"].isna().any():
        raise ValueError("Missing scores for finished matches")

    for column in ["home_goals", "away_goals"]:
        if (df[column].dropna() < 0).any():
            raise ValueError(f"Negative goals in column: {column}")
        
    if "source" in df.columns:
        if df["source"].isna().any():
            raise ValueError("Missing data source")

        if not df["source"].isin(
            ["api_football", "football_data"]
        ).all():
            raise ValueError("Unknown data source")