"""
Framework-independent analysis pipeline for Urban Pulse v2.

This is the orchestration logic extracted from the v1 Streamlit ``app.py``:
``get_analysis_bbox``, ``clip_to_city``, ``safe_merge``, ``has_data``,
``_has_cols``, ``_run_parallel_fetches`` and the full sequential
post-processing block that ran between the parallel fetch and the tab
rendering. Nothing here changes what any of those functions compute — this
was a mechanical extraction. There is no Streamlit import anywhere in this
module's call chain; Streamlit session-state reads/writes were replaced by
plain local variables.

Entry point:

    run_full_analysis(city_name: str, config: dict) -> dict

``config`` keys (all optional; defaults applied):
    city_size            "Small (< 100k)" | "Medium (100k–500k)" | "Large (500k+)"
    zone_mode            "Entire city" | "Select district" | "Draw custom bbox"
    selected_district    district name (used with "Select district")
    custom_bbox          (min_lon, min_lat, max_lon, max_lat) (used with "Draw custom bbox")
    morphology, transport, nature, terrain, climate,
    stress_index, fabric_typology, cross_analysis   — module toggles (bool),
                         same semantics as the v1 sidebar "Analysis Modules"
    ai                   bool — generate AI insights when ANTHROPIC_API_KEY is set

Returns a plain dict of everything the frontend needs — ``metrics_summary``,
per-tab scalar readouts, every chart figure (as Plotly JSON specs) for the
nine v1 tabs, district scores, warnings — ready to be JSON-serialized.
Non-JSON geodata needed by the export endpoints is returned separately under
the ``"artifacts"`` key (the API layer keeps it out of the DB row).
"""

import gc
import json
import os
import concurrent.futures
from math import radians, cos

import pandas as pd
import geopandas as gpd

from .data import (
    fetch_overture_pois, fetch_osm_data, fetch_osm_landuse,
    fetch_transport_data, fetch_nature_data, fetch_terrain_data,
    fetch_admin_boundaries, fetch_climate_data,
    get_city_polygon,
)
from .metrics import (
    poi_category_distribution,
    building_height_stats,
    land_use_diversity,
    street_network_stats,
    compute_morphological_index,
    landuse_composition,
    transport_accessibility_index,
    nature_accessibility_index,
    landuse_transport_crossref,
    compute_urban_stress_index,
    compute_fabric_typology,
    compute_temporal_vulnerability,
    compute_segregation_proxy,
    sample_terrain_for_hexes,
    compute_district_scores,
    compute_heat_island_proxy,
    create_hex_grid_from_bbox,
    create_hex_grid_from_pois,
    _resolve_heights,
)
from . import charts as ch
from .charts import add_admin_boundaries_to_fig


# ── Size configs (v1 sidebar "City size") ─────────────────────────────────────

SIZE_CONFIGS = {
    "Small (< 100k)": {
        "overture_limit": 5000,
        "building_limit": 15000,
        "network_dist": 3000,
        "hex_resolution": 9,
        "terrain_grid": 15,
        "road_tags": ['primary', 'secondary', 'tertiary'],
    },
    "Medium (100k–500k)": {
        "overture_limit": 15000,
        "building_limit": 25000,
        "network_dist": 5000,
        "hex_resolution": 9,
        "terrain_grid": 20,
        "road_tags": ['primary', 'secondary', 'tertiary'],
    },
    "Large (500k+)": {
        "overture_limit": 30000,
        "building_limit": 40000,
        "network_dist": 8000,
        "hex_resolution": 8,
        "terrain_grid": 20,
        "road_tags": ['primary', 'secondary'],
    },
}

DEFAULT_MODULES = {
    "morphology": True,
    "transport": True,
    "nature": True,
    "terrain": True,
    "climate": True,
    "stress_index": True,
    "fabric_typology": True,
    "cross_analysis": True,
    "ai": True,
}

MAX_ENTIRE_CITY_AREA_KM2 = 800


class AnalysisError(Exception):
    """User-facing pipeline failure (v1's st.error + st.stop)."""


# ── Helpers extracted verbatim from v1 app.py ─────────────────────────────────

def _has_cols(gdf, *cols, min_rows: int = 10) -> bool:
    if gdf is None or gdf.empty or len(gdf) < min_rows:
        return False
    return all(c in gdf.columns for c in cols)


def has_data(df_or_gdf, min_rows=3, required_cols=None):
    """Check if dataframe has enough data to plot."""
    if df_or_gdf is None:
        return False
    if hasattr(df_or_gdf, 'empty') and df_or_gdf.empty:
        return False
    if len(df_or_gdf) < min_rows:
        return False
    if required_cols:
        for col in required_cols:
            if col not in df_or_gdf.columns:
                return False
            if df_or_gdf[col].isna().all():
                return False
    return True


def safe_merge(base, other, on: str = "h3_cell", how: str = "left"):
    if base is None or (hasattr(base, "empty") and base.empty):
        return base
    if other is None or (hasattr(other, "empty") and other.empty):
        return base
    if on not in base.columns or on not in other.columns:
        return base
    try:
        return base.merge(other, on=on, how=how, suffixes=("", "_dup"))
    except Exception:
        return base


