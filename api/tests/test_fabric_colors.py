"""§1.3 of the UI addendum: assert the typology map's legend swatches and hex
fills come from the exact same color mapping (engine.charts.fabric_color_map),
so legend↔map colors can't silently drift after future edits.

Run:  .venv/bin/python tests/test_fabric_colors.py   (or via pytest)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import geopandas as gpd  # noqa: E402
import h3  # noqa: E402

from engine.charts import chart_fabric_typology_map, fabric_color_map  # noqa: E402


def _synthetic_fabric_gdf():
    """A few real H3 cells around Blois with fake fabric labels."""
    labels = ["Historic Mixed Core", "Mixed Suburb", "Commercial Strip",
              "Peri-Urban", "Dormitory", "Tower Block"]
    rows = []
    for i, lbl in enumerate(labels):
        for j in range(3):
            lat, lon = 47.58 + i * 0.01, 1.33 + j * 0.01
            cell = h3.latlng_to_cell(lat, lon, 9)
            rows.append({"h3_cell": cell, "lat": lat, "lon": lon,
                         "planning_label": lbl, "fabric_type": f"t{i}",
                         "FAR": 0.5, "diversity_score": 0.5})
    return gpd.GeoDataFrame(rows)


def test_legend_matches_map_colors():
    gdf = _synthetic_fabric_gdf()
    expected = fabric_color_map(gdf["planning_label"].unique())
    fig = chart_fabric_typology_map(gdf)

    seen = {}
    for trace in fig.data:
        # px.choropleth_mapbox emits one trace per category; its legend
        # swatch color IS its fill color (marker/colorscale on the trace).
        name = trace.name
        if not name:
            continue
        color = None
        if getattr(trace, "marker", None) is not None:
            color = getattr(trace.marker, "color", None) or None
        if color is None and getattr(trace, "colorscale", None):
            color = trace.colorscale[0][1]
        seen[name] = color

    assert seen, "no categorical traces found on the typology map figure"
    for name, color in seen.items():
        assert name in expected, f"trace {name!r} not in fabric_color_map"
        assert color == expected[name], (
            f"legend/map color mismatch for {name!r}: "
            f"trace={color!r} vs mapping={expected[name]!r}")
    print(f"OK: {len(seen)} categories, legend == map == fabric_color_map")


if __name__ == "__main__":
    test_legend_matches_map_colors()
