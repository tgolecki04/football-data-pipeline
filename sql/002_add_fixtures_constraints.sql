-- Migration 002: Improve fixtures data integrity.
-- Safe to rerun: checks are added only when missing.

BEGIN;

-- Required fixture attributes.
ALTER TABLE public.fixtures
    ALTER COLUMN date SET NOT NULL,
    ALTER COLUMN league_id SET NOT NULL,
    ALTER COLUMN season SET NOT NULL,
    ALTER COLUMN home_team_id SET NOT NULL,
    ALTER COLUMN away_team_id SET NOT NULL,
    ALTER COLUMN status SET NOT NULL;

-- Prevent invalid identifiers and scores.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'public.fixtures'::regclass
          AND conname = 'fixtures_valid_values'
    ) THEN
        ALTER TABLE public.fixtures
        ADD CONSTRAINT fixtures_valid_values
        CHECK (
            fixture_id > 0
            AND league_id > 0
            AND season > 0
            AND home_team_id > 0
            AND away_team_id > 0
            AND home_team_id <> away_team_id
            AND TRIM(status) <> ''
            AND (home_goals IS NULL OR home_goals >= 0)
            AND (away_goals IS NULL OR away_goals >= 0)
        );
    END IF;
END $$;

-- Finished fixtures must have scores.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'public.fixtures'::regclass
          AND conname = 'fixtures_finished_scores'
    ) THEN
        ALTER TABLE public.fixtures
        ADD CONSTRAINT fixtures_finished_scores
        CHECK (
            status NOT IN ('FT', 'AET', 'PEN', 'FINISHED')
            OR (home_goals IS NOT NULL AND away_goals IS NOT NULL)
        );
    END IF;
END $$;

COMMIT;