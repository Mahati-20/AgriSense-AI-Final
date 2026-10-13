# AgriSense AI Test Checklist

Audit date: 13 October 2026. Automated test databases were isolated. Existing `backend/agrisense.db` received only additive schema migrations at app startup; no existing user rows were changed or deleted. Browser write-flow checks used an isolated temporary database.

| # | Check | Result | Evidence / note |
|---:|---|---|---|
| 1 | FastAPI starts and health endpoint responds | PASS | `GET /health` → 200, `status=ok`. |
| 2 | Vite frontend is accessible | PASS | `GET http://127.0.0.1:5173/` → 200. |
| 3 | Backend automated suite | PASS | 76 tests ran, all passed, including dashboard refresh after farmer data changes. |
| 4 | Frontend automated suite | PASS | 26 tests passed. |
| 5 | Production frontend build | PASS | `npm run build` succeeded; largest JS chunk 225.33 kB, no size advisory. |
| 6 | Frontend-origin CORS | PASS | `Access-Control-Allow-Origin: http://127.0.0.1:5173`. |
| 7 | Dashboard API, provenance, and farmer metrics | PASS | Authenticated summary counts refresh after own crop/task create/update; other account remains isolated. Shared crop/weather context stays demo/provider-labelled. |
| 8 | Crop Doctor live image/provider flow | PARTIAL | Browser rejected a `.txt` upload (“Upload JPEG or PNG images only”); live PlantNet upload/provider response remains unverified. |
| 9 | Live market options and prices | PASS | From backend Python environment, options and price requests returned 200 from Mandi Price API. Current market records are provider sourced. |
| 10 | Profit calculation valid inputs | PASS | Valid request returned 200; formula covered in backend tests. |
| 11 | Profit validation | PASS | Zero quantity returned 422. |
| 12 | Deterministic decision endpoint | PASS | Valid request returned 200; missing-input behavior covered by test. |
| 13 | Live weather and risk | PASS | Open-Meteo returned 200 with seven forecast records during the latest out-of-sandbox provider check. |
| 14 | Storage list and authenticity | PARTIAL | 200 with sample data; real facilities/offers not verified. |
| 15 | Live GNews search | PARTIAL | HTTPS/DNS reachable; unauthenticated API probe returned HTTP 400 as expected. A keyed search was not repeated to avoid consuming provider quota; previous app request returned 502 in restricted network. |
| 16 | Live Gemini assistant response | PARTIAL | HTTPS/DNS reachable; no keyed generation request repeated to avoid provider usage/cost. Previous live request could not connect in restricted environment; credentials/configuration are not independently validated. |
| 17 | Auth/session/profile and account isolation | PASS | Browser signup, profile update, logout passed on isolated DB; backend session and identity tests passed. |
| 18 | Calendar CRUD and ownership | PASS | Browser add/complete/edit/delete passed on isolated DB; backend covers ownership and validation. |
| 19 | Farm-tool CRUD/calculations/report scoping | PASS | Backend tests cover planner/journal/harvest/profit records and account-scoped reports. |
| 20 | Auth guard on farm report | PASS | Unauthenticated `GET /api/farm-tools/report` returned 401. |
| 21 | Weather coordinate validation | PASS | Out-of-range latitude returned 422. |
| 22 | Blank news query validation | PASS | Whitespace-only query returned 422. |
| 23 | Notifications provenance and read isolation | PASS | Per-user receipt tests passed; signed-in browser read flow passed on isolated DB; anonymous mark-read returns 401. |
| 24 | SQLite migration/record-preservation test | PASS | Automated tests use temporary DBs and verify existing rows are preserved; app applied additive table migration. |
| 25 | Real backend process restart persistence | PARTIAL | SQLite and isolated startup tests support persistence; real stop/restart data check was not run. |
| 26 | Five-language UI coverage | PARTIAL | Five dictionaries have 32 keys; browser confirmed Hindi dashboard heading, but many page strings remain English. |
| 27 | Navigation and interactive controls in a browser | PARTIAL | 11 routes rendered; auth/calendar/notification/logout flows exercised. Not every control was clicked. |
| 28 | Mobile layout and accessibility | PARTIAL | At 390 px, 11 routes had no horizontal overflow. Contrast, keyboard traversal, and screen-reader behavior remain unmeasured. |
| 29 | Dashboard updates after user data changes | PASS | Backend regression test creates a farmer crop/task, fetches dashboard, completes task, and verifies refreshed account-scoped metrics. |
| 30 | Timezone-independent calendar date validation | PASS | Unit regression test passed; calendar browser flow passed. |
| 31 | Spreadsheet formula-safe CSV escaping | PASS | Unit tests cover formula prefixes and CSV quoting. |
| 32 | Farm-record delete error recovery | PARTIAL | Source now reports errors and offers retry; forced server-failure UI path was not browser-tested. |
| 33 | Desktop dashboard metric layout | PASS | Headless Chrome at desktop width showed four metric cards in one row after grid fix. |
| 34 | Invalid Crop Doctor file handling | PASS | Browser rejected unsupported `.txt` file before any provider request. |
| 35 | Auth guard/security regression and CORS | PASS | Anonymous notification mutation returned 401; auth/isolation tests and frontend CORS check passed. |
| 36 | Production frontend API URL | PASS | Production app fails closed with a clear message if `VITE_API_URL` is absent; loopback API fallback is development-only. |
| 37 | Production backend CORS | PASS | `APP_ENV=production` disables development loopback regex; only explicit `CORS_ALLOWED_ORIGINS` are accepted. |
| 38 | Repository secret/generated-file hygiene | PASS | Tracked-file review found no `.env`, local DB, venv, `node_modules`, or build artifacts; ignore rules cover them. |
| 39 | Hosting and persistent SQLite configuration | PASS | Exact Vercel/Render commands and required environment variables documented in the pre-deployment report; no host was created. |

## Runtime endpoint notes

- Dashboard, crops, weather/risk, storage, notifications, and assistant status returned 200; demo/fallback source labels are present where applicable.
- The latest backend-context probes reached Mandi options/prices and Open-Meteo successfully (HTTP 200). Gemini and PlantNet authenticated operations were not repeated to avoid provider usage; GNews keyed search was also not repeated to avoid quota consumption. Host DNS/TLS connectivity succeeded for all five providers; a GNews no-key probe returned HTTP 400.
- Calendar, authentication, profile, and notification browser writes were performed only against a temporary isolated database. No audit-created account or farm records were written to the existing database.
- Count the numbered results above as: **30 PASS, 9 PARTIAL, 0 FAIL, 0 BLOCKED** (39 checks total).
