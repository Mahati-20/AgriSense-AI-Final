# AgriSense AI — Final Pre-Deployment Quality Report

**Audit date:** 13 October 2026  
**Decision: B. READY FOR DEMO DEPLOYMENT WITH DOCUMENTED LIMITATIONS.** The core app builds and runs, account-scoped farmer metrics now refresh from saved farm records, and live Open-Meteo and Mandi requests succeeded. Gemini and PlantNet authenticated requests remain unverified; GNews keyed search was not repeated to avoid consuming quota. Nothing was deployed, published, pushed, or charged by a hosting setup.

## Quality gates

| Gate | Result | Evidence |
|---|---|---|
| Backend suite | PASS | 76 tests passed; includes user ownership and dashboard summary refresh after add/update. |
| Frontend suite | PASS | 26 tests passed. |
| Production build | PASS | `npm run build`; largest JS chunk 225.33 kB; no size advisory. A build with the configured backend URL also passed and bundled that URL with no app-level loopback API fallback. Without `VITE_API_URL`, production requests fail closed. |
| Lint | PASS WITH WARNINGS | `npm run lint` exit 0; six `react(set-state-in-effect)` warnings remain. |
| Local services/CORS | PASS | FastAPI health and Vite returned 200; local frontend CORS worked. |
| Browser checks | PASS FOR EXERCISED FLOWS | Prior headless Chrome run covered 11 routes at 390 px, signup/profile/calendar CRUD/notification read/logout on isolated DB, and desktop dashboard grid. Dashboard data refresh has a new API regression test; that specific post-mutation refresh was not repeated through browser clicks. |
| Open-Meteo | PASS | Backend-context live forecast returned 200 with seven records. |
| Mandi | PASS | Backend-context live options and prices returned 200 with `Mandi Price API` provenance. |
| GNews | PARTIAL | DNS/TLS reachable; no-key endpoint returned 400. Keyed search not repeated to avoid consuming account quota; prior sandboxed request returned 502. |
| Gemini | PARTIAL | DNS/TLS reachable; previous keyed request could not connect in sandbox. No new generation call was made due to possible provider charges/quota. Key validity and model access remain unverified. |
| PlantNet | PARTIAL | DNS/TLS reachable; upload path validated using rejected `.txt` file, but no valid-image provider request was sent because it may consume daily quota. Key validity and account feature access remain unverified. |

## Changes made

- Added per-account dashboard summaries for farmer-entered crop profiles and open tasks; the dashboard fetch reflects subsequent create and completion updates. Shared seed crops and farm size remain visibly labelled demo data.
- Restricted production frontend API calls to configured `VITE_API_URL`; absent configuration now yields a clear error instead of a loopback request.
- Added production CORS settings: `APP_ENV=production` disables the development loopback regex and only configured origins are accepted.
- Added `AGRISENSE_DB_PATH` support for mounting SQLite on a persistent disk.
- Added Vercel SPA routing rewrite in `frontend/vercel.json`.
- Pinned Render’s Python runtime to 3.14 in the repository-root `.python-version`; local tests run on Python 3.14.7.
- Earlier audit fixes remain: account-specific notification receipts, timezone-safe date validation, formula-safe CSV cells, farm-tool retry/error feedback, responsive dashboard grid, and frontend vendor chunk splitting.

## Data integrity and security

The existing database was never reset, seeded, or replaced. `notification_read_receipt` was added through the startup migration and existing rows were preserved. Automated and browser mutation flows used isolated temporary databases. `.env`, the local database, `.venv`, `node_modules`, and build output are ignored and absent from the tracked-file list. No secret values were printed or included in reports. The existing user modification to `frontend/.env.example` was preserved.

Private records, farm-tool CRUD, notification read receipts, and reports are account-scoped with authentication/ownership checks covered by backend tests. CSV formula escaping has unit coverage. The API reports sample/fallback provenance. Live Mandi and weather checks succeeded; shared seeded farm context, storage facilities, and sample notifications remain demo/sample information. UI accessibility beyond the responsive overflow smoke and full-page translation remain incomplete.

## Provider diagnostics (sanitized)

From the same `.venv` Python environment used by FastAPI, all five provider hosts resolved DNS. Direct HTTPS probes succeeded at the transport layer: Gemini root returned HTTP 404, PlantNet root HTTP 200, configured Mandi `/states` HTTP 200, GNews without credentials HTTP 400, and Open-Meteo forecast HTTP 200. These status codes demonstrate network/TLS reachability; they do not prove authentication or each product operation.

Actual no-key/no-cost operations were then run in a temporary database: Open-Meteo forecast returned 200; Mandi options and price endpoints returned 200. No PlantNet image, Gemini generation, or keyed GNews search was sent in the final check to avoid provider quota or possible billing. Previous failures occurred under restricted network conditions, so those results are not treated as proof of current provider outages. Inspect credentials in hosting settings if those keyed integrations fail after deployment; never put them in Vite variables.

