import osmnx as ox
import pandas as pd
import geopandas as gpd
import time
import threading


OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
]

# Caps how many Overpass HTTP calls the whole app can have in flight at once.
# osmnx splits large bboxes into many internal sub-requests, and with 4 layers
# (osm/transport/landuse/nature) fetched in parallel threads, uncapped
# concurrency can flood public mirrors and take them down. Applies uniformly
# to every osmnx_fetch_with_retry() call — admin boundaries, POIs (including
# the OSM/Overpass POI fallback), street network, landuse, transport, nature.
_OVERPASS_SEMAPHORE = threading.Semaphore(2)


def configure_osmnx():
    """Configure osmnx with retry-friendly settings."""
    ox.settings.timeout = 45
    ox.settings.requests_timeout = 20
    # Smaller max query area => osmnx auto-splits bboxes into more, smaller
    # sub-requests. Each sub-request is less likely to time out on its own,
    # even though there are more of them overall.
    ox.settings.max_query_area_size = 2_500_000_000
    ox.settings.overpass_rate_limit = False
    ox.settings.overpass_url = OVERPASS_MIRRORS[0]


configure_osmnx()


# Logical Overpass fetch counter — lets the pipeline log how many Overpass
# round-trips one analysis costs, to confirm the composite-query rewrite
# actually reduced them (v2 data-reliability layer).
_overpass_call_count = 0
_count_lock = threading.Lock()


def get_overpass_call_count() -> int:
    return _overpass_call_count


def reset_overpass_call_count():
    global _overpass_call_count
    with _count_lock:
        _overpass_call_count = 0


def osmnx_fetch_with_retry(fetch_func, max_retries=1, delay=3):
    """
    Retry osmnx fetch across Overpass mirrors (OVERPASS_MIRRORS) on connection
    errors. On failure, moves straight to the next mirror rather than
    retrying the same one — under load the problem is usually mirror
    overload, not a one-off blip, so waiting and retrying in place just adds
    latency without improving odds. Every actual HTTP call is gated by
    _OVERPASS_SEMAPHORE so at most 2 Overpass requests are in flight across
    the whole app at once.
    """
    global _overpass_call_count
    with _count_lock:
        _overpass_call_count += 1
    last_exc = None
    for mirror in OVERPASS_MIRRORS:
        ox.settings.overpass_url = mirror
        for attempt in range(max_retries):
            try:
                with _OVERPASS_SEMAPHORE:
                    result = fetch_func()
                time.sleep(2)
                print(f"[OSM] Overpass mirror OK: {mirror}")
                return result
            except Exception as e:
                last_exc = e
                err_str = str(e)
                if any(k in err_str for k in ('Connection refused', 'Max retries', 'timeout', 'Timeout')):
                    if attempt < max_retries - 1:
                        wait = delay * (attempt + 1)
                        print(f"[OSM] {mirror} failed, retrying in {wait}s... (attempt {attempt+1}/{max_retries})")
                        time.sleep(wait)
                        continue
                    print(f"[OSM] {mirror} failed after {max_retries} attempt(s), trying next mirror...")
                    break
                raise e
    if last_exc is not None:
        raise last_exc
    return None


# ── Overture Maps ─────────────────────────────────────────────────────────────

