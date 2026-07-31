# Database Schema (Supabase Postgres)

Project ref: `etmrjxsxwsecvwvexvbq`. Introspected live on 2026-07-31.
Schema: `public`. **RLS is enabled on all tables** → the MCP server uses the service-role key.

There is **no `projects` table**. Projects live in `locations` as rows with `level='project'`.
There is **no documents/embeddings table** and `pgvector` is not installed → RAG (US3) is greenfield.

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
| province | text | e.g. "Hà Nội" |
| district | text | e.g. "Hai Bà Trưng" |
| lat, lng | float8 | coordinates |
| sources, source_refs, attrs | jsonb | provenance / extra attributes |

**Hierarchy:** `project` (root, parent_id NULL) → `cluster` (optional) → `building` (leaf).
A building row carries `project_id` = its project's id.

---

## `listing` — property listings (1748 rows)
The core sellable-unit table. `id` is text. **No PK constraint declared.**

| column | type | notes |
|---|---|---|
| id | text | listing id |
| source, source_listing_id, listing_code, url | text | provenance / link |
| title | text | listing title |
| location_id, project_id, cluster_id, building_id | text | → `locations.id` at each level |
| property_type | text | `can_ho` (1646), `lien_ke` (55), `shophouse` (32), `thuong_mai_dich_vu` (7), `biet_thu_*` (few) |
| **area_m2** | **text** | ⚠️ numeric stored as text — coerce before use |
| area_type | text | |
| **bedrooms**, **bathrooms**, **floor_num** | **text** | ⚠️ numeric stored as text |
| bedrooms_plus | bool | "N+" flag |
| floor_band, direction_balcony, view | text | |
| legal_status, furnishing, usage_status | text | |
| **price_vnd** | **bigint** | ✅ safe to filter/sort in SQL (1725/1748 non-null) |
| **price_per_m2_vnd** | **bigint** | ✅ safe |
| price_type | text | |
| status | text | ⚠️ `ĐANG BÁN` **and** an encoding-corrupted duplicate; no `active` value exists |
| comp_group, comp_one_to_one | text/bool | comparison grouping |
| lat, lng | float8 | present on all 1748 rows |
| geo_precision | text | |
| thumbnail | text | image url |
| images | jsonb | array of image urls |
| image_count | bigint | |
| raw | jsonb | full source payload |
| crawled_at, first_seen, last_seen | timestamptz | |

---

## `dashboard_readings` (69k rows)
Telemetry/metrics table (param_name/value time series). **Not relevant** to the real-estate tools;
ignore it for this project.

---

## Gotchas the tools MUST handle (already handled in `shaping.py`)
1. **Text-typed numbers** (`area_m2`, `bedrooms`, `bathrooms`, `floor_num`): coerce with
   `shaping.to_float` / `to_int`. You cannot range-filter these in PostgREST without a cast, so
   `search_listings` filters `bedrooms` in Python after fetch. `price_vnd`/`price_per_m2_vnd` are
   real bigints → filter/sort them in SQL.
2. **`status` mojibake**: normalize with `shaping.normalize_status` → canonical `ĐANG BÁN`.
3. **No `active` status** — don't filter on `status='active'` (returns nothing).
4. **`province` is not a column on `listing`** — to filter listings by province, resolve province →
   project ids via `locations` first, then filter `listing.project_id`.
5. **No FK constraints / no PKs declared** — joins are by convention on the text ids above.

## Available Postgres extensions (for phase 2)
Installed: `pgcrypto`, `pg_stat_statements`, `supabase_vault`, `uuid-ossp`.
Available (not yet installed) and relevant: `vector` (pgvector 0.8 — for RAG), `pg_trgm` +
`unaccent` (fuzzy Vietnamese name search), `pgroonga`/`rum` (full-text/BM25), `postgis`/`earthdistance`
(geo/radius), `pg_cron` (scheduled re-index).

## How to re-introspect
Use the Supabase MCP: `list_tables(project_id, verbose=true)` and `execute_sql(...)`.
Do **not** hardcode assumptions — re-verify after any migration.
