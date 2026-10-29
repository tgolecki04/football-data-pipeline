
CREATE OR REPLACE VIEW gold_team_recent_form AS

WITH team_matches AS (
    -- Home team perspective
    SELECT
        fixture_id,
        date,
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

    -- Away team perspective
    SELECT
        fixture_id,
        date,
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
),

ranked_matches AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY league_id, season, team_id
            ORDER BY date DESC, fixture_id DESC
        ) AS match_rank
    FROM team_matches
),

recent_matches AS (
    SELECT *
    FROM ranked_matches
    WHERE match_rank <= 5
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

FROM recent_matches

GROUP BY
    season,
    league_id,
    team_id;
