---
title: Urban Pulse API
emoji: 🔌
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# Urban Pulse API

FastAPI backend for Urban Pulse v2. Wraps the framework-independent analytics
engine (`engine/`) behind a job-based REST API.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/analyze` | `{city_name, zone_mode, config}` → `{job_id}`; runs `run_full_analysis` in a background thread |
| GET | `/api/analyze/{job_id}` | `{status: pending\|running\|done\|error, result, error}` — poll every 2–3 s |
| POST | `/api/compare` | `{city_a, city_b, config}` → both result sets + numeric diff summary |
| GET | `/api/export/{job_id}?format=geojson\|shapefile` | Raw geodata (buildings, hex grid, street edges) |
| POST | `/api/report/{job_id}` | PDF report bytes (v1 `report.py`, unchanged) |
| GET | `/api/analysis/{id}` | Public shareable fetch of a completed job's result |
| GET | `/health` | Liveness check |

## Environment

- `DATABASE_URL` — Neon Postgres connection string. If unset, falls back to a
  local SQLite file (dev only).
- `ANTHROPIC_API_KEY` — optional; enables AI insights in results/PDF.
- `CORS_ORIGINS` — comma-separated extra allowed origins (the Vercel production
  domain). Vercel preview deployments are matched by regex.

## Engine

`engine/data.py`, `engine/metrics.py`, `engine/charts.py`, `engine/ai.py`,
`engine/report.py` are the v1 computation modules. `engine/pipeline.py` is the
orchestration layer extracted from the v1 Streamlit `app.py` —
`run_full_analysis(city_name, config) -> dict` with no Streamlit anywhere in
the call chain.