def get_analysis_bbox(city_name, zone_mode, selected_district, admin_boundaries, custom_bbox):
    """Return (min_lon, min_lat, max_lon, max_lat) for the active zone selection."""
    if zone_mode == "Draw custom bbox" and custom_bbox and all(v != 0.0 for v in custom_bbox):
        return tuple(custom_bbox)
    if zone_mode == "Select district" and selected_district != "All":
        for level in ['admin_9', 'admin_10']:
            gdf = (admin_boundaries or {}).get(level)
            if gdf is not None and not gdf.empty:
                match = gdf[gdf['admin_name'] == selected_district]
                if not match.empty:
                    b = match.total_bounds
                    return (b[0], b[1], b[2], b[3])
    # Reuse the city boundary already fetched in fetch_admin_boundaries()
    # instead of issuing a second, unprotected geocode request.
    city_gdf = (admin_boundaries or {}).get("city")
    if city_gdf is not None and not city_gdf.empty:
        b = city_gdf.total_bounds
        return (b[0], b[1], b[2], b[3])
    return None


def bbox_area_km2(bbox):
    """Approximate area of a (min_lon, min_lat, max_lon, max_lat) bbox in km²."""
    min_lon, min_lat, max_lon, max_lat = bbox
    lat_km = (max_lat - min_lat) * 111
    lon_km = (max_lon - min_lon) * 111 * cos(radians((min_lat + max_lat) / 2))
    return abs(lat_km * lon_km)


def clip_to_city(data, city_polygon):
    """
    Clip a GeoDataFrame (spatial clip) or plain DataFrame with lat/lon columns
    to the city boundary polygon. Returns data unchanged if city_polygon is None
    or clipping fails.
    """
    if city_polygon is None or data is None:
        return data
    try:
        if hasattr(data, "geometry"):
            gdf = data.copy()
            if gdf.empty:
                return gdf
            if gdf.crs is None:
                gdf = gdf.set_crs("EPSG:4326")
            city_gdf = gpd.GeoDataFrame(geometry=[city_polygon], crs="EPSG:4326")
            clipped = gpd.clip(gdf, city_gdf)
            print(f"[clip] {len(data)} → {len(clipped)} rows")
            return clipped
        elif "lat" in data.columns and "lon" in data.columns:
            from shapely.geometry import Point
            pts = [Point(lon, lat) for lon, lat in zip(data["lon"], data["lat"])]
            mask = [city_polygon.contains(p) for p in pts]
            clipped = data[mask].reset_index(drop=True)
            print(f"[clip] {len(data)} → {len(clipped)} rows (lat/lon)")
            return clipped
    except Exception as e:
        print(f"[clip] failed: {e}")
    return data


def _run_parallel_fetches(city_name, analysis_bbox, config,
                          run_morph, run_transport, run_nature, run_terrain,
                          layers=None):
    """Fetch all data sources simultaneously using a thread pool.

    ``layers`` (optional set) restricts fetching to those keys — used when
    the city_cache already supplied the rest.
    """
    def _want(key):
        return layers is None or key in layers

    futures_map = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        if _want('poi'):
            futures_map['poi'] = executor.submit(
                fetch_overture_pois, city_name, analysis_bbox, config['overture_limit'])
        if _want('landuse'):
            futures_map['landuse'] = executor.submit(fetch_osm_landuse, city_name, analysis_bbox)
        if run_morph and _want('osm'):
            futures_map['osm'] = executor.submit(
                fetch_osm_data, city_name, analysis_bbox, config['network_dist'])
        if run_transport and _want('transport'):
            futures_map['transport'] = executor.submit(
                fetch_transport_data, city_name, analysis_bbox, list(config['road_tags']))
        if run_nature and _want('nature'):
            futures_map['nature'] = executor.submit(fetch_nature_data, city_name, analysis_bbox)
        if run_terrain and analysis_bbox and _want('terrain'):
            futures_map['terrain'] = executor.submit(
                fetch_terrain_data, city_name, analysis_bbox, config['terrain_grid'])

        results = {}
        timed_out_keys = []
        for key, future in futures_map.items():
            try:
                results[key] = future.result(timeout=240)
            except concurrent.futures.TimeoutError as e:
                print(f"[parallel] {key} timed out: {e}")
                results[key] = None
                timed_out_keys.append(key)
            except Exception as e:
                print(f"[parallel] {key} failed: {type(e).__name__}: {e}")
                results[key] = None
    return results, timed_out_keys


def _ai_available() -> bool:
    key = os.getenv("ANTHROPIC_API_KEY", "")
    return bool(key) and key != "your_key_here"


def _fig_to_spec(fig):
    """Plotly Figure → JSON-safe dict (handles numpy arrays via plotly's encoder)."""
    if fig is None:
        return None
    return json.loads(fig.to_json())


# ── Entry point ───────────────────────────────────────────────────────────────

