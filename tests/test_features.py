import pandas as pd 
import pytest

from src.ml.features import to_team_matches, add_form_features, build_match_features


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


def test_form_points_ignores_current_match():

    team_matches =  pd.DataFrame({
        "team_id": [1,1,1],
        "date": pd.to_datetime(["2022-08-01", "2022-08-08", "2022-08-15"]),
        "points": [3,0,1],
        "season": [2022, 2022, 2022]
    })

    result = add_form_features(team_matches)

    assert pd.isna(result.loc[0,"form_points"])
    assert result.loc[1, "form_points"] == 3
    assert result.loc[2, "form_points"] == pytest.approx(1.5)


def test_build_match_features_returns_one_row_per_match():
    team_matches = pd.DataFrame(
        {
            "fixture_id": [1, 1, 2, 2],
            "date": pd.to_datetime(
                ["2022-08-05", "2022-08-05", "2022-08-12", "2022-08-12"]
            ),
            "season": [2022, 2022, 2022, 2022],
            "team_id": [10, 20, 30, 10],
            "is_home": [1, 0, 1, 0],
            "score": [2, 1, 1, 1],
            "form_points": [None, None, 2.0, 3.0],
        }
    )

    result = build_match_features(team_matches)

    assert len(result) == 2

    match_1 = result[result["fixture_id"] == 1].iloc[0]
    assert match_1["result"] == "H"

    match_2 = result[result["fixture_id"] == 2].iloc[0]
    assert match_2["home_team_id"] == 30
    assert match_2["away_team_id"] == 10
    assert match_2["home_form_points"] == 2.0
    assert match_2["away_form_points"] == 3.0
    assert match_2["result"] == "D"

    assert "home_goals" not in result.columns