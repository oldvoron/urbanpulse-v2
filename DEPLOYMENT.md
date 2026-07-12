# Deployment runbook

Three one-time setups, in this order. Nothing here touches the v1 Space.

## 1. Neon Postgres (~5 min)

1. https://console.neon.tech → create project `urbanpulse` (free tier).
2. Copy the connection string (`postgresql://…neon.tech/neondb?sslmode=require`).
3. Tables are created automatically by the API on first startup (`init_db()`),
   so no SQL to run by hand.
4. Optional (for the §5.2 Geofabrik preload later): open the SQL editor and run
   `CREATE EXTENSION IF NOT EXISTS postgis;` — if this errors on the free tier,
   use the GeoJSON-blob fallback documented in `api/scripts/preload_geofabrik.py`.

## 2. Backend → new Hugging Face Space (~10 min)

1. https://huggingface.co/new-space → name `urbanpulse-api`, SDK **Docker**,
   visibility public, CPU basic (free). This is a NEW Space — do not reuse the
   v1 Space.
2. Space Settings → Variables and secrets:
   - `DATABASE_URL` (secret) — the Neon string from step 1
   - `ANTHROPIC_API_KEY` (secret) — optional, enables AI insights
   - `CORS_ORIGINS` (variable) — your Vercel production URL once known,
     e.g. `https://urbanpulse.vercel.app` (previews are matched by regex
     automatically)
3. Push the `api/` folder as the Space repo:

   ```bash
   cd ~/urbanpulse-v2/api
   git init -b main && git add -A && git commit -m "Urban Pulse API"
   git remote add space https://huggingface.co/spaces/<user>/urbanpulse-api
   git push space main   # authenticate with a HF write token
   ```

   (The `api/README.md` front-matter already declares `sdk: docker`,
   `app_port: 7860`.)
4. Wait for the build, then verify:
   `curl https://<user>-urbanpulse-api.hf.space/health` → `{"status":"ok"}`.
5. Smoke-test a job end to end:

   ```bash
   curl -X POST https://…hf.space/api/analyze \
     -H 'Content-Type: application/json' \
     -d '{"city_name":"Blois, France","zone_mode":"Entire city","config":{"city_size":"Small (< 100k)"}}'
   # then poll: curl https://…hf.space/api/analyze/<job_id>
   ```

## 3. Frontend → Vercel (~5 min)

1. Push this monorepo to GitHub (`urbanpulse-v2`).
2. https://vercel.com/new → import the repo, set **Root Directory = `web`**
   (framework auto-detects Next.js).
3. Environment variable: `NEXT_PUBLIC_API_URL` = the HF Space URL
   (`https://<user>-urbanpulse-api.hf.space`, no trailing slash).
4. Deploy, then add the resulting production domain to the Space's
   `CORS_ORIGINS` variable (step 2.2) and restart the Space.

## Definition-of-done walkthrough

Open the Vercel URL → type a city → Analyze → progress state → 9 tabs of
charts → GeoJSON/Shapefile/PDF export → "Copy share link" opens
`/analysis/<id>` publicly → `/embed/<id>` renders chrome-less for iframes →
Register/Log in/Upgrade show the placeholder modal and do nothing else.

## Known constraints (accepted for the $0 stack)

- HF free tier is CPU-only, ~16 GB RAM: very large cities can OOM or time out,
  same as v1. The 800 km² full-city guard is still in place.
- Export geodata (`/api/export`) is held in Space memory for the last 6 jobs
  only; after a Space restart, exports need a re-run (the JSON result and PDF
  keep working from the DB forever).
- The `jobs.result` JSONB rows are 15–20 MB per analysis; prune old rows
  occasionally if the Neon free-tier storage (0.5 GB) fills up:
  `DELETE FROM jobs WHERE created_at < now() - interval '30 days';`
