"""Urban Pulse v2 API — FastAPI wrapper around engine/pipeline.py.

Job model (brief §3.3): the engine is fully synchronous (requests/osmnx/
geopandas), so analyses run in a ThreadPoolExecutor owned by the app — never
awaited on the event loop. POST /api/analyze returns a job_id immediately;
the worker thread writes status/result into the jobs row; the frontend polls
GET /api/analyze/{job_id} every 2–3 s.

/api/compare uses the same job mechanism (result contains both cities plus a
diff summary) so a two-city run can't hit HTTP proxy timeouts.
"""
import concurrent.futures
import io
import os
import tempfile
import threading
import zipfile
from collections import OrderedDict
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from db.session import SessionLocal, init_db
from db.models import CityCache, Job
from engine.pipeline import run_full_analysis, AnalysisError

load_dotenv()

app = FastAPI(title="Urban Pulse API", version="2.0.0")

# ── CORS: explicit origins + Vercel preview wildcard, never "*" ──────────────
_default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
_extra = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins + _extra,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Background execution ──────────────────────────────────────────────────────
# 2 workers: analyses are memory-heavy; HF free tier is CPU-only with limited
# RAM, so more concurrency would OOM before it would help.
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

# job_id → latest human-readable progress string (in-memory; best-effort)
_progress: dict[str, str] = {}

# job_id → {"buildings": gdf, "hex_grid": gdf, "street_edges": gdf}
# GeoDataFrames for the export endpoints. Kept in-process only (they are not
# JSON) and bounded; evicted artifacts make /api/export return 410 with a
# "re-run the analysis" message.
_artifacts: "OrderedDict[str, dict]" = OrderedDict()
_ARTIFACT_CAP = 6
_artifacts_lock = threading.Lock()


def _store_artifacts(job_id: str, artifacts: dict):
    with _artifacts_lock:
        _artifacts[job_id] = artifacts
        while len(_artifacts) > _ARTIFACT_CAP:
            _artifacts.popitem(last=False)


def _utcnow():
    return datetime.now(timezone.utc)


# ── city_cache provider (brief §5.3) ─────────────────────────────────────────
# TTL is enforced here on read: rows older than CITY_CACHE_TTL_DAYS are
# treated as stale (and simply overwritten by the next write-back).
_CACHE_TTL_DAYS = int(os.getenv("CITY_CACHE_TTL_DAYS", "60"))


class DbCityCache:
    """Moves JSON-able layer dicts in/out of the city_cache table."""

    def get(self, city_name: str, bbox_key):
        with SessionLocal() as db:
            row = db.get(CityCache, city_name)
        if row is None:
            return None
        cached_at = row.cached_at
        if cached_at is not None:
            if cached_at.tzinfo is None:  # SQLite loses tzinfo
                cached_at = cached_at.replace(tzinfo=timezone.utc)
            age_days = (_utcnow() - cached_at).days
            if age_days > _CACHE_TTL_DAYS:
                print(f"[cache] {city_name}: stale ({age_days}d) — refetching")
                return None
        if bbox_key is not None and row.bbox is not None and row.bbox != bbox_key:
            print(f"[cache] {city_name}: bbox mismatch — refetching")
            return None
        return row.raw_data

    def set(self, city_name: str, bbox_key, layers: dict):
        with SessionLocal() as db:
            row = db.get(CityCache, city_name)
            if row is None:
                row = CityCache(city_name=city_name)
                db.add(row)
            row.bbox = bbox_key
            row.raw_data = layers
            row.cached_at = _utcnow()
            db.commit()


_city_cache = DbCityCache()


def _set_job(job_id: str, **fields):
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None:
            return
        for k, v in fields.items():
            setattr(job, k, v)
        db.commit()


