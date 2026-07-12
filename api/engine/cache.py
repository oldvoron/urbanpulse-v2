"""city_cache (de)serialization for the raw fetch layers.

The pipeline's raw fetch results (poi/landuse/osm/transport/nature/terrain)
are cached per city in the `city_cache` table so a repeat analysis hits zero
live external sources. This module converts those layers to/from a plain
JSON-able dict; the DB read/write itself is done by whatever cache provider
the caller passes into ``run_full_analysis`` (see ``main.py:DbCityCache``),
keeping the engine free of any database dependency.

The street graph is stored as zlib-compressed base64 GraphML. Raw building
GeoDataFrames are trimmed to geometry + the height columns
``metrics._resolve_heights`` actually reads — the rest of the ~100 raw OSM
tag columns are dead weight and often not JSON-safe.
"""
import base64
import json
import tempfile
import zlib

import pandas as pd
import geopandas as gpd

CACHEABLE_LAYERS = ["poi", "landuse", "osm", "transport", "nature", "terrain"]

_BUILDING_COLS = ["height", "building:levels", "levels", "building:height"]


def _gdf_to_obj(gdf):
    if gdf is None:
        return None
    if getattr(gdf, "empty", True):
        return {"kind": "gdf", "geojson": None}
    g = gdf.copy()
    # OSM tag columns can hold lists; GeoJSON properties take them as-is,
    # but dict values (rare) are stringified for safety.
    for c in g.columns:
        if c != "geometry" and g[c].map(lambda v: isinstance(v, dict)).any():
            g[c] = g[c].astype(str)
    return {"kind": "gdf", "geojson": json.loads(g.to_json())}


def _obj_to_gdf(obj):
    if obj is None:
        return None
    gj = obj.get("geojson")
    if not gj or not gj.get("features"):
        return gpd.GeoDataFrame()
    return gpd.GeoDataFrame.from_features(gj["features"], crs="EPSG:4326")


def _graph_to_str(G):
    if G is None:
        return None
    import osmnx as ox
    with tempfile.NamedTemporaryFile(suffix=".graphml") as tmp:
        ox.save_graphml(G, filepath=tmp.name)
        tmp.seek(0)
        raw = tmp.read()
    return base64.b64encode(zlib.compress(raw, level=6)).decode("ascii")


def _str_to_graph(s):
    if not s:
        return None
    import osmnx as ox
    raw = zlib.decompress(base64.b64decode(s))
    return ox.load_graphml(graphml_str=raw.decode("utf-8"))


def serialize_layers(all_data: dict) -> dict:
    """Raw fetch-result dict → JSON-able dict for the city_cache row."""
    out = {}
    for key in CACHEABLE_LAYERS:
        val = all_data.get(key)
        if val is None:
            continue
        try:
            if key == "poi":
                out[key] = {"kind": "df", "records": val.to_dict("records")}
            elif key == "osm":
                buildings = val.get("buildings")
                if buildings is not None and not buildings.empty:
                    keep = ["geometry"] + [c for c in _BUILDING_COLS if c in buildings.columns]
                    buildings = buildings[keep]
                out[key] = {
                    "kind": "osm",
                    "graph": _graph_to_str(val.get("graph")),
                    "buildings": _gdf_to_obj(buildings),
                }
            elif key == "transport":
                out[key] = {"kind": "layers", "layers": {
                    k: _gdf_to_obj(val.get(k)) for k in ["roads", "transit_stops", "cycling"]}}
            elif key == "nature":
                out[key] = {"kind": "layers", "layers": {
                    k: _gdf_to_obj(val.get(k))
                    for k in ["green_spaces", "water_bodies", "flood_risk_proxy"]}}
            elif key == "landuse":
                out[key] = _gdf_to_obj(val)
            elif key == "terrain":
                t = dict(val)
                for k in ("elevation_grid", "lats", "lons"):
                    if t.get(k) is not None:
                        t[k] = [None if pd.isna(x) else float(x) for x in t[k]]
                out[key] = {"kind": "terrain", "data": t}
        except Exception as e:
            print(f"[cache] serialize {key} failed: {e}")
    return out


def deserialize_layers(raw: dict) -> dict:
    """city_cache row → raw fetch-result dict. Layers that fail to
    deserialize are dropped (the pipeline will fetch them live)."""
    out = {}
    for key, obj in (raw or {}).items():
        if obj is None:
            continue
        try:
            if key == "poi":
                out[key] = pd.DataFrame(obj["records"],
                                        columns=["name", "category", "lat", "lon"])
            elif key == "osm":
                out[key] = {
                    "graph": _str_to_graph(obj.get("graph")),
                    "buildings": _obj_to_gdf(obj.get("buildings")),
                }
            elif key in ("transport", "nature"):
                out[key] = {k: (_obj_to_gdf(v) if v is not None else gpd.GeoDataFrame())
                            for k, v in obj["layers"].items()}
            elif key == "landuse":
                out[key] = _obj_to_gdf(obj)
            elif key == "terrain":
                import numpy as np
                t = dict(obj["data"])
                for k in ("elevation_grid", "lats", "lons"):
                    if t.get(k) is not None:
                        t[k] = np.array([np.nan if x is None else x for x in t[k]],
                                        dtype=float)
                out[key] = t
        except Exception as e:
            print(f"[cache] deserialize {key} failed: {e}")
    return out


def bbox_key(bbox) -> list | None:
    """Round a bbox for cache-identity comparison (~11 m tolerance)."""
    if bbox is None:
        return None
    return [round(float(v), 4) for v in bbox]
