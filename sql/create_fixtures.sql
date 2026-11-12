CREATE TABLE IF NOT EXISTS public.fixtures (
    source TEXT NOT NULL,
    fixture_id BIGINT NOT NULL,
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
    status TEXT,
    PRIMARY KEY (source, fixture_id)
);