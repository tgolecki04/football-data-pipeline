
-- Check 1: Duplicate fixture IDs.
SELECT
    'duplicate_fixture_ids' AS check_name,
    COUNT(*) - COUNT(DISTINCT fixture_id) AS failures
FROM fixtures;

-- Check 2: Finished fixtures must have valid scores.
SELECT
    'invalid_finished_fixtures' AS check_name,
    COUNT(*) AS failures
FROM fixtures
WHERE status IN ('FT', 'AET', 'PEN')
  AND (
      home_goals IS NULL
      OR away_goals IS NULL
      OR home_goals < 0
      OR away_goals < 0
  );

-- Check 3: Team statistics must be internally consistent.
SELECT
    'inconsistent_team_stats' AS check_name,
    COUNT(*) AS failures
FROM gold_team_stats
WHERE played <> wins + draws + losses
   OR points <> wins * 3 + draws
   OR goal_difference <> goals_for - goals_against;

-- Check 4: Teams must have valid identifiers.
SELECT
    'invalid_team_identifiers' AS check_name,
    COUNT(*) AS failures
FROM gold_team_stats
WHERE team_id IS NULL
   OR team_name IS NULL;