def fetch_overture_pois(city_name: str, bbox=None, overture_limit: int = 15000) -> pd.DataFrame:
    """
    Fetch POIs from Overture Maps using the overturemaps Python package (primary)
    with DuckDB S3 as fallback. Returns DataFrame with [name, category, lat, lon].
    """
    if bbox is None:
        try:
            b = ox.geocode_to_gdf(city_name).total_bounds  # minx, miny, maxx, maxy
            bbox = (b[0], b[1], b[2], b[3])
        except Exception as e:
            print(f"[overture] geocode failed: {e}")
            return pd.DataFrame(columns=["name", "category", "lat", "lon"])

    min_lon, min_lat, max_lon, max_lat = bbox

    # Primary: overturemaps package
    try:
        import overturemaps
        reader = overturemaps.record_batch_reader("place", bbox=(min_lon, min_lat, max_lon, max_lat))
        table = reader.read_all()
        df = table.to_pandas()

        if df.empty:
            raise ValueError("empty result")

        if "names" in df.columns:
            df["name"] = df["names"].apply(
                lambda x: x.get("primary", "") if isinstance(x, dict) else ""
            )
        else:
            df["name"] = ""

        if "categories" in df.columns:
            df["category"] = df["categories"].apply(
                lambda x: x.get("primary", "unknown") if isinstance(x, dict) else "unknown"
            )
        else:
            df["category"] = "unknown"

        if "geometry" in df.columns:
            def _xy(g):
                if hasattr(g, "x"):
                    return g.x, g.y
                if isinstance(g, dict):
                    coords = g.get("coordinates", [None, None])
                    return coords[0], coords[1]
                try:
                    import shapely.wkb
                    pt = shapely.wkb.loads(bytes(g)) if isinstance(g, (bytes, bytearray, memoryview)) else g
                    return pt.x, pt.y
                except Exception:
                    return None, None

            df[["lon", "lat"]] = df["geometry"].apply(lambda g: pd.Series(_xy(g)))

        df = df.dropna(subset=["lat", "lon"])
        if len(df) > overture_limit:
            df = df.head(overture_limit)
        print(f"[overture] package: {len(df)} places")
        return df[["name", "category", "lat", "lon"]]

    except Exception as e:
        print(f"[overture] package failed: {e}")

    # Fallback: DuckDB S3 (best-effort, path may be stale)
    try:
        import duckdb
        con = duckdb.connect()
        con.execute("INSTALL spatial; LOAD spatial;")
        con.execute("INSTALL httpfs; LOAD httpfs;")
        con.execute("SET s3_region='us-west-2';")
        q = f"""
            SELECT
                names.primary AS name,
                categories.primary AS category,
                ST_Y(ST_GeomFromWKB(geometry)) AS lat,
                ST_X(ST_GeomFromWKB(geometry)) AS lon
            FROM read_parquet(
                's3://overturemaps-us-west-2/release/2025-05-21.0/theme=places/type=place/*',
                hive_partitioning=1
            )
            WHERE bbox.minx BETWEEN {min_lon} AND {max_lon}
              AND bbox.miny BETWEEN {min_lat} AND {max_lat}
            LIMIT {overture_limit}
        """
        df = con.execute(q).df()
        con.close()
        df = df.dropna(subset=["lat", "lon"])
        print(f"[overture] DuckDB S3: {len(df)} places")
        return df[["name", "category", "lat", "lon"]]
    except Exception as e:
        print(f"[overture] DuckDB S3 fallback failed: {e}")

    # Fallback: OSM/Overpass via osmnx
    try:
        df = fetch_osm_pois(city_name, bbox=bbox)
        if not df.empty:
            print(f"[overture] OSM/Overpass fallback: {len(df)} places")
            return df
    except Exception as e:
        print(f"[overture] OSM/Overpass fallback failed: {e}")

    return pd.DataFrame(columns=["name", "category", "lat", "lon"])


# ── OSM helpers ───────────────────────────────────────────────────────────────
# osmnx 2.x: bbox = (left, bottom, right, top) = (min_lon, min_lat, max_lon, max_lat)

def _city_bbox(city_name: str):
    """Geocode a city to (min_lon, min_lat, max_lon, max_lat).

    Nominatim geocode, not an Overpass call — used so every Overpass query is
    bbox-only; polygon (features_from_place) queries are far more likely to
    time out on public mirrors.
    """
    b = ox.geocode_to_gdf(city_name).total_bounds
    return (b[0], b[1], b[2], b[3])


