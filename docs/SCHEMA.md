# Database Schema (Supabase Postgres)

Project ref: `edfmsjiptksqhqfqptcc`. Introspected live on 2026-08-03.
Schema: `public`. **RLS is enabled on all tables** → the MCP server uses the service-role key.
An anon key returns 0 rows on every query, with no error — see docs/TESTING.md.

Only **two** tables exist and both are used: `locations` and `listings`.
There is **no `projects` table** — projects live in `locations` as rows with `level='project'`.
There is **no documents/embeddings table** and `pgvector` is not installed → RAG (US3) is greenfield.

> ⚠️ The table is **`listings`** (plural). An earlier snapshot of this dataset used `listing`
> (singular) with 1748 rows and text-typed numeric columns; that is no longer the case.
> Re-introspect rather than trusting either shape.

---

## `locations` — the place/project hierarchy (352 rows)
Self-referential tree. `id` is a text slug like `oh:amber-riverside`.

| column | type | notes |
|---|---|---|
| id | text | slug PK (no DB PK constraint declared) |
| level | text | `project` (57), `cluster` (87), `building` (208) |
| name | text | display name, e.g. "Amber Riverside" |
| name_norm | text | normalized name (useful for matching) |
| parent_id | text | → `locations.id` of the parent (NULL for projects) |
| project_id | text | → the owning project's id (NULL on project rows themselves) |
| province | text | e.g. "Hà Nội". NULL on ~9 project rows and ~11 clusters |
| district | text | e.g. "Hai Bà Trưng" |
| lat, lng | float8 | ⚠️ **projects only** (47/57). Always NULL on cluster and building rows |
| sources | jsonb | array of provenance tags |
| source_refs, attrs | jsonb | provenance / extra attributes |
| updated_at | timestamptz | last write |

**Hierarchy:** `project` (root, `parent_id` NULL) → `cluster` (optional) → `building` (leaf).
A building row carries `project_id` = its project's id.

**Province distribution (project rows):** Hà Nội 213, Hồ Chí Minh 63, Hưng Yên 35,
Hải Phòng 17, Long An 4 — counted across all levels; `list_provinces()` returns the 5 distinct
non-NULL values.

---

## `listings` — property listings (2355 rows)
The core sellable-unit table. `id` is text. **No PK constraint declared.**

| column | type | notes |
|---|---|---|
| id | text | listing id, e.g. `oh:TOFMRB` |
| source, source_listing_id, listing_code, url | text | provenance / link. `source` is `onehousing` throughout |
| title | text | listing title |
| location_id, project_id, cluster_id, building_id | text | → `locations.id` at each level. `building_id` NULL on ~18% of rows |
| property_type | text | see the table below |
| **area_m2** | **float8** | ✅ real numeric. 2207/2355 non-null |
| area_type | text | |
| **bedrooms**, **bathrooms**, **floor_num** | **int** | ✅ real numerics. `bedrooms` 2200/2355; `bathrooms` is sparse (~44%) |
| bedrooms_plus | bool | "N+" flag |
| floor_band | text | 1264/2355 non-null |
| direction_balcony, view | text | `view` sparse (~54%) |
| legal_status, furnishing, usage_status | text | |
| **price_vnd** | **bigint** | ✅ safe to filter/sort in SQL. 2331/2355 non-null |
| **price_per_m2_vnd** | **bigint** | ✅ safe. 2328/2355 non-null |
| price_type | text | `asking` throughout |
| status | text | ✅ clean `ĐANG BÁN` — no encoding corruption in this DB. No `active` value exists |
| comp_group | text | sparse (~6%) — comparison grouping |
| comp_one_to_one | bool | |
| lat, lng | float8 | present on **all 2355 rows** |
| geo_precision | text | |
| thumbnail | text | image url |
| images | jsonb | array of image urls |
| image_count | bigint | |
| raw | jsonb | full source payload — never returned to the agent |
| crawled_at, first_seen, last_seen | timestamptz | |

### `property_type` values

| value | rows | meaning |
|---|---:|---|
| `can_ho` | 2199 | apartment (dominant) |
| `lien_ke` | 83 | townhouse |
| `shophouse` | 48 | shophouse |
| `thuong_mai_dich_vu` | 11 | commercial / service |
| `biet_thu_song_lap` | 7 | semi-detached villa |
| `biet_thu_tu_lap` | 3 | quad villa |
| `biet_thu_don_lap` | 2 | detached villa |
| `nha_pho` | 1 | street house |
| *(NULL)* | 1 | |

Keep `tools/listings.py > PROPERTY_TYPES` in sync with this list — a value present in the data but
missing from that tuple makes `search_listings` reject a legitimate filter.

---

## Gotchas the tools MUST handle
1. **No `active` status** — don't filter on `status='active'` (returns nothing). The only value is
   `ĐANG BÁN`.
2. **`province` is not a column on `listings`** — to filter listings by province, resolve province →
   project ids via `locations` first, then filter `listings.project_id`.
3. **No FK constraints / no PKs declared** — joins are by convention on the text ids above.
4. **`locations.lat`/`lng` exist only on project rows.** Tools that return cluster or building nodes
   (`list_project_buildings`) always report `lat: null` / `lng: null`. Listing coordinates are
   complete, so `map_listings` is unaffected.
5. **Nullable numerics.** `price_vnd`, `area_m2`, and `bedrooms` are each NULL on 100–150 rows.
   Aggregates in `project_price_stats` already skip NULLs; new code must too.

### Note on `shaping.py`
`to_float` / `to_int` / `normalize_status` were written for an earlier snapshot where the numeric
columns were text and `status` was mojibake. Against this DB they are pass-throughs. They are kept
as defensive guards (they cost nothing on clean data), **but the workarounds built on top of them
are now unnecessary** — in particular `search_listings` filters `bedrooms` in Python with a
`limit * 3` over-fetch, which can silently under-return. Now that `bedrooms` is a real `int`, move
that filter into SQL.

---

## Available Postgres extensions (for phase 2)
> ⚠️ **Not verified against project `edfmsjiptksqhqfqptcc`** — this list was carried over from the
> earlier project's introspection. Confirm with `SELECT * FROM pg_extension;` (Supabase SQL Editor
> or the Supabase MCP) before planning phase-2 work on it.

Previously observed as installed: `pgcrypto`, `pg_stat_statements`, `supabase_vault`, `uuid-ossp`.
Available (not yet installed) and relevant: `vector` (pgvector — for RAG), `pg_trgm` +
`unaccent` (fuzzy Vietnamese name search), `pgroonga`/`rum` (full-text/BM25), `postgis`/`earthdistance`
(geo/radius), `pg_cron` (scheduled re-index).

## How to re-introspect
Use the Supabase MCP: `list_tables(project_id, verbose=true)` and `execute_sql(...)`, or query
through the app's own client:

```bash
set -a && . ./.env && set +a
./venv/bin/python -c "
from app.db import get_client
r = get_client().table('listings').select('*').limit(1).execute().data[0]
print(sorted(r))
"
```

Do **not** hardcode assumptions — re-verify after any migration, and update this file plus
`tests/conftest.py` (sample ids) when the data changes.