def _run_analyze_job(job_id: str, city_name: str, config: dict):
    _set_job(job_id, status="running")
    _progress[job_id] = "Starting analysis…"
    try:
        result = run_full_analysis(
            city_name, config,
            progress=lambda m: _progress.__setitem__(job_id, m),
            cache=_city_cache,
        )
        artifacts = result.pop("artifacts", {})
        _store_artifacts(job_id, artifacts)
        _set_job(job_id, status="done", result=result, completed_at=_utcnow())
    except AnalysisError as e:
        _set_job(job_id, status="error", error=str(e), completed_at=_utcnow())
    except Exception as e:
        _set_job(job_id, status="error",
                 error=f"{type(e).__name__}: {e}", completed_at=_utcnow())
    finally:
        _progress.pop(job_id, None)


_COMPARE_METRICS = [
    "total_buildings", "total_pois", "median_height", "green_space_pct",
    "transport_index_mean", "urban_stress_mean",
]


def _run_compare_job(job_id: str, city_a: str, city_b: str, config: dict):
    _set_job(job_id, status="running")
    try:
        results = {}
        for label, city in (("city_a", city_a), ("city_b", city_b)):
            _progress[job_id] = f"Analyzing {city}…"
            r = run_full_analysis(
                city, config,
                progress=lambda m, c=city: _progress.__setitem__(job_id, f"{c}: {m}"),
                cache=_city_cache,
            )
            r.pop("artifacts", None)  # compare jobs don't serve geodata exports
            results[label] = r

        diff = {}
        ma = results["city_a"]["metrics_summary"]
        mb = results["city_b"]["metrics_summary"]
        for k in _COMPARE_METRICS:
            va, vb = ma.get(k), mb.get(k)
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                diff[k] = {"city_a": va, "city_b": vb, "delta": vb - va}

        _set_job(job_id, status="done", completed_at=_utcnow(), result={
            "kind": "compare",
            "city_a": results["city_a"],
            "city_b": results["city_b"],
            "diff_summary": diff,
        })
    except AnalysisError as e:
        _set_job(job_id, status="error", error=str(e), completed_at=_utcnow())
    except Exception as e:
        _set_job(job_id, status="error",
                 error=f"{type(e).__name__}: {e}", completed_at=_utcnow())
    finally:
        _progress.pop(job_id, None)


# ── Schemas ───────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    city_name: str = Field(min_length=1)
    zone_mode: str = "Entire city"
    config: dict = Field(default_factory=dict)


class CompareRequest(BaseModel):
    city_a: str = Field(min_length=1)
    city_b: str = Field(min_length=1)
    config: dict = Field(default_factory=dict)


# ── Lifecycle ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
def _startup():
    init_db()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    config = dict(req.config or {})
    config["zone_mode"] = req.zone_mode or config.get("zone_mode", "Entire city")
    with SessionLocal() as db:
        job = Job(kind="analyze", city_name=req.city_name.strip(),
                  config=config, status="pending")
        db.add(job)
        db.commit()
        job_id = job.id
    _executor.submit(_run_analyze_job, job_id, req.city_name.strip(), config)
    return {"job_id": job_id}


@app.get("/api/analyze/{job_id}")
def job_status(job_id: str):
    with SessionLocal() as db:
        job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return {
        "status": job.status,
        "progress": _progress.get(job_id),
        "result": job.result if job.status == "done" else None,
        "error": job.error,
    }


@app.post("/api/compare")
def compare(req: CompareRequest):
    config = dict(req.config or {})
    with SessionLocal() as db:
        job = Job(kind="compare",
                  city_name=f"{req.city_a.strip()} vs {req.city_b.strip()}",
                  config=config, status="pending")
        db.add(job)
        db.commit()
        job_id = job.id
    _executor.submit(_run_compare_job, job_id,
                     req.city_a.strip(), req.city_b.strip(), config)
    return {"job_id": job_id}


_EXPORT_LAYERS = ["buildings", "hex_grid", "street_edges"]


