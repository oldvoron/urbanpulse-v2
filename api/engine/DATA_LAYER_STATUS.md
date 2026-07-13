# Data-layer optimization audit (Addendum 2 §2)

Audited 2026-07-12 against the live code in `api/engine/` (greps + a measured
full-city run). Status per item:

## 1. Composite Overpass queries — ✅ confirmed implemented
- `fetch_transport_data`: roads + transit stops + cycling = **1** union query
  (was 6 tag-group calls in v1).
- `fetch_nature_data`: green + water + flood-proxy waterways = **1** union
  query (was 7).
- `fetch_osm_landuse`: landuse + leisure + natural = **1** union query (was 3).
- `fetch_admin_boundaries`: both admin levels = **1** bbox query (was 2
  polygon queries).
- Buildings keep the v1 progressive tag-fallback loop *by design* — it costs
  1 call on the happy path and only retries with relaxed tags after a failure.
- **Measured** (Blois, full city, cold cache): `[pipeline] Overpass calls this
  analysis: 5` after boundary fetch (+1 admin composite before the counter
  reset) → **~6 total vs ~17–20 in the v1 pattern**. Counter:
  `data.get_overpass_call_count()`, logged by `pipeline.py` on every run.

## 2. Bbox-only, never polygon — ✅ confirmed implemented
- `features_from_place` / `graph_from_place` appear **only in comments**.
- `_osm_features()` geocodes to a bbox when none is supplied and always calls
  `features_from_bbox`; the street network uses `graph_from_bbox` (fallback:
  `graph_from_point`, also non-polygon).
- Note: `ox.geocode_to_gdf`/`ox.geocode` calls are **Nominatim** (geocoding),
  not Overpass — bbox rules don't apply to them.

## 3. `max_query_area_size` — ✅ confirmed implemented
- `configure_osmnx()` sets `2_500_000_000` (vs 25e9 default); re-asserted in
  `fetch_osm_data` before the network fetch. No later edit reverted it.

## 4. Retry/mirror behavior + semaphore — ✅ confirmed implemented
- 5-mirror `OVERPASS_MIRRORS` list; `max_retries=1` per mirror (moves to the
  next mirror instead of waiting in place).
- `_OVERPASS_SEMAPHORE = threading.Semaphore(2)` acquired **around the actual
  fetch call** inside `osmnx_fetch_with_retry` (`with _OVERPASS_SEMAPHORE:
  fetch_func()`), and **every** Overpass call site routes through
  `osmnx_fetch_with_retry` (verified by grep: `features_from_bbox`,
  `graph_from_bbox`, `graph_from_point` in `data.py` and `districts.py`).
- Caveat (accepted, inherited from v1): osmnx may split one logical fetch into
  several internal HTTP sub-requests; the semaphore caps concurrent *logical
  fetches* at 2, which bounds sub-request concurrency to 2 groups.

## 5. `city_cache` read-before-fetch — ✅ confirmed implemented
- `pipeline.run_full_analysis` step 2: cache read happens **before any live
  fetch**; only layers missing from the cached blob are fetched
  (`_run_parallel_fetches(..., layers=missing)`), and a successful live fetch
  writes back. Covers all six layers: poi / osm(graph+buildings) / landuse /
  transport / nature / terrain.
- **Measured**: repeat Blois analysis logs `All layers served from city_cache
  — 0 live fetches` and completes in ~31 s vs ~320 s cold.
- District lists are cached separately under `"{city}:districts"`.
- TTL enforced on read (`CITY_CACHE_TTL_DAYS`, default 60); bbox mismatch →
  treated as miss.

**Conclusion**: nothing from the agreed plan regressed or was left
conversation-only; no re-implementation work needed. (This file is the §2
deliverable; keep it updated if the fetch layer changes.)