def _osm_features(city_name: str, bbox, tags: dict) -> gpd.GeoDataFrame:
    """Fetch OSM features with retry — always bbox-only, never polygon."""
    if bbox is None:
        bbox = _city_bbox(city_name)
    result = osmnx_fetch_with_retry(lambda: ox.features_from_bbox(bbox=bbox, tags=tags))
    return result if result is not None else gpd.GeoDataFrame()


def _tag_match(gdf: gpd.GeoDataFrame, col: str, values) -> pd.Series:
    """Row mask: does `col` match any of `values` (True = any non-null value)?

    Composite union queries return one GeoDataFrame with a column per tag key;
    this splits it back into the per-layer subsets the pipeline expects.
    OSM tag columns can hold scalars or lists.
    """
    if col not in gdf.columns:
        return pd.Series(False, index=gdf.index)
    series = gdf[col]
    if values is True:
        return series.notna()
    vals = {values} if isinstance(values, str) else set(values)

    def _match(v):
        if isinstance(v, list):
            return any(x in vals for x in v)
        try:
            if pd.isna(v):
                return False
        except (TypeError, ValueError):
            pass
        return v in vals

    return series.apply(_match)


_POI_CATEGORY_TAGS = ["amenity", "shop", "tourism", "leisure", "office", "craft"]


def fetch_osm_pois(city_name: str, bbox=None) -> pd.DataFrame:
    """
    Fetch POIs from OSM/Overpass (via osmnx, with mirror retry) as a fallback
    for Overture Maps. Returns DataFrame with [name, category, lat, lon].
    """
    tags = {tag: True for tag in _POI_CATEGORY_TAGS}
    gdf = _osm_features(city_name, bbox, tags)
    if gdf.empty:
        return pd.DataFrame(columns=["name", "category", "lat", "lon"])

    df = gdf.copy()
    if "name" in df.columns:
        df["name"] = df["name"].fillna("")
    else:
        df["name"] = ""

    def _category(row):
        for tag in _POI_CATEGORY_TAGS:
            val = row.get(tag)
            if pd.notna(val) and val not in (None, "", False):
                return val
        return "unknown"

    df["category"] = df.apply(_category, axis=1)

    utm_crs = df.estimate_utm_crs()
    centroids = df.geometry.to_crs(utm_crs).centroid.to_crs(df.crs)
    df["lat"] = centroids.y
    df["lon"] = centroids.x

    df = df.dropna(subset=["lat", "lon"])
    return df[["name", "category", "lat", "lon"]].reset_index(drop=True)


# ── Street network & buildings ────────────────────────────────────────────────

def fetch_osm_data(city_name: str, bbox=None, network_dist: int = 5000) -> dict:
    """Return {'graph': G|None, 'buildings': GeoDataFrame|None}."""
    ox.settings.timeout = 45
    ox.settings.max_query_area_size = 2_500_000_000

    result = {"graph": None, "buildings": None}

    # Street network — bbox-only, never a polygon (place) query
    try:
        if bbox is None:
            bbox = _city_bbox(city_name)
        G = osmnx_fetch_with_retry(lambda: ox.graph_from_bbox(bbox=bbox, network_type="walk"))
        if G is None:
            raise ValueError("graph fetch returned None after retries")
        result["graph"] = G
        print(f"[OSM] Street network: {len(G.nodes)} nodes, {len(G.edges)} edges")
    except Exception as e:
        print(f"[OSM] Street network failed: {e}")
        try:
            loc = ox.geocode(city_name)
            G = osmnx_fetch_with_retry(lambda: ox.graph_from_point(loc, dist=network_dist, network_type="walk"))
            if G is not None:
                result["graph"] = G
                print(f"[OSM] Fallback point network: {len(G.nodes)} nodes")
        except Exception as e2:
            print(f"[OSM] Fallback network failed: {e2}")

    # Buildings — try progressively relaxed tag sets
    for tags in [
        {"building": True},
        {"building": ["yes", "house", "residential", "apartments",
                      "commercial", "retail", "office", "industrial"]},
        {"building": "yes"},
    ]:
        try:
            gdf = _osm_features(city_name, bbox, tags)
            if not gdf.empty:
                result["buildings"] = gdf
                print(f"[OSM] {len(gdf)} buildings (tags: {list(tags.keys())})")
                break
        except Exception as e:
            print(f"[OSM] Building attempt failed ({list(tags.keys())}): {e}")

    return result