@app.get("/api/export/{job_id}")
def export(job_id: str, format: str = "geojson"):
    if format not in ("geojson", "shapefile"):
        raise HTTPException(400, "format must be geojson or shapefile")

    with SessionLocal() as db:
        job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    if job.status != "done":
        raise HTTPException(409, f"Job status is {job.status}, not done")

    with _artifacts_lock:
        artifacts = _artifacts.get(job_id)
    if not artifacts:
        raise HTTPException(
            410, "Geodata for this job is no longer held in memory — "
                 "re-run the analysis to export.")

    slug = job.city_name.replace(", ", "_").replace(" ", "_").lower()

    if format == "geojson":
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for layer in _EXPORT_LAYERS:
                gdf = artifacts.get(layer)
                if gdf is None or getattr(gdf, "empty", True):
                    continue
                zf.writestr(f"{slug}_{layer}.geojson", gdf.to_json())
        buf.seek(0)
        return Response(
            buf.read(), media_type="application/zip",
            headers={"Content-Disposition":
                     f'attachment; filename="urbanpulse_{slug}_geojson.zip"'})

    # shapefile: write each layer with the ESRI driver, zip the whole bundle
    buf = io.BytesIO()
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for layer in _EXPORT_LAYERS:
                gdf = artifacts.get(layer)
                if gdf is None or getattr(gdf, "empty", True):
                    continue
                out_dir = os.path.join(tmp, layer)
                os.makedirs(out_dir, exist_ok=True)
                try:
                    # Shapefile column names are capped at 10 chars; let
                    # geopandas truncate, and stringify list columns first.
                    g = gdf.copy()
                    for c in g.columns:
                        if c != "geometry" and g[c].map(
                                lambda v: isinstance(v, (list, dict))).any():
                            g[c] = g[c].astype(str)
                    g.to_file(os.path.join(out_dir, f"{layer}.shp"),
                              driver="ESRI Shapefile")
                except Exception as e:
                    print(f"[export] shapefile {layer} failed: {e}")
                    continue
                for fn in os.listdir(out_dir):
                    zf.write(os.path.join(out_dir, fn), f"{layer}/{fn}")
    buf.seek(0)
    return Response(
        buf.read(), media_type="application/zip",
        headers={"Content-Disposition":
                 f'attachment; filename="urbanpulse_{slug}_shapefile.zip"'})


# Figures the v1 PDF report expects, rebuilt from the stored Plotly specs.
_PDF_FIGURE_KEYS = [
    "poi_distribution", "building_heights", "morphotype_clusters",
    "far_heatmap", "transport_map", "nature_map", "stress_map",
    "fabric_matrix", "morphotype_radar", "opportunity_surface",
    "cross_morph_transport", "cross_nature_density",
    "terrain_elevation", "terrain_flood_risk",
]


@app.post("/api/report/{job_id}")
def report(job_id: str):
    with SessionLocal() as db:
        job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    if job.status != "done" or not job.result:
        raise HTTPException(409, f"Job status is {job.status}, not done")
    if job.result.get("kind") == "compare":
        raise HTTPException(400, "PDF reports are per-city; use an analyze job")

    import plotly.graph_objects as go
    from engine.report import generate_pdf_report

    charts = job.result.get("charts", {})
    figures = {}
    for key in _PDF_FIGURE_KEYS:
        spec = charts.get(key)
        if spec:
            try:
                figures[key] = go.Figure(spec)
            except Exception as e:
                print(f"[report] rebuild {key} failed: {e}")

    pdf_bytes = generate_pdf_report(
        city_name=job.result.get("city_name", job.city_name),
        metrics_summary=job.result.get("metrics_summary", {}),
        figures=figures,
        ai_insights=job.result.get("ai_insights", ""),
    )
    slug = job.city_name.replace(", ", "_").replace(" ", "_").lower()
    return Response(
        pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition":
                 f'attachment; filename="urbanpulse_{slug}.pdf"'})


@app.get("/api/analysis/{analysis_id}")
def shared_analysis(analysis_id: str):
    """Public, no auth — persistent shareable fetch of a completed job."""
    with SessionLocal() as db:
        job = db.get(Job, analysis_id)
    if job is None or job.status != "done" or not job.result:
        raise HTTPException(404, "Analysis not found")
    return {
        "id": job.id,
        "city_name": job.city_name,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "result": job.result,
    }
