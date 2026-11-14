import pandas as pd

FINISHED_STATUSES = ("FT", "AET", "PEN")

def to_team_matches(fixtures: pd.DataFrame) -> pd.DataFrame:
    """Convert fixtures to team matches."""

    finished = fixtures[fixtures["status"].isin(FINISHED_STATUSES)] 

    home_matches = finished[["fixture_id","home_team_id","date", "home_goals", "away_goals","season"]].copy()
    home_matches["is_home"] = 1
    home_matches.rename(columns={"home_team_id": "team_id", "home_goals": "score", "away_goals": "opponent_score"}, inplace=True)
    
    away_matches = finished[["fixture_id","away_team_id","date", "away_goals", "home_goals","season"]].copy()
    away_matches["is_home"] = 0
    away_matches.rename(columns={"away_team_id": "team_id", "away_goals": "score", "home_goals": "opponent_score"}, inplace=True)

    team_matches = pd.concat([home_matches, away_matches], ignore_index=True)
    team_matches["points"] = team_matches.apply(lambda row: 3 if row["score"] > row["opponent_score"] else (1 if row["score"] == row["opponent_score"] else 0), axis=1)
    team_matches.sort_values(by=["team_id", "date"], inplace=True, ignore_index=True)

    return team_matches

def add_form_features(team_matches: pd.DataFrame) -> pd.DataFrame:

    result = team_matches.copy()

    result["form_points"] = (
    result.groupby(["team_id", "season"])["points"]
    .transform(lambda s: s.shift(1).rolling(5, min_periods=1).mean())
    )

    return result
