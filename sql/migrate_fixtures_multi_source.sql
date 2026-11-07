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

-- 4. Replace the old primary key.
ALTER TABLE public.fixtures
DROP CONSTRAINT fixtures_pkey;

ALTER TABLE public.fixtures
ADD CONSTRAINT fixtures_pkey
PRIMARY KEY (source, fixture_id);

COMMIT;