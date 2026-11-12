BEGIN;

-- 1. Add provider identifier.
ALTER TABLE public.fixtures
ADD COLUMN IF NOT EXISTS source TEXT;

-- 2. Existing fixtures come from API-Football.
UPDATE public.fixtures
SET source = 'api_football'
WHERE source IS NULL;

-- 3. Require source for every fixture.
ALTER TABLE public.fixtures
ALTER COLUMN source SET NOT NULL;

-- 4. Replace the primary key only if necessary.
DO $$
DECLARE
    current_pk_columns TEXT[];
BEGIN
    SELECT array_agg(a.attname ORDER BY k.ordinality)
    INTO current_pk_columns
    FROM pg_constraint c
    JOIN unnest(c.conkey) WITH ORDINALITY AS k(attnum, ordinality)
        ON TRUE
    JOIN pg_attribute a
        ON a.attrelid = c.conrelid
       AND a.attnum = k.attnum
    WHERE c.conrelid = 'public.fixtures'::regclass
      AND c.contype = 'p';

    IF current_pk_columns IS DISTINCT FROM ARRAY['source', 'fixture_id'] THEN
        ALTER TABLE public.fixtures
        DROP CONSTRAINT IF EXISTS fixtures_pkey;

        ALTER TABLE public.fixtures
        ADD CONSTRAINT fixtures_pkey
        PRIMARY KEY (source, fixture_id);
    END IF;
END $$;

COMMIT;