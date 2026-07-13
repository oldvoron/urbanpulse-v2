"""One-off preload of France/Germany OSM extracts into Neon Postgres (§5.2).

Purpose: for preloaded regions, /api/analyze never needs a live Overpass call
for buildings/roads/landuse/nature — the layers are read from Postgres.

NOT run automatically. Prerequisites (in order):

1. Confirm PostGIS is enabled on the Neon project (free tier supports it, but
   verify on YOUR project first):  ``CREATE EXTENSION IF NOT EXISTS postgis;``
   → If PostGIS turns out to be unavailable, FALLBACK: keep the loader but
   write geometries as GeoJSON into a plain JSONB table (osm_preload_geojson)
   — less efficient spatial querying, still zero live external calls.
2. Install extra tooling (not in requirements.txt — keeps the Space image
   lean):  ``pip install pyosmium``  and/or  ``brew install osmium-tool``.
3. Download the extracts (large: France ≈ 4 GB, Germany ≈ 4 GB):
     https://download.geofabrik.de/europe/france-latest.osm.pbf
     https://download.geofabrik.de/europe/germany-latest.osm.pbf

Usage:
    python scripts/preload_geofabrik.py france-latest.osm.pbf --database-url $DATABASE_URL

Schema written (PostGIS variant):
    CREATE TABLE osm_preload (
        id BIGINT,
        region TEXT,
        layer TEXT,          -- buildings | roads | landuse | nature | transit
        tags JSONB,
        geom GEOMETRY(Geometry, 4326)
    );
    CREATE INDEX osm_preload_geom_idx ON osm_preload USING GIST (geom);
    CREATE INDEX osm_preload_layer_idx ON osm_preload (region, layer);

Read path (to be wired into engine/data.py once data exists): before any
Overpass call, check whether the analysis bbox falls inside a preloaded
region (SELECT ... WHERE geom && ST_MakeEnvelope(...)) and build the same
GeoDataFrames the fetch_* functions return today.
"""
import argparse
import json
import sys


LAYER_FILTERS = {
    "buildings": lambda tags: "building" in tags,
    "roads":     lambda tags: "highway" in tags,
    "landuse":   lambda tags: any(k in tags for k in ("landuse", "leisure", "natural")),
    "nature":    lambda tags: any(k in tags for k in ("leisure", "natural", "waterway")),
    "transit":   lambda tags: tags.get("highway") == "bus_stop"
                              or "railway" in tags or "public_transport" in tags,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pbf", help="Geofabrik .osm.pbf extract")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--region", default=None, help="region label (default: pbf stem)")
    args = parser.parse_args()

    try:
        import osmium
    except ImportError:
        sys.exit("pyosmium is required: pip install pyosmium")

    import psycopg2

    region = args.region or args.pbf.split("/")[-1].split("-")[0]
    conn = psycopg2.connect(args.database_url)
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS osm_preload (
            id BIGINT, region TEXT, layer TEXT, tags JSONB,
            geom GEOMETRY(Geometry, 4326));
        CREATE INDEX IF NOT EXISTS osm_preload_geom_idx
            ON osm_preload USING GIST (geom);
        CREATE INDEX IF NOT EXISTS osm_preload_layer_idx
            ON osm_preload (region, layer);
    """)
    conn.commit()

    wkbfab = osmium.geom.WKBFactory()
    batch, count = [], 0

    class Handler(osmium.SimpleHandler):
        def _emit(self, oid, tags, wkb_hex):
            nonlocal batch, count
            tags = dict(tags)
            for layer, pred in LAYER_FILTERS.items():
                if pred(tags):
                    batch.append((oid, region, layer, json.dumps(tags), wkb_hex))
            if len(batch) >= 5000:
                cur.executemany(
                    "INSERT INTO osm_preload VALUES (%s,%s,%s,%s,"
                    "ST_SetSRID(%s::geometry,4326))", batch)
                conn.commit()
                count += len(batch)
                print(f"  {count:,} rows...", flush=True)
                batch = []

        def way(self, w):
            try:
                self._emit(w.id, w.tags, wkbfab.create_linestring(w))
            except Exception:
                pass

        def area(self, a):
            try:
                self._emit(a.id, a.tags, wkbfab.create_multipolygon(a))
            except Exception:
                pass

        def node(self, n):
            tags = dict(n.tags)
            if LAYER_FILTERS["transit"](tags):
                try:
                    self._emit(n.id, n.tags, wkbfab.create_point(n))
                except Exception:
                    pass

    print(f"Processing {args.pbf} → region '{region}' (this takes a while)…")
    Handler().apply_file(args.pbf, locations=True)
    if batch:
        cur.executemany(
            "INSERT INTO osm_preload VALUES (%s,%s,%s,%s,"
            "ST_SetSRID(%s::geometry,4326))", batch)
        conn.commit()
    print(f"Done: {count + len(batch):,} rows loaded.")
    conn.close()


if __name__ == "__main__":
    main()
