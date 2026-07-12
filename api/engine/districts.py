"""District discovery for the zone-selection system (UI addendum §2.2).

OSM has no single admin_level meaning "district" across countries (Paris
arrondissements = 9, Berlin Bezirke = 9, London boroughs = 8, Moscow okrugs =
8…), so we probe levels 8 → 9 → 10 and pick the first that yields a
"reasonable" number of subdivisions *inside* the city polygon.
"""
import warnings

import geopandas as gpd
import osmnx as ox

from .data import _osm_features, _tag_match, osmnx_fetch_with_retry

_TRY_LEVELS = ("8", "9", "10")
_MIN_DISTRICTS = 3
_MAX_DISTRICTS = 40
# A "subdivision" covering ≥80% of the city is just the city re-returned.
_CITY_AREA_RATIO = 0.8


def find_districts(city_name: str) -> dict:
    """Return {level_used, districts: [{name, osm_id}], city_bbox}.

    level_used is None (districts empty) when no probed admin_level yields a
    usable subdivision set — the frontend then shows the honest fallback and
    points the user at Custom area mode.
    """
    city_gdf = osmnx_fetch_with_retry(lambda: ox.geocode_to_gdf(city_name))
    if city_gdf is None or city_gdf.empty:
        raise ValueError(f"Could not geocode city: {city_name}")
    b = city_gdf.total_bounds
    city_bbox = [float(b[0]), float(b[1]), float(b[2]), float(b[3])]
    try:
        city_poly = city_gdf.union_all()
    except AttributeError:
        city_poly = city_gdf.unary_union

    # One composite bbox query for all three candidate levels.
    combined = _osm_features(
        city_name, tuple(city_bbox),
        {"boundary": "administrative", "admin_level": list(_TRY_LEVELS)},
    )
    empty = {"level_used": None, "districts": [], "city_bbox": city_bbox}
    if combined.empty or "admin_level" not in combined.columns:
        return empty
    combined = combined.reset_index()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # planar .area on EPSG:4326 — ratios only
        city_area = gpd.GeoSeries([city_poly]).area.iloc[0]

        for level in _TRY_LEVELS:
            gdf = combined[_tag_match(combined, "admin_level", level)].copy()
            gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
            if gdf.empty or "name" not in gdf.columns:
                continue
            gdf = gdf[gdf["name"].notna()]
            if gdf.empty:
                continue
            # Subdivisions OF the city: representative point inside the city
            # polygon (neighbouring communes in the bbox get dropped)…
            gdf = gdf[gdf.representative_point().within(city_poly)]
            # …not the city itself re-returned at this level, and not tiny
            # mis-tagged footprints (e.g. a town-hall building carrying
            # admin_level): a real district is ≥0.1% of the city's area.
            if not gdf.empty and city_area > 0:
                ratio = gdf.geometry.area / city_area
                gdf = gdf[(ratio < _CITY_AREA_RATIO) & (ratio > 0.001)]
            gdf = gdf.drop_duplicates(subset=["name"])
            n = len(gdf)
            print(f"[districts] {city_name}: admin_level {level} → {n} subdivisions")
            if _MIN_DISTRICTS <= n <= _MAX_DISTRICTS:
                id_col = next((c for c in ("id", "osmid", "element_id") if c in gdf.columns), None)
                districts = [
                    {"name": str(row["name"]),
                     "osm_id": str(row[id_col]) if id_col else ""}
                    for _, row in gdf.sort_values("name").iterrows()
                ]
                return {"level_used": int(level), "districts": districts,
                        "city_bbox": city_bbox}

    return empty