# ── Transport data ────────────────────────────────────────────────────────────

_TRANSIT_RAILWAY = ["station", "halt", "tram_stop", "subway_entrance"]


def fetch_transport_data(city_name: str, bbox=None,
                         road_tags: list = None) -> dict:
    """Roads + transit stops + cycling in ONE composite Overpass union query
    (was 6 separate tag-group calls in v1), split client-side by tag column.
    """
    ox.settings.timeout = 45
    if road_tags is None:
        road_tags = ['primary', 'secondary', 'tertiary']
    result = {
        "roads": gpd.GeoDataFrame(),
        "transit_stops": gpd.GeoDataFrame(),
        "cycling": gpd.GeoDataFrame(),
    }

    try:
        combined = _osm_features(city_name, bbox, {
            "highway": list(road_tags) + ["bus_stop", "cycleway"],
            "railway": _TRANSIT_RAILWAY,
            "public_transport": "stop_position",
            "bicycle": "designated",
        })
    except Exception as e:
        print(f"[transport] composite fetch error: {e}")
        return result
    if combined.empty:
        return result
    combined = combined.reset_index(drop=True)

    line_mask = combined.geometry.geom_type.isin(["LineString", "MultiLineString"])

    # Roads — filtered by config road_tags to control data volume
    roads = combined[_tag_match(combined, "highway", road_tags) & line_mask].copy()
    if not roads.empty:
        if "highway" not in roads.columns:
            roads["highway"] = "other"
        result["roads"] = roads[["geometry", "highway"]].copy()
        print(f"[transport] {len(result['roads'])} road segments")

    # Transit stops
    transit_mask = (
        _tag_match(combined, "highway", "bus_stop")
        | _tag_match(combined, "railway", _TRANSIT_RAILWAY)
        | _tag_match(combined, "public_transport", "stop_position")
    )
    pts = combined[transit_mask & (combined.geometry.geom_type == "Point")][["geometry"]].copy()
    if not pts.empty:
        stops = gpd.GeoDataFrame(pts, crs="EPSG:4326")
        stops = stops.drop_duplicates(subset=["geometry"])
        stops["lat"] = stops.geometry.y
        stops["lon"] = stops.geometry.x
        result["transit_stops"] = stops
        print(f"[transport] {len(stops)} transit stops")

    # Cycling infrastructure
    cycling_mask = (
        _tag_match(combined, "highway", "cycleway")
        | _tag_match(combined, "bicycle", "designated")
    )
    lines = combined[cycling_mask & line_mask][["geometry"]].copy()
    if not lines.empty:
        result["cycling"] = gpd.GeoDataFrame(lines.reset_index(drop=True), crs="EPSG:4326")

    return result


# ── Nature & green space ──────────────────────────────────────────────────────

_GREEN_LEISURE = ["park", "garden", "nature_reserve", "pitch", "playground"]
_GREEN_LANDUSE = ["forest", "grass", "meadow", "recreation_ground", "village_green"]
_GREEN_NATURAL = ["wood", "scrub", "heath", "grassland"]


