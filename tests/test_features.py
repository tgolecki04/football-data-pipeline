import pandas as pd 

from src.ml.features import to_team_matches

def test_to_team_matches_returns_two_row_per_matches():

    fixtures = pd.DataFrame(
        {
        "fixture_id": [1, 2, 3],
        "date": pd.to_datetime(["2022-08-05", "2022-08-12","2022-08-13"], utc=True),
        "season": [2022, 2022, 2022],
        "home_team_id": [10, 30, 20],
        "away_team_id": [20, 10, 30],
        "home_goals": [2, 1, 2],
        "away_goals": [1, 1, 2],
        "status": ["FT", "FT","NS"],
    })

    result = to_team_matches(fixtures)

    assert len(result) == 4
    assert 3 not in result["fixture_id"].values

    team_10_match_1 = result[(result["fixture_id"] == 1) & (result["team_id"] == 10)].iloc[0]
    assert team_10_match_1["points"] == 3

    team_10_match_2 = result[(result["fixture_id"] == 2) & (result["team_id"] == 10)].iloc[0]
    assert team_10_match_2["points"] == 1