-- 001 — Fuzzy project search (US1 "harden" item in docs/TOOLS_TODO.md)
--
-- Run this in the Supabase SQL Editor (Dashboard > SQL Editor) before deploying the matching
-- app code: `services/locations.search_projects` calls the function defined here and will fail
-- with "Could not find the function public.search_projects_fuzzy" without it.
--
-- Why a function instead of a PostgREST query: pg_trgm's similarity operators are not
-- expressible in a PostgREST query string, and combining them with ILIKE needs an OR group
-- that PostgREST cannot build safely from user input.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Speeds up both word_similarity() and the ILIKE '%...%' branches below, which would otherwise
-- sequential-scan the table.
CREATE INDEX IF NOT EXISTS locations_name_norm_trgm
  ON locations USING gin (name_norm gin_trgm_ops);


-- Match on three widening levels, ranked by trigram score:
--   1. name      ILIKE %q%        -> accented input, as typed
--   2. name_norm ILIKE %q_folded% -> accent-folded input ("chung cu" finds "Chung cư ...")
--   3. word_similarity >= min_score -> typos ("vinhoms" finds "Vinhomes ...")
--
-- word_similarity (not similarity): plain similarity() penalises length mismatch, so a short
-- query like 'vinhomes' scores poorly against 'vinhomes ocean park 2' even though it is an
-- obvious match. word_similarity asks "does the query match some run of words in the target".
--
-- min_score 0.55 was picked by measuring real data: 'vinhoms'/'vinhomse' score above it,
-- unrelated strings ('xyzabc') score below. Re-measure before changing it.
CREATE OR REPLACE FUNCTION search_projects_fuzzy(
  q          text,
  q_folded   text,
  lim        int   DEFAULT 10,
  min_score  real  DEFAULT 0.55,
  prov       text  DEFAULT NULL
)
RETURNS SETOF locations
LANGUAGE sql STABLE AS $$
  SELECT *
  FROM locations
  WHERE level = 'project'
    AND (prov IS NULL OR province ILIKE '%' || prov || '%')
    AND (
      q_folded = ''                                        -- province-only search
      OR name      ILIKE '%' || q || '%'
      OR name_norm ILIKE '%' || q_folded || '%'
      OR word_similarity(q_folded, name_norm) >= min_score
    )
  ORDER BY
    word_similarity(q_folded, name_norm) DESC,
    name
  LIMIT lim;
$$;

-- Sanity checks — expected: 22 rows, 2 rows, Vinhomes rows, 0 rows.
--   SELECT count(*) FROM search_projects_fuzzy('Vinhomes', 'vinhomes', 100);
--   SELECT name     FROM search_projects_fuzzy('chung cu', 'chung cu', 10);
--   SELECT name     FROM search_projects_fuzzy('vinhoms',  'vinhoms',  5);
--   SELECT count(*) FROM search_projects_fuzzy('xyzabc',   'xyzabc',   5);