def fetch_nature_data(city_name: str, bbox=None) -> dict:
    """Green spaces + water bodies + flood-risk waterways in ONE composite
    Overpass union query (was 7 separate tag-group calls in v1).
    """
    ox.settings.timeout = 45
    result = {
        "green_spaces": gpd.GeoDataFrame(),
        "water_bodies": gpd.GeoDataFrame(),
        "flood_risk_proxy": gpd.GeoDataFrame(),
    }
    poly_types = {"Polygon", "MultiPolygon"}

    try:
        combined = _osm_features(city_name, bbox, {
            "leisure": _GREEN_LEISURE,
            "landuse": _GREEN_LANDUSE + ["reservoir"],
            "natural": _GREEN_NATURAL + ["water"],
            "waterway": ["river", "stream", "canal"],
        })
    except Exception as e:
        print(f"[nature] composite fetch error: {e}")
        return result
    if combined.empty:
        return result
    combined = combined.reset_index(drop=True)

    # Green spaces
    green_mask = (
        _tag_match(combined, "leisure", _GREEN_LEISURE)
        | _tag_match(combined, "landuse", _GREEN_LANDUSE)
        | _tag_match(combined, "natural", _GREEN_NATURAL)
    )
    polys = combined[green_mask & combined.geometry.geom_type.isin(poly_types)][["geometry"]].copy()
    if not polys.empty:
        result["green_spaces"] = gpd.GeoDataFrame(
            polys.reset_index(drop=True), crs="EPSG:4326"
        )
        print(f"[nature] {len(result['green_spaces'])} green space polygons")

    # Water bodies
    water_mask = (
        _tag_match(combined, "natural", "water")
        | _tag_match(combined, "waterway", ["river", "stream", "canal"])
        | _tag_match(combined, "landuse", "reservoir")
    )
    water = combined[water_mask][["geometry"]].copy()
    if not water.empty:
        result["water_bodies"] = gpd.GeoDataFrame(
            water.reset_index(drop=True), crs="EPSG:4326"
        )

    # Flood risk proxy from waterways (reuses the same composite result)
    try:
        waterways = combined[_tag_match(combined, "waterway", ["river", "stream"])]
        if not waterways.empty:
            wl = waterways[waterways.geometry.geom_type.isin(
                ["LineString", "MultiLineString"])].copy()
            if not wl.empty:
                wl_m = wl.to_crs("EPSG:3857")
                union_line = wl_m.geometry.unary_union
                flood_rows = []
                for tier, dist in [("high", 50), ("medium", 100), ("low", 200)]:
                    buf = union_line.buffer(dist)
                    flood_rows.append({
                        "geometry": gpd.GeoSeries([buf], crs="EPSG:3857").to_crs("EPSG:4326").iloc[0],
                        "flood_tier": tier,
                        "buffer_m": dist,
                    })
                result["flood_risk_proxy"] = gpd.GeoDataFrame(flood_rows, crs="EPSG:4326")
    except Exception as e:
        print(f"[nature] Flood risk proxy error: {e}")

    return result


# ── Land use ──────────────────────────────────────────────────────────────────

_LANDUSE_CLASSES = {
    "residential", "commercial", "industrial", "retail",
    "park", "forest", "water", "recreation_ground", "meadow", "farmland",
}
_LEISURE_MAP = {"park": "park", "garden": "park", "pitch": "park",
                "playground": "park", "nature_reserve": "forest"}
_NATURAL_MAP = {"water": "water", "wood": "forest", "scrub": "forest",
                "wetland": "forest", "grassland": "park"}


