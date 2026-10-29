
CREATE TABLE fixtures (
    fixture_id BIGINT PRIMARY KEY,
    date TIMESTAMPTZ,
    league_id INTEGER,
    season INTEGER,
    round TEXT,
    home_team_id INTEGER,
    home_team TEXT,
    away_team_id INTEGER,
    away_team TEXT,
    home_goals INTEGER,
    away_goals INTEGER,
    status TEXT
);

INSERT INTO fixtures (
    fixture_id,
    date,
    league_id,
    season,
    round,
    home_team_id,
    home_team,
    away_team_id,
    away_team,
    home_goals,
    away_goals,
    status
)
VALUES
    (1, '2023-08-01', 39, 2023, 'Round 1',
     101, 'Alpha FC', 102, 'Beta FC', 2, 1, 'FT'),

    (2, '2023-08-02', 39, 2023, 'Round 1',
     103, 'Gamma FC', 104, 'Delta FC', 0, 0, 'FT'),

    (3, '2023-08-03', 39, 2023, 'Round 2',
     102, 'Beta FC', 103, 'Gamma FC', 3, 1, 'FT'),

    (4, '2023-08-04', 39, 2023, 'Round 2',
     104, 'Delta FC', 101, 'Alpha FC', 1, 2, 'FT');
