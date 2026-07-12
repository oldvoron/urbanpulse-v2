# Urban Pulse v2

Ground-up platform rewrite of Urban Pulse around the unchanged v1 Python analytics
engine (OSM/Overture fetch → morphology, street network, transport accessibility,
nature/green space, urban stress index, fabric typology, district scores → Plotly
charts → PDF export).

v1 (Streamlit, on its original Hugging Face Space) stays live and untouched; this
repo is the fully separate v2 build.

## Layout

- **`api/`** — FastAPI backend. Wraps the framework-independent analytics engine
  (`api/engine/`) behind a job-based REST API. Deployed as a Docker Space on
  Hugging Face (separate from the v1 Space). State lives in Neon Postgres
  (`jobs`, `city_cache`, `users` tables).
- **`web/`** — Next.js (App Router, TypeScript, Tailwind) frontend deployed to
  Vercel. Talks to the API via `web/lib/api.ts` (`NEXT_PUBLIC_API_URL`).

The two halves are independent deployables; the only contract between them is
the REST API (see `api/README.md`).

## Local development

```bash
# backend
cd api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --port 7860 --reload   # SQLite fallback if DATABASE_URL unset

# frontend
cd web
npm install
NEXT_PUBLIC_API_URL=http://localhost:7860 npm run dev
```

Auth ("Register"/"Log in") and payments ("Upgrade") are **decorative UI
placeholders only** — a modal explaining accounts aren't live yet. No auth or
payment logic exists anywhere in this codebase.