def fetch_osm_landuse(city_name: str, bbox=None) -> gpd.GeoDataFrame:
    """Landuse + leisure + natural polygons in ONE composite Overpass union
    query (was 3 separate calls in v1), classified client-side.
    """
    ox.settings.timeout = 45
    poly_types = {"Polygon", "MultiPolygon"}
    gdfs = []

    try:
        combined = _osm_features(city_name, bbox, {
            "landuse": True,
            "leisure": list(_LEISURE_MAP.keys()),
            "natural": list(_NATURAL_MAP.keys()),
        })
    except Exception as e:
        print(f"[landuse] composite fetch error: {e}")
        return gpd.GeoDataFrame(columns=["geometry", "landuse_class"], crs="EPSG:4326")
    if combined.empty:
        return gpd.GeoDataFrame(columns=["geometry", "landuse_class"], crs="EPSG:4326")
    combined = combined.reset_index(drop=True)
    combined = combined[combined.geometry.geom_type.isin(poly_types)].copy()

    def _scalar(v):
        return v[0] if isinstance(v, list) and v else v

    # Broad landuse sweep
    if "landuse" in combined.columns:
        lu = combined[combined["landuse"].notna()].copy()
        if not lu.empty:
            lu_vals = lu["landuse"].map(_scalar)
            lu["landuse_class"] = lu_vals.where(lu_vals.isin(_LANDUSE_CLASSES), "other")
            gdfs.append(lu[["geometry", "landuse_class"]])
            print(f"[landuse] {len(lu)} landuse polygons")

    # Leisure
    if "leisure" in combined.columns:
        lei = combined[_tag_match(combined, "leisure", list(_LEISURE_MAP.keys()))].copy()
        if not lei.empty:
            lei["landuse_class"] = lei["leisure"].map(_scalar).map(_LEISURE_MAP).fillna("park")
            gdfs.append(lei[["geometry", "landuse_class"]])

    # Natural
    if "natural" in combined.columns:
        nat = combined[_tag_match(combined, "natural", list(_NATURAL_MAP.keys()))].copy()
        if not nat.empty:
            nat["landuse_class"] = nat["natural"].map(_scalar).map(_NATURAL_MAP).fillna("other")
            gdfs.append(nat[["geometry", "landuse_class"]])

    if not gdfs:
        return gpd.GeoDataFrame(columns=["geometry", "landuse_class"], crs="EPSG:4326")
    return gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs="EPSG:4326")


# ── Terrain (elevation) ───────────────────────────────────────────────────────

def fetch_terrain_data(city_name: str, bbox: tuple, terrain_grid: int = 20) -> dict:
    """
    Fetch elevation from Open-Meteo over a terrain_grid×terrain_grid grid within bbox.
    bbox = (min_lon, min_lat, max_lon, max_lat)
    """
    import requests
    import numpy as np

    if bbox is None or len(bbox) != 4:
        return {"elevation_grid": None}

    min_lon, min_lat, max_lon, max_lat = bbox
    lat_steps = np.linspace(min_lat, max_lat, terrain_grid)
    lon_steps = np.linspace(min_lon, max_lon, terrain_grid)
    grid_lats, grid_lons = np.meshgrid(lat_steps, lon_steps)
    grid_lats = grid_lats.flatten()
    grid_lons = grid_lons.flatten()

    all_elevations = []
    for i in range(0, len(grid_lats), 100):
        batch_lats = grid_lats[i:i + 100]
        batch_lons = grid_lons[i:i + 100]
        try:
            r = requests.get(
                "https://api.open-meteo.com/v1/elevation",
                params={
                    "latitude":  ",".join(map(str, batch_lats.round(5))),
                    "longitude": ",".join(map(str, batch_lons.round(5))),
                },
                timeout=15,
            )
            all_elevations.extend(r.json().get("elevation", [None] * len(batch_lats)))
        except Exception as e:
            print(f"[terrain] batch {i} failed: {e}")
            all_elevations.extend([None] * len(batch_lats))

    elevs = np.array([e if e is not None else np.nan for e in all_elevations], dtype=float)
    if (~np.isnan(elevs)).sum() < 10:
        return {"elevation_grid": None}

    return {
        "elevation_grid": elevs,
        "lats": grid_lats,
        "lons": grid_lons,
        "elev_min": float(np.nanmin(elevs)),
        "elev_max": float(np.nanmax(elevs)),
        "elev_mean": float(np.nanmean(elevs)),
    }


# ── Admin boundaries ──────────────────────────────────────────────────────────

def get_city_polygon(admin_boundaries: dict):
    """Return a single Shapely polygon/multipolygon for the city boundary, or None."""
    if admin_boundaries is None:
        return None
    city_gdf = admin_boundaries.get("city")
    if city_gdf is None or city_gdf.empty:
        return None
    try:
        return city_gdf.union_all()
    except AttributeError:
        # geopandas < 1.0 used unary_union
        return city_gdf.unary_union


