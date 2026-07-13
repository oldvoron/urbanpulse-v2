# Urban Pulse API

FastAPI backend for Urban Pulse v2. Wraps the framework-independent analytics
engine (`engine/`) behind a job-based REST API. Deployed as a Docker container
on **Google Cloud Run** (always-free tier: 2M requests/month, scales to zero).

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/analyze` | `{city_name, zone_mode, config}` → `{job_id}`; runs `run_full_analysis` in a background thread |
| GET | `/api/analyze/{job_id}` | `{status: pending\|running\|done\|error, result, error}` — poll every 2–3 s |
| POST | `/api/compare` | `{city_a, city_b, config}` → job with both result sets + numeric diff summary |
| GET | `/api/districts?city_name=…` | Auto-detected district list (OSM admin levels 8→9→10), cached |
| GET | `/api/export/{job_id}?format=geojson\|shapefile` | Raw geodata (buildings, hex grid, street edges) |
| POST | `/api/report/{job_id}` | Dark, branded PDF report |
| GET | `/api/card/{job_id}` | 1200×630 share-card PNG (also the OG preview image) |
| POST | `/api/waitlist` | `{email}` → paid-plans waitlist (users.email) |
| GET | `/api/analysis/{id}` | Public shareable fetch of a completed job's result |
| GET | `/health` | Liveness check |

## Environment

- `DATABASE_URL` — Neon Postgres connection string. If unset, falls back to a
  local SQLite file (dev only).
- `CORS_ORIGINS` — comma-separated extra allowed origins (the Vercel
  production domain). Vercel preview deployments are matched by regex.
- `PORT` — injected by Cloud Run (defaults to 8080); the Dockerfile CMD reads
  it at container start. Do not set it manually.

## Deploying (Google Cloud Run)

```bash
cd api
gcloud run deploy urbanpulse-api \
  --source . \
  --region europe-west1 \
  --allow-unauthenticated \
  --max-instances 2 \
  --set-env-vars DATABASE_URL=<neon-connection-string>
```

Then point the Vercel frontend's `NEXT_PUBLIC_API_URL` at the printed
service URL and add the Vercel production domain to `CORS_ORIGINS`
(`gcloud run services update urbanpulse-api --set-env-vars CORS_ORIGINS=…`).

## Local development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --port 7860 --reload   # SQLite fallback if DATABASE_URL unset
```

## Engine

`engine/data.py`, `engine/metrics.py`, `engine/charts.py`, `engine/report.py`
are the v1 computation modules (data.py carries the composite-Overpass-query
rework — see `engine/DATA_LAYER_STATUS.md`). `engine/pipeline.py` is the
orchestration layer extracted from the v1 Streamlit `app.py` —
`run_full_analysis(city_name, config) -> dict` with no web framework anywhere
in the call chain.
