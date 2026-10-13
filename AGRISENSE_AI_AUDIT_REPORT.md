# AgriSense AI — Final Project Audit

**Audit date:** 13 October 2026  
**Scope:** Continued from the previous audit: unresolved dashboard behavior, provider diagnostics, production configuration, security/data checks, and full regression suites.  
**Readiness:** **B. READY FOR DEMO DEPLOYMENT WITH DOCUMENTED LIMITATIONS.** Do not claim every provider is live. No deployment, publishing, Git push, or hosting service creation occurred.

## Summary

Final results: **76 backend tests passed**, **26 frontend tests passed**, production build succeeded (largest JS chunk 225.33 kB), and lint exited 0 with six React effect warnings. Frontend and backend local services returned HTTP 200. Browser checks from the prior audit covered 11 routes at 390 px and signup/profile/calendar CRUD/notification read/logout using an isolated database. A new backend regression test verifies account-specific dashboard metrics update after farmer records are added or changed.

The production build was also run with the configured backend URL: the application bundle included that public URL and contained no app-level loopback API fallback. An initial sandboxed attempt to run this configured build was blocked by child-process policy (`spawn EPERM`); escalation allowed it to complete successfully. The unconfigured production code path reports a clear missing-URL error before making an API request.

Actual provider connectivity improved when tested outside the restricted sandbox. Open-Meteo returned a live seven-day forecast; Mandi options and prices returned HTTP 200. Gemini and PlantNet DNS/TLS reached their hosts, but no authenticated request was made in this pass due possible costs/quotas. GNews DNS/TLS was reachable and its no-key API probe rejected the request as expected; keyed search was not repeated to avoid consuming quota. No API key values were printed.

## Changes made in this final pass

- Dashboard now returns an authenticated `farmer_summary` based on that account’s saved planner crops and tasks. The UI shows **USER ENTERED** counts for signed-in users; shared seed crop/farm-size values continue to say **DEMO**. A backend test checks initial values, create, task completion, and account isolation.
- Production frontend builds no longer fall back to localhost. When `VITE_API_URL` is missing, requests stop with a clear configuration error. Local development retains its loopback default.
- Added strict production CORS configuration through `APP_ENV` and `CORS_ALLOWED_ORIGINS`; development loopback regex is disabled in production.
- Added `AGRISENSE_DB_PATH` for explicit persistent-disk location and `frontend/vercel.json` SPA route rewrites.
- Added root `.python-version` for the tested Python 3.14 line.
- Prior fixes remain: per-account notification read receipts, timezone-safe calendar dates, formula-safe CSV exports, farm-tool retry/error messages, responsive dashboard metrics, and code splitting.

## Feature results

| Area | Result | Evidence and limits |
|---|---|---|
| Startup, health, frontend, CORS | PASS | Local health and frontend HTTP 200; development CORS verified. |
| Tests/build/lint | PASS WITH LINT WARNINGS | 76 backend, 26 frontend; build succeeds; six `react(set-state-in-effect)` warnings. |
| Auth/session/profile/logout | PASS for exercised flows | Browser E2E and backend tests; writes used isolated databases. |
| Dashboard/farmer metrics | PASS for account summary refresh | Regression test verifies own crop/task counts update after create and task completion. Seeded farmer/crop context still demo; not all recommendation inputs are user-specific. |
| Crop Doctor | PARTIAL | Unsupported `.txt` upload rejected in Chrome; live valid-image PlantNet operation not run. |
| Mandi markets | PASS in current live check | Options/prices returned HTTP 200 with Mandi provenance. Market trend requires sufficient compatible dated observations; availability/freshness remains provider-dependent. |
| Profit and deterministic decision | PASS | API validation and calculation tested; unit tests passed. |
| Weather/risk | PASS for current forecast check | Live Open-Meteo forecast HTTP 200 with seven records; fallback remains explicitly labelled if unavailable. |
| Storage | PARTIAL | Sample facilities are labelled; authenticity of real facilities/offers not established. |
| GNews | PARTIAL | DNS/TLS reachable; no-key request returned expected 400. Keyed search not repeated to preserve quota. |
| Gemini | PARTIAL | Transport reachable; prior request failed in sandbox. No new generation request; model/key entitlement unverified. |
| Calendar and farm tools | PASS for tested backend/browser scope | CRUD, validation, ownership covered; browser calendar CRUD passed. Delete error branch is source-covered, not forced in browser. |
| Notifications | PASS | Per-user receipts, authenticated update, and browser flow tested; anonymous read update returns 401. |
| Language, accessibility, navigation | PARTIAL | Hindi dashboard translation/browser smoke and 390 px layout checked. Full translation, contrast, keyboard and assistive tech remain unverified. |

See [AGRISENSE_AI_TEST_CHECKLIST.md](AGRISENSE_AI_TEST_CHECKLIST.md) for the 39 scoped checks.

## Provider diagnostics