def fetch_admin_boundaries(city_name: str) -> dict:
    """Fetch city + district boundaries via OSM admin_level tags.

    Both admin levels come from ONE bbox-only composite Overpass query (v1
    issued a polygon features_from_place call per level). The bbox is the
    geocoded city boundary's bounds; districts from neighbouring communes
    that fall inside the bbox are filtered out against the city polygon.
    """
    result = {}
    try:
        result["city"] = osmnx_fetch_with_retry(lambda: ox.geocode_to_gdf(city_name))
    except Exception:
        result["city"] = None

    city_gdf = result.get("city")
    city_poly = None
    if city_gdf is not None and not city_gdf.empty:
        try:
            city_poly = city_gdf.union_all()
        except AttributeError:
            city_poly = city_gdf.unary_union

    combined = gpd.GeoDataFrame()
    if city_gdf is not None and not city_gdf.empty:
        try:
            b = city_gdf.total_bounds
            combined = _osm_features(
                city_name, (b[0], b[1], b[2], b[3]),
                {"boundary": "administrative", "admin_level": ["9", "10"]},
            )
        except Exception as e:
            print(f"[admin] composite boundary fetch failed: {e}")

    for admin_level in [9, 10]:
        try:
            if combined.empty or "admin_level" not in combined.columns:
                result[f"admin_{admin_level}"] = None
                continue
            gdf = combined[_tag_match(combined, "admin_level", str(admin_level))].copy()
            gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
            if city_poly is not None and not gdf.empty:
                gdf = gdf[gdf.representative_point().within(city_poly)].copy()
            if not gdf.empty:
                name_col = "name" if "name" in gdf.columns else gdf.columns[0]
                gdf["admin_name"] = gdf[name_col].fillna(f"Zone_{admin_level}")
                result[f"admin_{admin_level}"] = gdf[["admin_name", "geometry"]].copy()
                continue
            result[f"admin_{admin_level}"] = None
        except Exception:
            result[f"admin_{admin_level}"] = None

    district_names = []
    for level in ["admin_9", "admin_10"]:
        lvl = result.get(level)
        if lvl is not None and not lvl.empty:
            district_names.extend(lvl["admin_name"].tolist())
    result["district_names"] = list(set(district_names))
    result["has_districts"] = len(district_names) > 0
    return result


# ── Climate ───────────────────────────────────────────────────────────────────

def fetch_climate_data(city_center_lat: float, city_center_lon: float) -> dict:
    """7-day forecast from Open-Meteo (no API key)."""
    import requests
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": city_center_lat,
                "longitude": city_center_lon,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,"
                         "et0_fao_evapotranspiration",
                "timezone": "auto",
                "forecast_days": 7,
            },
            timeout=10,
        )
        daily = r.json().get("daily", {})
        tmax = daily.get("temperature_2m_max", [])
        tmin = daily.get("temperature_2m_min", [])
        return {
            "temp_max_avg": sum(tmax) / max(len(tmax), 1),
            "temp_min_avg": sum(tmin) / max(len(tmin), 1),
            "precip_7day": sum(daily.get("precipitation_sum", [])),
            "raw_daily": daily,
            "source": "Open-Meteo 7-day forecast",
        }
    except Exception as e:
        return {"error": str(e)}


# ── Population (best-effort) ──────────────────────────────────────────────────

def fetch_population_grid(bbox) -> dict:
    """Best-effort WorldPop estimate. Returns {} on any failure."""
    import requests
    if bbox is None:
        return {}
    min_lon, min_lat, max_lon, max_lat = bbox
    try:
        r = requests.get(
            "https://api.worldpop.org/v1/wopr/pointestimate",
            params={
                "iso3": "AUTO", "ver": "1",
                "lat": (min_lat + max_lat) / 2,
                "lon": (min_lon + max_lon) / 2,
            },
            timeout=10,
        )
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}
