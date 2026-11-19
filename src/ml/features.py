import pandas as pd
import numpy as np
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

def build_match_features(team_matches: pd.DataFrame) -> pd.DataFrame:
    """Build one row per match with home and away form features.

    Expects the output of add_form_features(): two rows per match, one for
    the home team (is_home == 1) and one for the away team (is_home == 0).
    Matches where a team has no form yet (first match of a season) keep NaN
    and must be dropped before training.

    The target column `result` is H (home win), D (draw) or A (away win).
    Goals are not returned, so they cannot leak into the model by accident.
    """
    home = team_matches[team_matches["is_home"] == 1][
        ["fixture_id", "date", "season", "team_id", "score", "form_points"]
    ].rename(
        columns={
            "team_id": "home_team_id",
            "score": "home_goals",
            "form_points": "home_form_points",
        }
    )

    away = team_matches[team_matches["is_home"] == 0][
        ["fixture_id", "team_id", "score", "form_points"]
    ].rename(
        columns={
            "team_id": "away_team_id",
            "score": "away_goals",
            "form_points": "away_form_points",
        }
    )

    matches = home.merge(away, on="fixture_id", validate="one_to_one")

    matches["result"] = np.select(
        [
            matches["home_goals"] > matches["away_goals"],
            matches["home_goals"] < matches["away_goals"],
        ],
        ["H", "A"],
        default="D",
    )

    matches = matches.drop(columns=["home_goals", "away_goals"])

    return matches.sort_values("date", ignore_index=True)