DNS resolution succeeded in the FastAPI `.venv` for Gemini, PlantNet, Mandi, GNews, and Open-Meteo. The HTTPS preflight results were Gemini root HTTP 404, PlantNet root HTTP 200, Mandi `/states` HTTP 200, GNews without key HTTP 400, and Open-Meteo forecast HTTP 200. HTTP 404/400 at root/probe paths are not authentication success; they show transport reached the remote service.

Actual API calls, made using a temporary database and no-key integrations: Open-Meteo forecast HTTP 200, Mandi options HTTP 200, Mandi prices HTTP 200. Previous sandbox checks returned connectivity errors for several providers, so those errors describe restricted-network conditions rather than established current provider outages. Keyed GNews/Gemini operations and valid-image PlantNet were not repeated because of quota or potential billing. Therefore key validity/account permissions remain a manual check.

Implementation inspection confirmed HTTPS endpoints, parameter/header formats, and bounded timeouts. PlantNet authentication is a query parameter, Gemini uses an API-key header, and GNews uses a query parameter; avoid logging full request URLs. Provider exceptions are sanitized and provider failure does not crash the API. Open-Meteo fallback values carry a `DEMO` source. The assistant “configured” status confirms presence only and is not a connectivity check.

## Security, repository, and persistence

- Existing `backend/agrisense.db` was preserved. Startup only applies additive migrations; no existing records were reset, seeded, or deleted. New tests and browser write flows used temporary isolated databases.
- Git status was reviewed. The pre-existing modification to `frontend/.env.example` was left intact. Tracked-file review did not find `.env`, local database, virtual environment, `node_modules`, or build output; ignore rules cover these files.
- No secret values were printed, stored in frontend code, or put in reports. Frontend production has no loopback API fallback. The configured Vite API endpoint is injected at build via `VITE_API_URL`.
- Production CORS is exact-origin allowlist mode using `APP_ENV=production` and `CORS_ALLOWED_ORIGINS`. Host `OPTIONS` preflight remains handled by middleware. No wildcard production origins are configured.
- SQLite defaults to `backend/agrisense.db`; on an ephemeral host this would lose data across instance replacement. `AGRISENSE_DB_PATH` now permits a mounted disk path. Multi-instance deployment should use a managed database and a separately tested migration, not shared SQLite files.
- Render currently documents that persistent disks are unavailable on its Free plan, and a disk is limited to one instance. Disk-backed SQLite therefore requires selecting a paid disk-capable configuration; no such choice or charge was made ([Render disk limits](https://render.com/docs/disks)). Runtime pin and Vercel SPA rewrite follow the current [Render Python](https://render.com/docs/python-version) and [Vercel Vite SPA](https://vercel.com/docs/frameworks/frontend/vite) guides.
- Code supports authenticated account isolation for farm records, reports, sessions, and notification read state. Current dashboard includes a small user-entered farm summary but still has shared demo farmer/crop context and some provider/demo-based recommendation values.

## Hosting configuration prepared (not deployed)

### Vercel

- Root: `frontend`; Vite framework; install `npm ci`; build `npm run build`; output `dist`.
- Set `VITE_API_URL=https://<render-service>.onrender.com` in Vercel build environment. This is a public backend URL, never a provider key.
- SPA rewrite is in `frontend/vercel.json`; verify direct nested-route refresh after deployment.

### Render

- Root: `backend`; build `pip install -r requirements.txt`; start `uvicorn main:app --host 0.0.0.0 --port $PORT`; health check `/health`.
- Set `APP_ENV=production`, exact `CORS_ALLOWED_ORIGINS=https://<vercel-domain>`, and `AGRISENSE_DB_PATH=/var/data/agrisense.db`.
- Attach a persistent disk mounted at `/var/data`. Do not assume a free service has durable disk or uninterrupted uptime. SQLite is appropriate only for a single service instance with that persistent mount; consider managed PostgreSQL before scaling horizontally.
- Backend variable names actually read by the code: `PLANTNET_API_KEY`, `GEMINI_API_KEY`, optional `GEMINI_MODEL` (default `gemini-3.8-flash`), `GNEWS_API_KEY`, `MANDI_API_BASE_URL`, optional `GNEWS_CACHE_TTL_SECONDS` (default 300), plus `APP_ENV`, `CORS_ALLOWED_ORIGINS`, and `AGRISENSE_DB_PATH`. Google Maps is currently a reserved, unused key. Secrets belong in Render environment settings, not Git or Vercel.
- Repository has no Python runtime pin. Select a host Python version compatible with installed dependencies before launch; pin it if the host requires reproducibility.

## Remaining manual work

1. Configure Render/Vercel only after approval; no external action was taken.
2. Verify the live Gemini, PlantNet, and GNews keyed operations from the deployed backend while monitoring the provider’s quota/billing dashboard.
3. Confirm actual Vercel origin and Render URL, test CORS, login, direct route refresh, and persistent-disk restart before entering real data.
4. Validate storage listings and finish accessibility/localization review for production use.

No regression was observed: previous suites were 75 backend / 26 frontend; the new dashboard summary regression increased backend coverage to 76 and all tests still pass. The Vite chunk advisory remains resolved.
