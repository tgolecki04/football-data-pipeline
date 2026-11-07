from src.processing.transform_football_data import transform_matches


def test_transform_matches():
    data = {
        "matches": [
            {
                "id": 498613,
                "utcDate": "2024-08-15T17:00:00Z",
                "status": "FINISHED",
                "matchday": 1,
                "competition": {"id": 2014},
                "season": {"startDate": "2024-08-18"},
                "homeTeam": {"id": 77, "name": "Athletic Club"},
                "awayTeam": {"id": 82, "name": "Getafe CF"},
                "score": {
                    "fullTime": {"home": 1, "away": 1}
                },
            }
        ]
    }

    df = transform_matches(data)

    assert len(df) == 1
    assert df.iloc[0]["source"] == "football_data"
    assert df.iloc[0]["fixture_id"] == 498613
    assert df.iloc[0]["league_id"] == 2014
    assert df.iloc[0]["season"] == 2024
    assert df.iloc[0]["home_goals"] == 1
    assert df.iloc[0]["away_goals"] == 1
    assert df.iloc[0]["status"] == "FINISHED"