Timeouts in provider code are bounded (generally 10–15 seconds, Gemini uses a bounded retry path); provider failures are mapped to API errors or explicitly labelled weather demo fallback and do not stop FastAPI. PlantNet uses `api-key` query authentication, Gemini uses the `x-goog-api-key` header, and GNews uses an `apikey` query parameter. Mandi uses the configured HTTPS base URL without an API credential. Do not log full provider URLs because some contain credentials in query parameters.

## Vercel + Render deployment preparation

No services were created and no hosting/deployment action was taken. Create a **private** GitHub repository manually after reviewing the pending working tree; do not commit local `.env` or database files.

### Vercel frontend

- **Root directory:** `frontend`
- **Framework:** Vite
- **Install command:** `npm ci`
- **Build command:** `npm run build`
- **Output directory:** `dist`
- **Required environment:** `VITE_API_URL=https://<your-render-service>.onrender.com` (backend origin only; no trailing path and no secret). Set it for Production and Preview only if the preview backend explicitly allows that origin.
- `frontend/vercel.json` rewrites SPA paths to `index.html`; verify a nested route refresh after the first deployment.

### Render backend

- **Root directory:** `backend`
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Health check path:** `/health`
- **Required settings:**
  - `APP_ENV=production`
  - `CORS_ALLOWED_ORIGINS=https://<your-vercel-project>.vercel.app` (comma-separated exact origins for any custom production domains; no wildcard)
  - `AGRISENSE_DB_PATH=/var/data/agrisense.db`
  - `PLANTNET_API_KEY` (only if enabling Crop Doctor live identification)
  - `GEMINI_API_KEY` (only if enabling assistant generation)
  - `GNEWS_API_KEY` (only if enabling live news)
  - `GEMINI_MODEL` (optional; code default is `gemini-3.8-flash`)
  - `MANDI_API_BASE_URL` (configured HTTPS service URL; code validates HTTPS)
  - `GNEWS_CACHE_TTL_SECONDS` (optional; code default 300 seconds)

Attach a Render persistent disk mounted at `/var/data` before starting the service. SQLite defaults to `backend/agrisense.db`, which is suitable for local development but is ephemeral on hosts without a persistent disk. Render documents that persistent disks are not available on its Free plan; choosing a disk-capable plan may incur cost. Only files under the mount path persist, and a disk is limited to one service instance ([Render disks](https://render.com/docs/disks)). For multi-instance scaling, use a managed database such as PostgreSQL and plan a tested migration before changing architecture. No database architecture migration was performed.

The Python runtime is pinned to the 3.14 line in the repository-root `.python-version`, matching local Python 3.14.7 tests; Render supports `.python-version` pins ([Render Python version](https://render.com/docs/python-version)). The start command binds to `0.0.0.0` and Render’s `$PORT` as required by [Render web service docs](https://render.com/docs/web-services). Render environment settings supply secrets; do not upload `.env`.

Vercel’s [Vite SPA guide](https://vercel.com/docs/frameworks/frontend/vite) documents the `vercel.json` rewrite used here for deep links.

## Final regression commands

```powershell
.\.venv\Scripts\python.exe -m unittest backend.test_main
cd frontend
node --experimental-strip-types --test tests/*.test.ts
npm run build
npm run lint
```

Outcomes: 76/76 backend tests, 26/26 frontend tests, successful build, and lint exit 0 with six warnings. The first sandboxed configured-URL build was blocked by sandbox child-process policy (`spawn EPERM`); the same configured build succeeded after escalation, with the public backend URL baked in and no loopback URL in the application bundle. This was an execution restriction, not a code/build failure. No dependencies were changed.

## Manual actions before representing all integrations as live

- In hosting dashboards, add backend-only credentials and confirm each key/model/account is active. Do not send secrets through chat or commit them.
- Choose a Render plan with persistent disk if farmer accounts/data must survive redeploys. This manual cost choice was not made.
- After deploying with approval, verify Gemini generation, PlantNet valid-image identification, and GNews keyed search from Render; these final checks are intentionally not claimed as passed.
- Confirm exact Vercel production origin in `CORS_ALLOWED_ORIGINS` and set Vercel `VITE_API_URL` to the Render origin, then test route refresh and auth flows.
- Verify persistent-disk attachment and restart persistence before creating real farmer accounts/data.
- Complete keyboard, contrast, screen-reader and full translation review if required for the target audience.

For feature-level results, see [AGRISENSE_AI_AUDIT_REPORT.md](AGRISENSE_AI_AUDIT_REPORT.md) and the [39-check test checklist](AGRISENSE_AI_TEST_CHECKLIST.md).
