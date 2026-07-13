"""15-Minute City Score (Addendum 2 §5) — network-based walkable accessibility.

For each H3 hex cell, walking time along the EXISTING street network (the same
graph already fetched for the Street Network/Transport tabs — no second
network fetch) to the nearest destination in five essential-service
categories: grocery/food, pharmacy/health, school/education, park/green
space, transit stop. Score = share of the 5 categories reachable within 15
minutes at 4.5 km/h, as 0–100, plus per-category minutes so users can see
which service type is the bottleneck for an area.

Implementation: one multi-source Dijkstra per category (cutoff at the
15-minute walking radius) instead of per-hex routing — O(5 × E log V), cheap
even for large networks. Hexes beyond the scope guard are sampled.
"""
import numpy as np
import pandas as pd
import geopandas as gpd

WALK_SPEED_KMH = 4.5
MINUTES = 15
CUTOFF_M = WALK_SPEED_KMH * 1000 / 60 * MINUTES  # 1125 m

# Keyword match against the categorized POI set already used by the POI
# dominance chart (raw Overture/OSM category strings) — not a new taxonomy.
_POI_CATEGORY_KEYWORDS = {
    "food": ("supermarket", "grocery", "convenience", "bakery", "butcher",
             "greengrocer", "food_market", "marketplace", "deli"),
    "health": ("pharmacy", "hospital", "clinic", "doctor", "dentist",
               "health", "medical"),
    "education": ("school", "college", "university", "kindergarten",
                  "education", "creche", "child_care"),
}
CATEGORY_LABELS = {
    "food": "Grocery / food",
    "health": "Pharmacy / health",
    "education": "School / education",
    "green": "Park / green space",
    "transit": "Transit stop",
}

# Scope guard (§5): cap the per-category Dijkstra work for very large runs.
_MAX_HEXES = 3000
_MAX_SOURCES_PER_CAT = 4000


def _match_poi_category(poi_df: pd.DataFrame, keywords) -> pd.DataFrame:
    if poi_df is None or poi_df.empty or "category" not in poi_df.columns:
        return pd.DataFrame(columns=["lat", "lon"])
    cat = poi_df["category"].astype(str).str.lower()
    mask = cat.str.contains("|".join(keywords), regex=True, na=False)
    return poi_df.loc[mask, ["lat", "lon"]]


def _category_points(poi_df, transit_stops_gdf, green_spaces_gdf) -> dict:
    """(lat, lon) destination arrays per essential-service category."""
    pts = {}
    for key, kws in _POI_CATEGORY_KEYWORDS.items():
        df = _match_poi_category(poi_df, kws)
        pts[key] = (df["lat"].to_numpy(), df["lon"].to_numpy())

    if transit_stops_gdf is not None and not getattr(transit_stops_gdf, "empty", True):
        g = transit_stops_gdf
        if "lat" in g.columns and "lon" in g.columns:
            pts["transit"] = (g["lat"].to_numpy(), g["lon"].to_numpy())
        else:
            pts["transit"] = (g.geometry.y.to_numpy(), g.geometry.x.to_numpy())
    else:
        pts["transit"] = (np.array([]), np.array([]))

    if green_spaces_gdf is not None and not getattr(green_spaces_gdf, "empty", True):
        c = green_spaces_gdf.geometry.representative_point()
        pts["green"] = (c.y.to_numpy(), c.x.to_numpy())
    else:
        pts["green"] = (np.array([]), np.array([]))
    return pts


def compute_15min_scores(hex_gdf: gpd.GeoDataFrame, graph, poi_df,
                         transit_stops_gdf, green_spaces_gdf) -> gpd.GeoDataFrame:
    """Add score_15min (0–100) + min15_<category> (walking minutes, NaN if
    beyond 15 min) columns to hex_gdf. Returns hex_gdf unchanged when the
    graph or hex grid is unusable."""
    if graph is None or hex_gdf is None or hex_gdf.empty:
        return hex_gdf
    if "lat" not in hex_gdf.columns or "lon" not in hex_gdf.columns:
        return hex_gdf

    import networkx as nx
    import osmnx as ox

    hex_gdf = hex_gdf.copy()

    # Scope guard: sample very large hex grids; others keep NaN.
    idx = hex_gdf.index
    if len(idx) > _MAX_HEXES:
        idx = hex_gdf.sample(_MAX_HEXES, random_state=42).index
        print(f"[15min] sampling {_MAX_HEXES} of {len(hex_gdf)} hexes")

    hex_lats = hex_gdf.loc[idx, "lat"].to_numpy(dtype=float)
    hex_lons = hex_gdf.loc[idx, "lon"].to_numpy(dtype=float)
    hex_nodes = ox.distance.nearest_nodes(graph, X=hex_lons, Y=hex_lats)

    meters_per_minute = WALK_SPEED_KMH * 1000 / 60
    cats = _category_points(poi_df, transit_stops_gdf, green_spaces_gdf)
    per_cat_minutes = {}

    for cat, (lats, lons) in cats.items():
        col = f"min15_{cat}"
        hex_gdf[col] = np.nan
        if len(lats) == 0:
            per_cat_minutes[cat] = None
            continue
        if len(lats) > _MAX_SOURCES_PER_CAT:
            keep = np.random.RandomState(42).choice(
                len(lats), _MAX_SOURCES_PER_CAT, replace=False)
            lats, lons = lats[keep], lons[keep]
        try:
            src_nodes = set(ox.distance.nearest_nodes(
                graph, X=np.asarray(lons, dtype=float),
                Y=np.asarray(lats, dtype=float)))
            # One multi-source Dijkstra out from every destination of this
            # category, cut off at the 15-minute walking radius.
            dist = nx.multi_source_dijkstra_path_length(
                graph, src_nodes, cutoff=CUTOFF_M, weight="length")
        except Exception as e:
            print(f"[15min] {cat} routing failed: {e}")
            per_cat_minutes[cat] = None
            continue
        minutes = np.array(
            [dist.get(n, np.nan) / meters_per_minute for n in hex_nodes])
        hex_gdf.loc[idx, col] = minutes
        per_cat_minutes[cat] = minutes

    # 0–100 score: percentage of the 5 categories reachable within 15 min
    reach_cols = [f"min15_{c}" for c in CATEGORY_LABELS]
    reached = hex_gdf.loc[idx, reach_cols].notna().sum(axis=1)
    hex_gdf["score_15min"] = np.nan
    hex_gdf.loc[idx, "score_15min"] = (reached / len(CATEGORY_LABELS) * 100).astype(float)

    scored = hex_gdf["score_15min"].dropna()
    if not scored.empty:
        print(f"[15min] mean score {scored.mean():.1f} over {len(scored)} hexes")
    return hex_gdf
