# Deployment runbook

Three one-time setups, in this order. Nothing here touches the v1 Space.
(Backend host is **Google Cloud Run** — HF Docker Spaces are no longer free;
superseded per Addendum 3.)

## 1. Neon Postgres (~5 min)

1. https://console.neon.tech → create project `urbanpulse` (free tier).
2. Copy the connection string (`postgresql://…neon.tech/neondb?sslmode=require`).
3. Tables are created automatically by the API on first startup (`init_db()`),
   so no SQL to run by hand.
4. Optional (for the §5.2 Geofabrik preload later): open the SQL editor and run
   `CREATE EXTENSION IF NOT EXISTS postgis;` — if this errors on the free tier,
   use the GeoJSON-blob fallback documented in `api/scripts/preload_geofabrik.py`.

## 2. Backend → Google Cloud Run (~10 min)

Prereqs: a Google Cloud project with billing enabled (the always-free tier —
2M requests/month, 180k vCPU-s — covers this workload; `--max-instances 2`
caps any surprise) and the `gcloud` CLI authenticated (`gcloud init`).

```bash
cd api
gcloud run deploy urbanpulse-api \
  --source . \
  --region europe-west1 \
  --allow-unauthenticated \
  --max-instances 2 \
  --set-env-vars DATABASE_URL=<neon-connection-string>
```

Notes:
- The container listens on Cloud Run's injected `PORT` (Dockerfile handles it);
  no port configuration needed.
- Memory: analyses are RAM-heavy — if large cities OOM, redeploy with
  `--memory 2Gi --cpu 2` (still within reasonable free-tier usage at low volume).
- **Deployment test** (required after the port-handling change): once deployed,
  `curl https://<service-url>/health` → `{"status":"ok"}`, then a full job:

  ```bash
  curl -X POST https://<service-url>/api/analyze \
    -H 'Content-Type: application/json' \
    -d '{"city_name":"Blois, France","zone_mode":"Entire city","config":{"city_size":"Small (< 100k)"}}'
  # poll: curl https://<service-url>/api/analyze/<job_id>
  ```

## 3. Frontend → Vercel (~5 min)

1. Push this monorepo to GitHub (`urbanpulse-v2`).
2. https://vercel.com/new → import the repo, set **Root Directory = `web`**
   (framework auto-detects Next.js).
3. Environment variable: `NEXT_PUBLIC_API_URL` = the Cloud Run service URL
   (`https://urbanpulse-api-….run.app`, no trailing slash).
4. Deploy, then add the resulting production domain to the backend:
   `gcloud run services update urbanpulse-api --region europe-west1 \
      --set-env-vars CORS_ORIGINS=https://<your-domain>` (preview deploys are
   matched by the built-in `*.vercel.app` regex).

## Definition-of-done walkthrough

Open the Vercel URL → type a city → Analyze → progress state → 9 tabs of
charts (with the selected zone highlighted) → GeoJSON/Shapefile/PDF export →
"Copy share link" opens `/analysis/<id>` (server-rendered, with OG preview
card) → `/embed/<id>` and `/embed/<id>/badge` render chrome-less for iframes →
Register/Log in/Upgrade show the placeholder modal (waitlist email works).

## Known constraints (accepted for the $0 stack)

- Cloud Run scales to zero: the first request after idle pays a cold start
  (~10–20 s for this image). Fine for a free product; `--min-instances 1`
  removes it but costs money.
- In-flight background jobs die if the instance is stopped mid-run; Cloud Run
  keeps instances alive while requests poll, which the frontend does every
  2.5 s, so in practice jobs complete. (A managed queue is the paid-tier fix.)
- Export geodata (`/api/export`) is held in instance memory for the last 6
  jobs; after a scale-to-zero cycle, exports need a re-run (JSON results, the
  PDF, and the share card persist in the DB forever).
- The `jobs.result` JSONB rows are 15–20 MB per analysis; prune old rows
  occasionally if the Neon free-tier storage (0.5 GB) fills up:
  `DELETE FROM jobs WHERE created_at < now() - interval '30 days';`