def run_full_analysis(city_name: str, config: dict = None,
                      progress=None, cache=None) -> dict:
    """
    Run the complete v1 analysis for one city with no web framework involved.

    ``progress`` is an optional ``callable(str)`` invoked with human-readable
    stage descriptions (replaces the v1 spinners).

    ``cache`` is an optional city_cache provider with
    ``get(city_name, bbox) -> dict | None`` and
    ``set(city_name, bbox, layers: dict)`` — layer dicts are the JSON-able
    form from ``engine.cache`` (serialize/deserialize happens here, so
    providers only move plain dicts in and out of storage).
    """
    config = dict(config or {})
    city_name = (city_name or "").strip()
    if not city_name:
        raise AnalysisError("City name is required.")

    def _progress(msg):
        if progress:
            try:
                progress(msg)
            except Exception:
                pass
        print(f"[pipeline] {msg}")

    warnings: list[str] = []

    def _warn(msg):
        warnings.append(str(msg))
        print(f"[pipeline][warn] {msg}")

    # ── Config resolution (v1 sidebar) ────────────────────────────────────────
    city_size = config.get("city_size", "Medium (100k–500k)")
    if city_size not in SIZE_CONFIGS:
        city_size = "Medium (100k–500k)"
    size_cfg = dict(SIZE_CONFIGS[city_size])
    # allow explicit overrides of individual size parameters
    for k in size_cfg:
        if k in config:
            size_cfg[k] = config[k]

    toggles = {k: bool(config.get(k, v)) for k, v in DEFAULT_MODULES.items()}
    run_morphology = toggles["morphology"]
    run_transport = toggles["transport"]
    run_nature = toggles["nature"]
    run_terrain = toggles["terrain"]
    run_climate = toggles["climate"]
    run_stress = toggles["stress_index"]
    run_typology = toggles["fabric_typology"]
    run_cross = toggles["cross_analysis"]

    zone_mode = config.get("zone_mode", "Entire city")
    selected_district = config.get("selected_district", "All")
    custom_bbox = tuple(config.get("custom_bbox") or (0.0, 0.0, 0.0, 0.0))

    SKIP_MODULES = (
        ['segregation', 'vulnerability', 'fabric_typology']
        if city_size == "Small (< 100k)" else []
    )

    # ── Step 1: Admin boundaries + city polygon ───────────────────────────────
    _progress("Fetching administrative boundaries…")
    try:
        admin_boundaries = fetch_admin_boundaries(city_name)
    except Exception as e:
        _warn(f"Admin boundaries failed: {e}")
        admin_boundaries = {}

    city_polygon = get_city_polygon(admin_boundaries)

    analysis_bbox = get_analysis_bbox(
        city_name, zone_mode, selected_district, admin_boundaries, custom_bbox
    )

    if zone_mode == "Entire city" and analysis_bbox is not None:
        area = bbox_area_km2(analysis_bbox)
        if area > MAX_ENTIRE_CITY_AREA_KM2:
            raise AnalysisError(
                "This city's area is too large for a full-city analysis via "
                "free Overpass servers. Please select a specific district "
                f"(detected area: {area:.0f} km², limit: {MAX_ENTIRE_CITY_AREA_KM2} km²)."
            )

    # ── Step 2: Fetch all data sources (city_cache first, then live) ──────────
    from .data import get_overpass_call_count, reset_overpass_call_count
    from . import cache as cache_codec
    reset_overpass_call_count()

    all_data = {}
    timed_out_layers = []
    if cache is not None:
        try:
            cached_raw = cache.get(city_name, cache_codec.bbox_key(analysis_bbox))
            if cached_raw:
                all_data = cache_codec.deserialize_layers(cached_raw)
                _progress(f"Cache hit: {sorted(all_data.keys())}")
        except Exception as e:
            _warn(f"City cache read failed: {e}")
            all_data = {}

    needed = {'poi', 'landuse'}
    if run_morphology or run_transport:
        needed.add('osm')
    if run_transport:
        needed.add('transport')
    if run_nature:
        needed.add('nature')
    if run_terrain and analysis_bbox:
        needed.add('terrain')
    missing = {k for k in needed if all_data.get(k) is None}

    if missing:
        _progress(f"Fetching data sources: {sorted(missing)}…")
        fetched, timed_out_layers = _run_parallel_fetches(
            city_name, analysis_bbox, size_cfg,
            run_morph=(run_morphology or run_transport),
            run_transport=run_transport,
            run_nature=run_nature,
            run_terrain=run_terrain,
            layers=missing,
        )
        all_data.update({k: v for k, v in fetched.items() if v is not None})
        print(f"[pipeline] Overpass calls this analysis: {get_overpass_call_count()}")

        # Write back after a successful live fetch (only layers that succeeded)
        if cache is not None and any(fetched.get(k) is not None for k in missing):
            try:
                cache.set(city_name, cache_codec.bbox_key(analysis_bbox),
                          cache_codec.serialize_layers(all_data))
                _progress("City cache updated")
            except Exception as e:
                _warn(f"City cache write failed: {e}")
    else:
        print("[pipeline] All layers served from city_cache — 0 live fetches")
    gc.collect()

    poi_raw = all_data.get('poi')
    poi_df_raw = poi_raw if poi_raw is not None else pd.DataFrame(columns=["name", "category", "lat", "lon"])
    osm_result = all_data.get('osm') or {"graph": None, "buildings": None}
    landuse_raw = all_data.get('landuse')
    landuse_gdf = landuse_raw if landuse_raw is not None else gpd.GeoDataFrame()
    transport_data = all_data.get('transport') or {
        "roads": gpd.GeoDataFrame(), "transit_stops": gpd.GeoDataFrame(), "cycling": gpd.GeoDataFrame()}
    nature_data = all_data.get('nature') or {
        "green_spaces": gpd.GeoDataFrame(), "water_bodies": gpd.GeoDataFrame(),
        "flood_risk_proxy": gpd.GeoDataFrame()}
    terrain_data = all_data.get('terrain') or {}

    poi_df = clip_to_city(poi_df_raw, city_polygon)
    del poi_df_raw
    if poi_df is None or len(poi_df) == 0:
        raise AnalysisError(
            "No data found for this city. Make sure to include the country, "
            "e.g. 'Blois, France'"
        )
    elif len(poi_df) < 15:
        _warn("Very few POIs found. Results may be incomplete.")
    _progress(f"Data fetched: {len(poi_df):,} POIs")

    if timed_out_layers:
        _warn(
            "Some data layers timed out for this large area. Try selecting "
            "a smaller zone (district) instead of the entire city."
        )

    graph = None
    buildings_raw = None
    buildings_gdf = gpd.GeoDataFrame(columns=["geometry", "height"])

    if run_morphology or run_transport:
        graph = osm_result.get("graph")
        buildings_raw = osm_result.get("buildings")

        if buildings_raw is not None and not buildings_raw.empty:
            try:
                b = buildings_raw.copy()
                if b.crs is None:
                    b = b.set_crs("EPSG:4326")
                b = b[b.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].reset_index(drop=True)
                b = clip_to_city(b, city_polygon)
                if not b.empty:
                    b["height"] = _resolve_heights(b).values
                    buildings_gdf = b[["geometry", "height"]].copy()
            except Exception as e:
                _warn(f"Building normalisation failed: {e}")

    landuse_gdf = clip_to_city(landuse_gdf, city_polygon)

    if run_transport:
        transport_data["roads"] = clip_to_city(
            transport_data.get("roads", gpd.GeoDataFrame()), city_polygon)
        transport_data["transit_stops"] = clip_to_city(
            transport_data.get("transit_stops", gpd.GeoDataFrame()), city_polygon)

    if run_nature:
        nature_data["green_spaces"] = clip_to_city(
            nature_data.get("green_spaces", gpd.GeoDataFrame()), city_polygon)
        nature_data["water_bodies"] = clip_to_city(
            nature_data.get("water_bodies", gpd.GeoDataFrame()), city_polygon)

    # Sample buildings for metric computation — config-based limit
    _building_cap = size_cfg['building_limit']
    if buildings_gdf is not None and len(buildings_gdf) > _building_cap:
        buildings_sample = buildings_gdf.sample(_building_cap, random_state=42)
        print(f"[perf] Sampling {_building_cap} from {len(buildings_gdf)} buildings for metrics")
    else:
        buildings_sample = buildings_gdf
    gc.collect()

    # ── Step 3: Core metrics ──────────────────────────────────────────────────
    _progress("Computing core metrics…")
    try:
        category_series = poi_category_distribution(poi_df)
    except Exception as e:
        _warn(f"POI distribution failed: {e}")
        category_series = pd.Series(dtype=int)

    try:
        height_stats = building_height_stats(buildings_gdf) if run_morphology else {}
    except Exception as e:
        _warn(f"Building height stats failed: {e}")
        height_stats = {}

    try:
        diversity_df = land_use_diversity(poi_df)
    except Exception as e:
        _warn(f"Land use diversity failed: {e}")
        diversity_df = pd.DataFrame(columns=["h3_cell", "lat", "lon", "diversity_score"])

    try:
        net_stats = street_network_stats(graph) if run_morphology else {}
    except Exception as e:
        _warn(f"Street network stats failed: {e}")
        net_stats = {}

    try:
        morph_data = (
            compute_morphological_index(buildings_sample, graph, diversity_df=diversity_df) if run_morphology
            else {"hex_metrics": gpd.GeoDataFrame(),
                  "typology_counts": pd.Series(dtype=int),
                  "typologies": pd.Series(dtype=str)}
        )
    except Exception as e:
        _warn(f"Morphological index failed: {e}")
        morph_data = {"hex_metrics": gpd.GeoDataFrame(),
                      "typology_counts": pd.Series(dtype=int)}

    try:
        lu_metrics = landuse_composition(landuse_gdf)
    except Exception as e:
        _warn(f"Land use composition failed: {e}")
        lu_metrics = {}
    gc.collect()

    # ── Step 4: Accessibility ─────────────────────────────────────────────────
    _progress("Computing transport & nature accessibility…")
    transit_stops_gdf = transport_data.get("transit_stops", gpd.GeoDataFrame())
    green_spaces_gdf = nature_data.get("green_spaces", gpd.GeoDataFrame())

    try:
        transport_hex = (
            transport_accessibility_index(buildings_sample, transit_stops_gdf, graph)
            if run_transport else gpd.GeoDataFrame()
        )
    except Exception as e:
        _warn(f"Transport accessibility failed: {e}")
        transport_hex = gpd.GeoDataFrame()

    try:
        nature_hex = (
            nature_accessibility_index(
                buildings_sample, green_spaces_gdf,
                nature_data.get("water_bodies", gpd.GeoDataFrame()),
            )
            if run_nature else gpd.GeoDataFrame()
        )
    except Exception as e:
        _warn(f"Nature accessibility failed: {e}")
        nature_hex = gpd.GeoDataFrame()
    gc.collect()

    # ── Step 5: Build merged hex GDF — POI/bbox fallback when buildings absent ─
    hex_metrics = morph_data.get("hex_metrics", gpd.GeoDataFrame())
    typology_counts = morph_data.get("typology_counts", pd.Series(dtype=int))

    if hex_metrics.empty and run_morphology:
        _warn("Building data unavailable — using POI hex grid as base layer")
        poi_hex = create_hex_grid_from_pois(poi_df)
        if poi_hex.empty and analysis_bbox:
            poi_hex = create_hex_grid_from_bbox(analysis_bbox, resolution=size_cfg['hex_resolution'])
        hex_metrics = poi_hex

    merged_hex = hex_metrics.copy()

    if not diversity_df.empty:
        _div = diversity_df[[c for c in ["h3_cell", "diversity_score"] if c in diversity_df.columns]]
        if "h3_cell" in _div.columns:
            merged_hex = safe_merge(merged_hex, _div.drop_duplicates("h3_cell"))

    if not transport_hex.empty:
        _t_cols = [c for c in ["h3_cell", "transport_index", "transit_score",
                               "cycling_coverage", "road_hierarchy_mix"]
                   if c in transport_hex.columns]
        if "h3_cell" in _t_cols:
            merged_hex = safe_merge(merged_hex, transport_hex[_t_cols].drop_duplicates("h3_cell"))

    if not nature_hex.empty:
        _n_cols = [c for c in ["h3_cell", "nature_index", "green_space_ratio",
                               "park_access_score", "water_proximity", "flood_risk_tier"]
                   if c in nature_hex.columns]
        if "h3_cell" in _n_cols:
            merged_hex = safe_merge(merged_hex, nature_hex[_n_cols].drop_duplicates("h3_cell"))

    merged_hex = clip_to_city(merged_hex, city_polygon)

    # Drop unused columns to reduce memory footprint
    _keep_cols = ['h3_cell', 'lat', 'lon', 'geometry', 'FAR', 'BCR', 'CMI',
                  'transport_index', 'nature_index', 'urban_stress',
                  'diversity_score', 'cluster', 'terrain_flood_risk',
                  'elevation_m', 'green_space_ratio', 'flood_risk_tier',
                  'dominant_driver', 'vulnerability_score', 'segregation_score']
    merged_hex = merged_hex[[c for c in _keep_cols if c in merged_hex.columns]].copy()
    gc.collect()

    # ── Step 7: Advanced analytics ────────────────────────────────────────────
    _progress("Computing advanced analytics…")
    analysis_hex = merged_hex.copy()

    if run_stress:
        try:
            analysis_hex = compute_urban_stress_index(analysis_hex)
        except Exception as e:
            _warn(f"Failed to compute urban stress: {e}")

    if run_typology and 'fabric_typology' not in SKIP_MODULES:
        try:
            analysis_hex = compute_fabric_typology(analysis_hex)
        except Exception as e:
            _warn(f"Failed to compute fabric typology: {e}")

    if 'vulnerability' not in SKIP_MODULES:
        try:
            analysis_hex = compute_temporal_vulnerability(analysis_hex)
        except Exception as e:
            _warn(f"Failed to compute temporal vulnerability: {e}")

    if 'segregation' not in SKIP_MODULES:
        try:
            analysis_hex = compute_segregation_proxy(analysis_hex)
        except Exception as e:
            _warn(f"Failed to compute segregation proxy: {e}")
    gc.collect()

    # Population density proxy (buildings × 3.5 persons per unit)
    if not analysis_hex.empty and 'BCR' in analysis_hex.columns:
        try:
            analysis_hex['pop_density_proxy'] = (
                analysis_hex['BCR'].fillna(0) * 105332.51 / 100 * 3.5
            )
        except Exception:
            pass

    # ── Step 8: Terrain sampling ──────────────────────────────────────────────
    if run_terrain:
        _progress("Sampling terrain elevation per hex cell…")
        try:
            if not analysis_hex.empty and terrain_data.get("elevation_grid") is not None:
                analysis_hex = sample_terrain_for_hexes(analysis_hex, terrain_data)
        except Exception as e:
            _warn(f"Terrain sampling failed: {e}")
        gc.collect()

    # ── Step 9: Scalar summaries ──────────────────────────────────────────────
    total_buildings = (
        len(buildings_raw) if buildings_raw is not None and not buildings_raw.empty
        else len(buildings_gdf) if buildings_gdf is not None and not buildings_gdf.empty
        else 0
    )
    del buildings_raw
    gc.collect()
    total_pois = len(poi_df) if not poi_df.empty else 0
    green_pct = lu_metrics.get("green_space_ratio", 0.0) * 100
    dominant_morphotype = (
        hex_metrics["cluster"].mode()[0].replace("_", " ").title()
        if not hex_metrics.empty and "cluster" in hex_metrics.columns else "N/A"
    )
    orientation_entropy = net_stats.get("orientation_entropy", 0.0)
    dead_end_ratio = net_stats.get("dead_end_ratio", 0.0)
    block_size_median = net_stats.get("block_size_median", 0.0)
    orientation_hist = net_stats.get("orientation_histogram", [])
    if not hex_metrics.empty and "lat" in hex_metrics.columns:
        city_center_lat = float(hex_metrics["lat"].mean())
        city_center_lon = float(hex_metrics["lon"].mean())
    elif not poi_df.empty:
        city_center_lat = float(poi_df["lat"].mean())
        city_center_lon = float(poi_df["lon"].mean())
    else:
        city_center_lat, city_center_lon = 0.0, 0.0

    roads_gdf = transport_data.get("roads", gpd.GeoDataFrame())
    road_type_counts = {}
    if not roads_gdf.empty and "highway" in roads_gdf.columns:
        def _flat_hw(h):
            if isinstance(h, list):
                return h[0] if h else "other"
            return str(h) if h else "other"
        road_type_counts = roads_gdf["highway"].apply(_flat_hw).value_counts().to_dict()

    transit_stops_count = len(transit_stops_gdf) if not transit_stops_gdf.empty else 0
    cycling_gdf = transport_data.get("cycling", gpd.GeoDataFrame())
    cycling_km = 0.0
    if not cycling_gdf.empty:
        try:
            cycling_km = cycling_gdf.to_crs("EPSG:3857").geometry.length.sum() / 1000
        except Exception:
            pass
    dominant_road = max(road_type_counts, key=road_type_counts.get) if road_type_counts else "N/A"
    water_bodies_count = len(nature_data.get("water_bodies", gpd.GeoDataFrame()))
    high_flood_pct = 0.0
    if not nature_hex.empty and "flood_risk_tier" in nature_hex.columns:
        high_flood_pct = (nature_hex["flood_risk_tier"] == "high").mean() * 100

    nature_metrics_dict: dict = {}
    if not nature_hex.empty:
        nature_metrics_dict = {
            "green_ratio":     float(nature_hex["green_space_ratio"].mean()) if "green_space_ratio" in nature_hex.columns else 0.0,
            "park_access":     min(float(nature_hex["park_access_score"].mean()) / 10, 1.0) if "park_access_score" in nature_hex.columns else 0.0,
            "water_proximity": float(nature_hex["water_proximity"].mean()) if "water_proximity" in nature_hex.columns else 0.0,
            "flood_safety":    float((nature_hex["flood_risk_tier"] != "high").mean()) if "flood_risk_tier" in nature_hex.columns else 1.0,
        }

    # ── Step 10: Climate + UHI ────────────────────────────────────────────────
    climate_data: dict = {}
    if run_climate and city_center_lat != 0.0:
        _progress("Fetching climate data (Open-Meteo)…")
        try:
            climate_data = fetch_climate_data(city_center_lat, city_center_lon)
        except Exception as e:
            _warn(f"Climate data failed: {e}")

    if run_climate and climate_data and 'error' not in climate_data:
        try:
            analysis_hex = compute_heat_island_proxy(analysis_hex, climate_data)
        except Exception as e:
            _warn(f"Heat island proxy failed: {e}")

    # ── Step 11: Land use cross-reference ─────────────────────────────────────
    _progress("Computing land use cross-reference…")
    try:
        crossref_df = (
            landuse_transport_crossref(landuse_gdf, analysis_hex)
            if run_cross else pd.DataFrame()
        )
    except Exception as e:
        _warn(f"Land use cross-reference failed: {e}")
        crossref_df = pd.DataFrame()

    # ── Step 12: District scores ──────────────────────────────────────────────
    district_scores_df = pd.DataFrame()
    try:
        if not analysis_hex.empty and admin_boundaries.get('has_districts'):
            district_scores_df = compute_district_scores(analysis_hex, admin_boundaries)
    except Exception as e:
        _warn(f"District scores failed: {e}")

    # ── Charts (all nine v1 tabs) ─────────────────────────────────────────────
    _progress("Rendering charts…")
    figures: dict = {}

    def _chart(name, fn, *args, apply_admin_bounds=False, min_check=True, **kw):
        """v1 _safe_chart equivalent: build figure, optionally overlay admin
        boundaries, store under `name`. Failures become a skipped chart."""
        if not min_check:
            return
        try:
            fig = fn(*args, **kw)
            if apply_admin_bounds and admin_boundaries:
                fig = add_admin_boundaries_to_fig(
                    fig, admin_boundaries, show_city=True, show_districts=True,
                )
            figures[name] = fig
        except Exception as e:
            print(f"[pipeline][chart] {name} unavailable: {e}")

    # Tab 1 — Overview
    _chart("poi_dominance_map", ch.chart_poi_dominance_map,
           poi_df, analysis_hex if not analysis_hex.empty else None,
           apply_admin_bounds=True, min_check=has_data(poi_df, min_rows=1))
    _chart("poi_distribution", ch.chart_poi_distribution, category_series,
           min_check=has_data(category_series, min_rows=1))
    _chart("landuse_composition", ch.chart_landuse_composition, lu_metrics,
           min_check=bool(lu_metrics))
    _chart("poi_density_contour", ch.chart_poi_density_contour, poi_df, city_polygon,
           apply_admin_bounds=True, min_check=has_data(poi_df, min_rows=10))
    _chart("nearest_services", ch.chart_nearest_services, poi_df,
           city_center_lat, city_center_lon,
           min_check=has_data(poi_df, min_rows=5) and city_center_lat != 0.0)

    # Tab 2 — Morphology
    if run_morphology:
        _chart("far_heatmap", ch.chart_far_heatmap, hex_metrics,
               apply_admin_bounds=True,
               min_check=has_data(hex_metrics, min_rows=1, required_cols=['FAR']))
        _chart("morphotype_clusters", ch.chart_morphotype_clusters, hex_metrics,
               apply_admin_bounds=True,
               min_check=has_data(hex_metrics, min_rows=1, required_cols=['cluster']))
        _chart("density_gradient", ch.chart_density_gradient, buildings_gdf,
               poi_df=poi_df, city_center_lat=city_center_lat, city_center_lon=city_center_lon,
               min_check=has_data(buildings_gdf, min_rows=5, required_cols=['height']))
        _chart("morphological_transition", ch.chart_morphological_transition,
               analysis_hex, city_center_lat, city_center_lon,
               min_check=has_data(analysis_hex, min_rows=5) and city_center_lat != 0.0)
        _chart("urban_quality", ch.chart_urban_quality_index, analysis_hex,
               min_check=_has_cols(analysis_hex, "transport_index", "nature_index"))

    # Tab 3 — Street Network
    if run_morphology:
        _chart("street_orientation", ch.chart_street_orientation,
               orientation_entropy, orientation_hist,
               min_check=bool(orientation_hist) and any(h > 0 for h in orientation_hist))
        _chart("street_radar", ch.chart_street_network_radar, net_stats, city_name,
               min_check=bool(net_stats))
        _chart("street_centrality", ch.chart_street_centrality_edges, graph,
               city_center_lat, city_center_lon, apply_admin_bounds=True,
               min_check=graph is not None and city_center_lat != 0.0)

    # Tab 4 — Transport
    if run_transport:
        _chart("road_hierarchy", ch.chart_road_hierarchy, road_type_counts,
               min_check=bool(road_type_counts))
        _chart("transit_heatmap", ch.chart_transit_heatmap, transit_stops_gdf,
               apply_admin_bounds=True, min_check=has_data(transit_stops_gdf, min_rows=1))
        _chart("transport_map", ch.chart_transport_accessibility, transport_hex,
               apply_admin_bounds=True,
               min_check=has_data(transport_hex, min_rows=1, required_cols=['transport_index']))

    # Tab 5 — Nature & Risk
    if run_nature:
        _chart("nature_map", ch.chart_green_space_access, nature_hex,
               apply_admin_bounds=True,
               min_check=has_data(nature_hex, min_rows=1, required_cols=['nature_index']))
        _chart("flood_risk_map", ch.chart_flood_risk_zones, nature_hex,
               apply_admin_bounds=True,
               min_check=has_data(nature_hex, min_rows=1, required_cols=['flood_risk_tier']))
        _chart("nature_radar", ch.chart_nature_radar, nature_metrics_dict,
               min_check=bool(nature_metrics_dict))
        _chart("city_15min", ch.chart_15min_city_score,
               poi_df, transit_stops_gdf, green_spaces_gdf,
               city_center_lat, city_center_lon,
               min_check=has_data(poi_df, min_rows=1))

    if run_terrain and _has_cols(analysis_hex, "elevation_m", "terrain_flood_risk", min_rows=3):
        _chart("terrain_elevation", ch.chart_terrain_elevation, analysis_hex,
               apply_admin_bounds=True)
        _chart("terrain_flood_risk", ch.chart_terrain_flood_risk, analysis_hex,
               apply_admin_bounds=True)
        _chart("terrain_cross", ch.chart_terrain_cross_buildings, analysis_hex)
        _chart("twi_distribution", ch.chart_twi_distribution, analysis_hex)
        _chart("slope_elevation", ch.chart_slope_elevation_2d, analysis_hex)

    if run_climate and climate_data and 'error' not in climate_data and 'uhi_delta' in analysis_hex.columns:
        _chart("heat_island_map", ch.chart_heat_island_map, analysis_hex,
               climate_data.get('temp_max_avg', 20), apply_admin_bounds=True)

    # Tab 6 — Cross-Analysis
    if run_cross and _has_cols(analysis_hex, "CMI", "transport_index", "nature_index", min_rows=10):
        _chart("opportunity_surface", ch.chart_opportunity_surface, analysis_hex)
        _chart("cross_morph_transport", ch.chart_cross_heatmap_morph_transport, analysis_hex)
        _chart("cross_nature_density", ch.chart_cross_heatmap_nature_morph, analysis_hex)
        _chart("cross_transport_nature", ch.chart_cross_heatmap_transport_nature, analysis_hex)
        _chart("landuse_crossref", ch.chart_landuse_crossref, crossref_df,
               min_check=has_data(crossref_df, min_rows=1))

    # Tab 7 — Stress & Risk
    if run_stress and _has_cols(analysis_hex, "urban_stress", min_rows=5):
        _chart("stress_map", ch.chart_urban_stress_map, analysis_hex,
               apply_admin_bounds=True)
        _chart("stress_decomp", ch.chart_urban_stress_decomposition, analysis_hex)
        _chart("vulnerability_map", ch.chart_vulnerability_map, analysis_hex,
               apply_admin_bounds=True,
               min_check=_has_cols(analysis_hex, "vulnerability_score", min_rows=5))
        _chart("stress_pareto", ch.chart_urban_efficiency_pareto, analysis_hex)
        _chart("vuln_vs_stress", ch.chart_vulnerability_vs_stress, analysis_hex,
               min_check=_has_cols(analysis_hex, "urban_stress", "vulnerability_score", min_rows=5))

    # Tab 8 — Typology
    if run_typology and _has_cols(analysis_hex, "fabric_type", "planning_label", min_rows=5):
        _chart("fabric_matrix", ch.chart_fabric_typology_matrix, analysis_hex)
        _chart("fabric_map", ch.chart_fabric_typology_map, analysis_hex,
               apply_admin_bounds=True)
        _chart("morphotype_radar", ch.chart_morphotype_radar_comparison, analysis_hex,
               min_check=_has_cols(analysis_hex, "cluster", min_rows=5))
        _chart("segregation_map", ch.chart_segregation_map, analysis_hex,
               apply_admin_bounds=True,
               min_check=_has_cols(analysis_hex, "segregation_score", min_rows=5))

    # Tab 9 — District Scores
    _chart("district_scorecard", ch.chart_district_scorecard, district_scores_df,
           min_check=not district_scores_df.empty)

    # ── AI insights ───────────────────────────────────────────────────────────
    ai_insights = ""
    if toggles["ai"] and _ai_available():
        _progress("Generating AI insights…")
        try:
            from .ai import get_urban_insights
            _morph_stats = {
                "dominant_morphotype": dominant_morphotype,
                "green_space_ratio":   lu_metrics.get("green_space_ratio", 0.0),
                "far_mean": float(hex_metrics["FAR"].mean()) if not hex_metrics.empty and "FAR" in hex_metrics.columns else 0.0,
                "dead_end_ratio":      dead_end_ratio,
                "orientation_entropy": orientation_entropy,
                "transit_stops":       transit_stops_count,
                "cycling_km":          round(float(cycling_km), 1),
                "high_flood_pct":      round(float(high_flood_pct), 1),
            }
            ai_insights = get_urban_insights(
                city_name,
                poi_stats=category_series.head(5).to_dict() if not category_series.empty else {},
                height_stats=height_stats,
                network_stats={k: v for k, v in net_stats.items() if k != "orientation_histogram"},
                morph_stats=_morph_stats,
            )
        except Exception as e:
            _warn(f"AI insights failed: {e}")

    # ── Assemble result ───────────────────────────────────────────────────────
    _progress("Serializing results…")

    metrics_summary = {
        "total_buildings":      int(total_buildings),
        "total_pois":           int(total_pois),
        "median_height":        float(height_stats.get("median", 0) or 0),
        "green_space_pct":      float(green_pct),
        "transport_index_mean": (
            float(transport_hex["transport_index"].mean())
            if not transport_hex.empty and "transport_index" in transport_hex.columns else 0.0
        ),
        "urban_stress_mean": (
            float(analysis_hex["urban_stress"].mean())
            if not analysis_hex.empty and "urban_stress" in analysis_hex.columns else 0.0
        ),
        "dominant_morphotype": dominant_morphotype,
    }

    scalars = {
        "orientation_entropy": float(orientation_entropy or 0),
        "dead_end_ratio":      float(dead_end_ratio or 0),
        "block_size_median":   float(block_size_median or 0),
        "transit_stops_count": int(transit_stops_count),
        "cycling_km":          float(cycling_km),
        "dominant_road":       str(dominant_road),
        "water_bodies_count":  int(water_bodies_count),
        "high_flood_pct":      float(high_flood_pct),
        "city_center_lat":     city_center_lat,
        "city_center_lon":     city_center_lon,
        "typology_counts":     {str(k): int(v) for k, v in typology_counts.items()} if typology_counts is not None else {},
    }

    charts_json = {name: _fig_to_spec(fig) for name, fig in figures.items()}
    charts_json = {k: v for k, v in charts_json.items() if v is not None}

    district_scores = (
        json.loads(district_scores_df.to_json(orient="records"))
        if not district_scores_df.empty else []
    )

    # Street network edges as a GeoDataFrame for export
    edges_gdf = None
    if graph is not None:
        try:
            import osmnx as ox
            edges_gdf = ox.graph_to_gdfs(graph, nodes=False, edges=True).reset_index()
            edges_gdf = edges_gdf[[c for c in ["u", "v", "key", "highway", "name", "length", "geometry"]
                                   if c in edges_gdf.columns]]
        except Exception as e:
            print(f"[pipeline] edges export prep failed: {e}")

    result = {
        "city_name": city_name,
        "config": {
            "city_size": city_size,
            "zone_mode": zone_mode,
            "selected_district": selected_district,
            **{k: toggles[k] for k in DEFAULT_MODULES},
        },
        "metrics_summary": metrics_summary,
        "scalars": scalars,
        "charts": charts_json,
        "district_scores": district_scores,
        "ai_insights": ai_insights,
        "warnings": warnings,
        # Non-JSON geodata for the export endpoints; the API layer strips this
        # before persisting the result to the jobs table.
        "artifacts": {
            "buildings": buildings_gdf,
            "hex_grid": analysis_hex,
            "street_edges": edges_gdf,
        },
    }

    del buildings_gdf, buildings_sample, poi_df, landuse_gdf
    del transport_data, nature_data
    gc.collect()

    return result
