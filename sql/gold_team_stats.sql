
CREATE OR REPLACE VIEW gold_team_stats AS

WITH team_matches AS (

    -- Mecze z perspektywy gospodarzy
    SELECT
        season,
        league_id,
        home_team_id AS team_id,
        home_team AS team_name,
        home_goals AS goals_for,
        away_goals AS goals_against
    FROM fixtures
    WHERE status IN ('FT', 'AET', 'PEN')
      AND home_goals IS NOT NULL
      AND away_goals IS NOT NULL

    UNION ALL

    -- Mecze z perspektywy gości
    SELECT
        season,
        league_id,
        away_team_id AS team_id,
        away_team AS team_name,
        away_goals AS goals_for,
        home_goals AS goals_against
    FROM fixtures
    WHERE status IN ('FT', 'AET', 'PEN')
      AND home_goals IS NOT NULL
      AND away_goals IS NOT NULL
)

SELECT
    season,
    league_id,
    team_id,
    MAX(team_name) AS team_name,

    COUNT(*) AS played,

    COUNT(*) FILTER (
        WHERE goals_for > goals_against
    ) AS wins,

    COUNT(*) FILTER (
        WHERE goals_for = goals_against
    ) AS draws,

    COUNT(*) FILTER (
        WHERE goals_for < goals_against
    ) AS losses,

    SUM(goals_for) AS goals_for,
    SUM(goals_against) AS goals_against,

    SUM(goals_for - goals_against) AS goal_difference,

    (
        COUNT(*) FILTER (
            WHERE goals_for > goals_against
        ) * 3
        +
        COUNT(*) FILTER (
            WHERE goals_for = goals_against
        )
    ) AS points

FROM team_matches

GROUP BY
    season,
    league_id,
    team_id;
