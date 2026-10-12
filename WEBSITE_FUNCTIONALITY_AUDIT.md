# AgriSense AI — Website Functionality Audit

**Audit date:** 2026-10-12 (Asia/Kolkata)
**Scope:** React/Vite frontend, FastAPI backend, existing SQLite database, configured provider integrations.
**Status definitions:** WORKING = exercised successfully; PARTIALLY WORKING = verified with material limits; BROKEN = failed verification; NOT IMPLEMENTED = no implementation; NOT VERIFIED = evidence is insufficient.

## 1. Overall status

This inventory contains **43 distinct audit assertions** across routes, controls, integrations, authentication/data boundaries, and automated checks. Related layers are separate assertions (for example, the Ask AgriSense page, Gemini HTTP endpoint, and live Gemini call); repeated tests within one layer are not counted as separate features.

| Status | Count |
|---|---:|
| WORKING | 12 |
| PARTIALLY WORKING | 28 |
| BROKEN | 0 |
| NOT IMPLEMENTED | 1 |
| NOT VERIFIED | 2 |
| **Total** | **43** |

**Fixed during this implementation and audit:** six issues: the assistant input was prefilled with a sample question; Enter did not submit chat; legacy calendar writes were not account-scoped; the brand/favicon used the Vite default; signup password-strength validation differed between frontend and backend; and an existing auth test left a SQLite connection open on Windows. Gemini itself did not fail in this environment: its live backend request succeeded. No unsupported claim of a browser-tested UI is made.

**Readiness:** Ready for a limited demonstration only; not ready for deployment with private farm records.

## 2. Master feature checklist

- [x] PARTIALLY WORKING — `/` landing page and feature links; build verified, browser not exercised.
- [x] PARTIALLY WORKING — Main navigation, mobile menu, and sidebar links; implementation inspected, not browser exercised.
- [x] PARTIALLY WORKING — Signup form and real backend account creation; backend validated, UI not browser exercised.
- [x] PARTIALLY WORKING — Login form, invalid credentials, and post-login redirect; backend validated, UI not browser exercised.
- [x] PARTIALLY WORKING — Logout control and session revocation; backend test passes, browser flow not exercised.
- [x] PARTIALLY WORKING — Session restoration and protected calendar route; backend auth tested, refresh workflow not browser exercised.
- [x] PARTIALLY WORKING — Dashboard route, provider summary, and feature links; backend tests/build pass, data is shared demo.
- [x] PARTIALLY WORKING — Crop Doctor page, upload and retry controls; mocked PlantNet/error tests pass, no live image or browser upload.
- [x] PARTIALLY WORKING — Weather page; live API works, but the frontend page was not browser exercised.
- [x] PARTIALLY WORKING — Market and profit page; live service recovered after a 429 but returned stale dated records.
- [x] PARTIALLY WORKING — Storage Finder; helper/API tests pass, facilities are sample data and page not browser exercised.
- [x] PARTIALLY WORKING — News page and article controls; live API works, frontend search/filter flow not browser exercised.
- [x] PARTIALLY WORKING — Calendar page; API ownership and persistence tests pass, browser workflow not exercised.
- [x] PARTIALLY WORKING — Ask AgriSense page; live Gemini endpoint works, browser message display was not exercised.
- [x] PARTIALLY WORKING — Notifications; seeded data and read control exist, but read-state is shared and API unauthenticated.
- [x] PARTIALLY WORKING — Nested not-found panel and global fallback; route code/build checked, no dedicated global 404.
- [ ] NOT IMPLEMENTED — Profile/settings UI, password change, recovery, email verification, or account deletion.
- [x] WORKING — Gemini model ID and `generateContent` REST request format match current official docs; live backend request returned HTTP 200 and a non-empty answer.
- [x] WORKING — Custom AgriSense sprout/sunrise wordmark icon and matching SVG favicon replace the default Vite mark.
- [x] PARTIALLY WORKING — Reduced-motion and keyboard-focus CSS exists; assistive-technology and browser keyboard verification remain outstanding.
- [x] PARTIALLY WORKING — PlantNet forwarding and response mapping; mocked tests pass, live image request not made.
- [ ] NOT VERIFIED — Live PlantNet identification; no suitable plant photograph exists in project assets.
- [x] WORKING — Open-Meteo live forecast; HTTP 200 and `Open-Meteo` source label observed.
- [x] PARTIALLY WORKING — Mandi integration; live request recovered to HTTP 200 with 200 records, but marked stale; an earlier request returned HTTP 429.
- [x] WORKING — GNews live agricultural search; HTTP 200 observed; error/empty/filter behavior covered by tests.
- [x] WORKING — Backend signup password strength and duplicate-account checks; automated tests pass.
- [x] WORKING — Backend session creation, identity lookup and logout revocation; automated tests pass.
- [x] WORKING — Calendar cross-account isolation; two-user automated test passes.
- [x] WORKING — SQLite schema migration preserves legacy rows and marks ownerless tasks as demo; migration test and existing DB startup migration pass.
- [x] PARTIALLY WORKING — Dashboard navigation and retry controls; handler/API code inspected, no browser clicks.
- [x] PARTIALLY WORKING — Market selectors, retry controls, price-to-calculator action, and calculator inputs; backend calculation tests pass, no browser clicks.
- [x] PARTIALLY WORKING — Crop upload, plant-part selector, analyze, remove, disease screening and retry controls; source/mocked tests checked, no browser clicks.
- [x] PARTIALLY WORKING — Storage search, type filter, sort, item selection, details, clear filters, retry and directions; helper/API tests pass, no browser clicks.
- [x] PARTIALLY WORKING — Calendar add/edit/cancel/complete/delete/retry controls; APIs and ownership tested, no browser clicks.
- [x] PARTIALLY WORKING — News search, language/country/sort filters, suggestion buttons, retry and article links; API tested, no browser clicks.
- [x] PARTIALLY WORKING — Chat send/retry/keyboard controls; live endpoint and keyboard helper tests pass, chat rendering not browser-tested.
- [x] PARTIALLY WORKING — Notification retry/read control; UI handler exists, but changes shared demo state.
- [x] WORKING — Backend error/validation handling covered by unit tests for malformed, empty, timeout, quota and provider failures.
- [x] WORKING — Backend automated test suite; 69 passed.
- [x] WORKING — Frontend automated tests; 8 passed across storage and chat-keyboard helpers.
- [x] WORKING — TypeScript and production build; successful with bundle-size warning.
- [x] PARTIALLY WORKING — Frontend lint; exits successfully with six React effect warnings.
- [ ] NOT VERIFIED — Real-browser route, visual, keyboard, responsive, console and network workflows; browser automation and browser binaries were unavailable.

## A. Executive summary

The existing application already contains a responsive agricultural landing page, dashboard and feature modules, a shared earthy CSS system, reduced-motion rules, and backend integrations. This pass replaced the default purple Vite favicon with an AgriSense SVG, introduced a matching custom sprout/sunrise wordmark mark, and completed a safe calendar ownership migration. Signup/login/logout use real FastAPI operations, PBKDF2 password hashes, expiring/revocable opaque sessions, and an in-memory attempt limiter. Calendar endpoints now require a valid session and scope new tasks to their owner. Existing unowned calendar rows were retained and relabelled as read-only demo examples.

All 69 backend unit tests pass. All 8 frontend Node tests pass, including chat keyboard handling. The production build and lint command exit successfully with advisory warnings. Live Open-Meteo and GNews calls returned HTTP 200. A live Gemini generation returned HTTP 200 with a non-empty answer. The mandi provider first returned HTTP 429, then returned HTTP 200 with 200 records flagged stale; current pricing is therefore not verified. No browser automation tool or browser binary was available, so visual and end-to-end browser behavior has not been verified.

The site is suitable for a **limited demonstration** with clearly labelled data. It is **not deployment-ready for private farm records**: most farm data and several API endpoints remain shared/public demo or information endpoints, access tokens are stored in `sessionStorage`, account profile editing has no UI, and password recovery/email verification are not implemented. Gemini was exercised live; PlantNet was not because there is no suitable plant photo in the project.

## B. Page-by-page audit

| Route | Purpose | Status | Test method and result | Remaining issue |
|---|---|---|---|---|
| `/` | Public landing page and feature navigation | PARTIALLY WORKING | Source inspection and production build passed; browser not available | Browser/mobile interaction not exercised. |
| `/login` | Account login | PARTIALLY WORKING | Backend signup/login/logout tests pass; frontend build passes | Form and redirect behavior not browser-tested. |
| `/signup` | Account creation | PARTIALLY WORKING | Duplicate account, password storage, weak-password rejection and auth-session backend tests pass | Frontend form not browser-tested; no email verification. |
| `/dashboard` | Summary of farm, weather, market and task information | PARTIALLY WORKING | Backend dashboard data and missing-market regression tests pass; page builds | Displays seeded/shared farm examples; not user-specific. Browser route not exercised. |
| `/dashboard/crop-doctor` | Plant species identification and separate limited screening | PARTIALLY WORKING | PlantNet request mapping, malformed response, missing key, quota and image signature tests pass (mocked provider); page builds | No live PlantNet image request was made. Identification must not be treated as diagnosis. |
| `/dashboard/market` | Mandi records and profit calculations | PARTIALLY WORKING | Profit validation/unit tests pass; live provider later returned HTTP 200 with 200 records marked stale after an earlier HTTP 429; page builds | Current pricing remains unverified; user must confirm price date/units before using calculations. |
| `/dashboard/weather` | Forecast and weather risk | PARTIALLY WORKING | Live Open-Meteo request returned HTTP 200 with `Open-Meteo` source; fallback behavior is unit-tested | Location selection is limited to query parameters/default location; browser interaction not exercised. |
| `/dashboard/storage` | Storage facility listing and details | PARTIALLY WORKING | List/detail, sample labels, directions URL and failure behavior tested with mocked database rows | Facilities and capacity/prices are demo records, not verified availability. |
| `/dashboard/calendar` | Farm task planning | PARTIALLY WORKING | API tests verify login requirement, owner-scoped reads/writes, cross-user denial, validation, and legacy migration | Browser workflow not exercised; legacy unowned entries remain shared, read-only examples. |
| `/dashboard/news` | Agricultural news search | PARTIALLY WORKING | Live GNews request returned HTTP 200; backend tests cover empty, malformed, quota, timeout and missing-key cases | Browser search/filter workflow not exercised; results depend on provider access and plan limits. |
| `/dashboard/assistant` | Gemini agricultural assistance | PARTIALLY WORKING | Live `POST /api/assistant` returned HTTP 200 and a non-empty Gemini answer; mocked tests cover missing key, quota, retry and malformed response | Browser message rendering was not exercised; chat does not send conversation history; responses need independent agricultural verification. |
| `/dashboard/notifications` | Demo notification list | PARTIALLY WORKING | Source inspection and production build; API is backed by seeded shared rows | Read-state mutation is shared and the endpoint is not authenticated; not a private notification feature. |
| `/dashboard/*` unknown path | Dashboard not-found panel | PARTIALLY WORKING | Route definition inspected; frontend build passes | Browser/back-button behavior not exercised. |
| `*` outside dashboard | Fallback navigation | PARTIALLY WORKING | Route definition inspected; frontend build passes | Unknown URLs redirect to `/` rather than a dedicated 404 page. |
| Profile/settings | Account preferences | NOT IMPLEMENTED | No profile/settings page route or visible account settings UI found | Backend supports updating the account name, but there is no UI, password change, or account deletion flow. |

## C. Feature audit table

| Feature | Status | Evidence or test performed | Issue or limitation |
|---|---|---|---|
| Landing page | PARTIALLY WORKING | Route/component inspection; production build | No browser verification. |
| Custom brand mark and favicon | WORKING | Replaced default purple favicon and used inline SVG sprout/sunrise mark in brand treatments; production build | Visual rendering not browser-verified. |
| Signup | PARTIALLY WORKING | Backend tests for account creation, duplicate email, complexity validation and password hashing | Frontend form not browser-tested; no verification email. |
| Login | PARTIALLY WORKING | Backend login and invalid-credential tests | Frontend form/redirect not browser-tested. |
| Logout | PARTIALLY WORKING | Backend session revocation test; frontend clears local session in `finally` | Browser flow not exercised. |
| Dashboard | PARTIALLY WORKING | Backend regression tests and production build | Seeded farmer/crop records are shared and not associated with accounts. |
| Crop Doctor | PARTIALLY WORKING | Mocked PlantNet endpoint tests, including unsupported/invalid responses | No live request or browser upload exercised. |
| Weather | WORKING | Live Open-Meteo request returned HTTP 200 and source label `Open-Meteo`; fallback tested | Only the default Bengaluru location was live-checked. |
| Market & Profit | PARTIALLY WORKING | Profit calculations/unit handling tested; live mandi provider returned 200 stale records after an earlier 429 | Current price freshness is not assured; provider appears intermittently rate-limited. |
| Storage Finder | PARTIALLY WORKING | API list/detail, demo labels and directions tests | Data are hardcoded/sample records, not live facility inventory. |
| Agri News | WORKING | Live GNews request returned HTTP 200; failure/empty response tests pass | No browser search workflow; results depend on GNews plan and limits. |
| Farm Calendar | PARTIALLY WORKING | Authentication, owner scoping, validation, and migration tests pass | UI/browser not tested; pre-existing rows are retained as shared read-only examples. |
| Ask AgriSense | PARTIALLY WORKING | Gemini live generation returned HTTP 200; mocked tests cover quota, timeout and malformed replies | Browser UI not exercised; only current message is sent, without prior turns. |
| Mobile navigation | PARTIALLY WORKING | Accessible menu markup and responsive CSS inspected; build passes | No touch/mobile browser check. |
| Responsive layout | PARTIALLY WORKING | Responsive CSS breakpoints inspected; build passes | No desktop/tablet/mobile viewport verification. |
| Error handling | WORKING | Backend tests cover validation, provider errors, timeouts, malformed payloads, empty results and retries | End-to-end UI rendering of errors not browser-tested. |
| Security and privacy | PARTIALLY WORKING | Salted PBKDF2 hashes, opaque expiring sessions, logout revocation, rate-limit tests; new cross-user calendar test | Token is in `sessionStorage`; most demo/data endpoints remain public/shared; rate limiter is process-local. |
| Reduced motion and keyboard focus | PARTIALLY WORKING | CSS rules and visible focus styles inspected | Assistive technology and keyboard workflows not browser-tested. |
| 404 handling | PARTIALLY WORKING | Route definitions inspected | No dedicated global 404 page. |

## D. Button and form audit

The status below describes code/API behavior plus automated evidence. Every browser interaction remains unverified because no browser was available. API references identify the handler called by the control; local-only actions are marked accordingly.

| Control | Status | Evidence / limitation |
|---|---|---|
| Landing nav section anchors, login and signup links | PARTIALLY WORKING | Real route/anchor targets found; browser not exercised. |
| Responsive landing menu | PARTIALLY WORKING | `aria-expanded`, accessible label, open/close state and mobile CSS found; not touch-tested. |
| Signup/login submit | PARTIALLY WORKING | Calls real backend; backend auth tests pass; no browser submission. |
| Password show/hide | PARTIALLY WORKING | Real input type toggle in source; no browser interaction test. |
| Dashboard navigation and retry | PARTIALLY WORKING | Real navigation/API retry handlers found; browser not exercised. |
| Crop image upload/analysis | PARTIALLY WORKING | Upload validation and provider logic covered by backend tests; no browser upload or live PlantNet call. |
| Weather retry/location controls | PARTIALLY WORKING | API and retry logic inspected; only default location checked live. |
| Market filters, refresh and calculator | PARTIALLY WORKING | Inputs call API/calculation; calculations are unit-tested; live market API rate-limited. |
| Storage search/filter/sort/detail/directions | PARTIALLY WORKING | Filtering helpers and backend detail/directions tests exist; browser interactions not exercised. |
| Calendar create/edit/complete/delete | PARTIALLY WORKING | Backend endpoints and ownership checked; legacy demo tasks hide mutation controls; no browser workflow. |
| News query/filter/retry/article links | PARTIALLY WORKING | Live search API succeeded and backend failure cases tested; browser workflow not exercised. |
| Ask AgriSense send/retry | PARTIALLY WORKING | Backend request/response and error cases tested with mocks; live generation not attempted. |
| Notification mark-read | PARTIALLY WORKING | Handler exists, but mutation affects shared demo data and API is unauthenticated. |
| Profile update | NOT IMPLEMENTED (UI) | Backend route exists; no account settings form. |

### Detailed control-to-handler checklist

| Page / control | Expected action and handler | API or state change | Status / evidence |
|---|---|---|---|
| Landing logo, section links, login/signup links | Navigate to page or section | React route / anchor | PARTIALLY WORKING — targets found; browser not exercised. |
| Landing mobile menu toggle | Open/close navigation | Local menu state | PARTIALLY WORKING — accessible label and expanded state found; no touch test. |
| Landing feature cards and CTA buttons | Open the selected feature | React route | PARTIALLY WORKING — routes exist; browser not exercised. |
| Signup name, email, password, confirmation fields | Validate and create account | `POST /api/auth/signup` | PARTIALLY WORKING — backend policy and account tests pass; browser form not exercised. |
| Signup show/hide password; login show/hide password | Toggle password visibility | Local input type | PARTIALLY WORKING — source inspected. |
| Login email/password and submit | Authenticate and redirect | `POST /api/auth/login` | PARTIALLY WORKING — backend success and invalid-credential tests pass. |
| Logout | Revoke session and clear client token | `POST /api/auth/logout`, session storage | PARTIALLY WORKING — backend revocation test passes. |
| Dashboard navigation/sidebar links | Open selected module | React route | PARTIALLY WORKING — targets found. |
| Dashboard refresh/retry | Reload dashboard data | `GET /api/dashboard` | PARTIALLY WORKING — handler exists; browser click not exercised. |
| Dashboard market / Ask AgriSense / tool cards | Navigate to market, assistant, or feature | React route | PARTIALLY WORKING — target routes exist. |
| Market state selector | Select state and reload available market data | `GET /api/markets/options`, `GET /api/markets/prices` | PARTIALLY WORKING — live options endpoint returned 200; market prices returned stale records. |
| Market commodity selector | Choose commodity and reload price records | `GET /api/markets/prices?commodity=...&state=...` | PARTIALLY WORKING — live endpoint recovered from 429 but returned stale data. |
| Market retry / refresh | Retry provider request | `GET /api/markets/prices` | PARTIALLY WORKING — endpoint exercised; provider has intermittent 429/stale response. |
| Use market price in calculator | Copy chosen price into calculator | Local form state | PARTIALLY WORKING — handler found; browser not exercised. |
| Profit calculator quantity, unit, current price, expected price, production, transport, storage/day, storage duration, other expenses | Update estimate | `POST /api/profit/calculate` | PARTIALLY WORKING — validation, units, losses and storage-duration tests pass; no browser form test. |
| Decision/readiness inputs and submit | Evaluate market decision | `POST /api/decision/analyze` | PARTIALLY WORKING — required-input validation tested; browser form not exercised. |
| Weather retry | Reload forecast | `GET /api/weather` | PARTIALLY WORKING — live Open-Meteo response returned 200. |
| Weather location | Choose location | No complete location-picker control; backend query/default supports coordinates | PARTIALLY WORKING — default Bengaluru was live-checked; UI location selection is limited. |
| Crop image chooser | Select image and validate format/size | Local state; image sent to backend on analyze | PARTIALLY WORKING — backend validates image signature; browser upload/live PlantNet not tested. |
| Crop remove/clear image | Clear selected image/result | Local state | PARTIALLY WORKING — handler inspected. |
| Crop plant-part selector | Select plant organ context | Local state / analysis request field | PARTIALLY WORKING — source and mocked request mapping checked. |
| Crop analyze | Identify plant | `POST /api/crop/analyze` (PlantNet) | PARTIALLY WORKING — mocked tests pass; live request not made without suitable image. |
| Crop disease screen and retry | Run separate limited disease check/retry | `POST /api/crop/disease-screening` | PARTIALLY WORKING — endpoint/error mapping mocked; no live image test; not a diagnosis. |
| Storage search/location input | Filter facilities by location/text | Local filtering of `GET /api/storage` results | PARTIALLY WORKING — helper tests cover case-insensitive matching. |
| Storage type filter | Limit facility category | Local filtering | PARTIALLY WORKING — filter helper tests pass. |
| Storage sort selector | Sort distance, price or rating | Local sorting | PARTIALLY WORKING — sorting tests pass without mutating source. |
| Storage facility selection/details | Show selected facility details | `GET /api/storage/{id}` | PARTIALLY WORKING — endpoint and missing-record/error tests pass; facilities are samples. |
| Storage clear filters | Reset search/filter/sort | Local state | PARTIALLY WORKING — handler found. |
| Storage directions | Open directions link | External URL from sample record | PARTIALLY WORKING — URL encoding tested; actual destination not opened. |
| Calendar title, crop, date, priority and notes fields | Compose task | Local form state | PARTIALLY WORKING — backend validation tests pass. |
| Calendar save/add/edit | Persist task | Authenticated `POST`/`PUT` calendar endpoint | PARTIALLY WORKING — owner scoping and persistence tested. |
| Calendar cancel | Close/reset editor | Local state | PARTIALLY WORKING — handler found. |
| Calendar complete toggle | Change task completion | Authenticated `PUT` calendar endpoint | PARTIALLY WORKING — owner enforcement tested. |
| Calendar delete | Remove owned task | Authenticated `DELETE` calendar endpoint | PARTIALLY WORKING — cross-account denial tested. |
| Calendar retry/refresh | Reload tasks | Authenticated calendar `GET` | PARTIALLY WORKING — auth/ownership tests pass; browser refresh not exercised. |
| News query and submit/Enter | Search agriculture news | `GET /api/news?q=...` | PARTIALLY WORKING — live GNews request returned 200; browser workflow not exercised. |
| News language, country and sort controls | Refine query/results | `GET /api/news` query parameters / local sort | PARTIALLY WORKING — handlers inspected; no browser test. |
| News suggested-query chips | Populate/run suggested query | Local input plus news request | PARTIALLY WORKING — handler found. |
| News retry | Repeat provider request | `GET /api/news` | PARTIALLY WORKING — live request returned 200. |
| Article link | Open original publisher | External URL from provider article | PARTIALLY WORKING — link target behavior inspected; not opened. |
| Assistant text area | Type question | Local draft state | PARTIALLY WORKING — starts empty; keyboard helper test passes. |
| Assistant Enter / Shift+Enter | Enter sends; Shift+Enter inserts newline | Local keyboard handler | WORKING — helper tests cover Enter, newline, IME composition, and other keys. |
| Assistant send | Request agricultural response | `POST /api/assistant` (Gemini) | PARTIALLY WORKING — real backend generation returned HTTP 200; browser rendering not exercised. |
| Assistant retry | Retry failed query | `POST /api/assistant` | PARTIALLY WORKING — mocked retry/error behavior covered; no browser click. |
| Notification retry | Reload notifications | `GET /api/notifications` | PARTIALLY WORKING — endpoint handler found; browser not exercised. |
| Notification mark read | Update read state | Notification update endpoint | PARTIALLY WORKING — handler exists, but state is shared and endpoint lacks user ownership. |
| Profile/account settings controls | Edit profile/password/recovery | No UI controls | NOT IMPLEMENTED — account profile update endpoint is not surfaced in a settings page. |

## E. API audit

Credentials below are described by presence only. Their values are not included in this report.

| Provider / purpose | Integration point | Credential/config status | Live request | Result and error behavior | Limitations |
|---|---|---|---|---|---|
| Open-Meteo — forecast | `GET /api/weather` → `api.open-meteo.com/v1/forecast` | No API key required; backend config includes forecast source | Yes | HTTP 200; response labelled `Open-Meteo`. Offline fallback is explicitly labelled demo and tested. | Only default Bengaluru forecast checked. |
| Mandi price service — Indian mandi data | `GET /api/markets/prices`, options and trend routes; configured `MANDI_API_BASE_URL` | Base URL configured to third-party `mandi-api.onrender.com/v1`; no secret value reported | Yes | Options and price routes returned HTTP 200; prices contained 200 records flagged stale. An earlier price call returned HTTP 429. Unit tests cover success mapping, stale data, errors and unknown units. | This is a third-party proxy, not a direct data.gov.in connection. Current prices are not confirmed fresh; no provider dashboard/quota access was available. |
| GNews — agricultural articles | `GET /api/news` → GNews search | `GNEWS_API_KEY` present in backend configuration | Yes | HTTP 200; backend tests cover missing/invalid key, empty results, timeout, malformed response and quota errors. | No live article content copied into this report. Provider plan/coverage applies. |
| PlantNet — plant species and limited disease screening | `POST /api/crop/analyze`, `POST /api/crop/disease-screening` | `PLANTNET_API_KEY` present | No | Mocked tests verify mappings and safe handling of missing key, bad image, quota and malformed responses. | No live image request; disease screening remains limited and is not a diagnosis. |
| Gemini — Ask AgriSense | `POST /api/assistant`; `GET /api/assistant/status`; direct REST `generateContent` request | `GEMINI_API_KEY` present; configured model `gemini-3.8-flash` | Yes | Real backend generation returned HTTP 200 and a 109-character answer. The source label was Gemini with supplied AgriSense context. Mocked tests cover response parsing, quota, timeout, retries and missing key. | Browser display was not tested. Current code submits only the latest user message, so multi-turn chat context is absent. See [official model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash) and [official generateContent REST documentation](https://ai.google.dev/gemini-api/docs/generate-content). |

## F. Database audit

The existing `backend/agrisense.db` had the base tables `farmer`, `crop`, `market`, `storage`, `weather`, `farming_task`, `notification`, and `news`. The backend `init_db()` startup migration was run against the existing database and retained its tables and rows. It creates `app_user` and `auth_session`, adds nullable `farming_task.user_id`, and leaves pre-existing ownerless calendar tasks in place as `DEMO DATA` examples. No database reset or table drop was performed. The post-migration database had zero auth sessions.

New calendar tasks store the authenticated `user_id`. Calendar reads expose that user's tasks plus ownerless legacy demo examples. Updates/deletes require the task's `user_id` to match the authenticated account. A regression test verifies this across two users and verifies the migration preserves the legacy row. Email is unique case-insensitively. Passwords are stored as salted PBKDF2-HMAC-SHA256 digests with the iteration count recorded per account. Session tokens are stored server-side only as SHA-256 hashes.

Migration risk: legacy tasks have no provable owner, so they cannot safely be attributed to an account; they remain shared/read-only. Other seeded farm profile, crop, market, storage, weather, and notification data remain demonstration/shared data and are not account-owned.

## G. Authentication and security audit

- Signup and login are real backend endpoints, validate email shape, normalize email, reject duplicates, and use generic invalid-credential errors.
- Backend password hashing uses a unique random salt and PBKDF2-HMAC-SHA256 (600,000 iterations). Password hashes/salts are not returned in public account responses.
- Sessions use random opaque bearer tokens, expire after 24 hours, and can be revoked at logout. Authentication attempts are rate-limited per IP/email in process memory.
- The calendar API now requires authentication and enforces per-user ownership for created tasks. The frontend sends its session token and redirects unauthenticated calendar visits to login.
- The token is held in `sessionStorage`; a same-origin script injection could read it. Consider secure, HttpOnly, SameSite cookies or a reviewed BFF/session design before production.
- The rate limiter is process-local and resets on restart; it is not a distributed production control.
- Dashboard and most informational/demo endpoints remain public. They expose shared example farm records, not account-specific private data. Notification read-state is globally shared.
- No password change, account deletion, email verification, forgot-password flow, or profile/settings UI is implemented. Email verification is always unverified in current account responses.
- API credentials remain server-side in backend environment/config; frontend configuration only contains the API base URL. This audit checked key presence without printing values.
- Production HTTPS, security headers/CSP, deployment secrets management and multi-worker rate-limit behavior were not verified.

## H. Automated testing

| Check | Exact command | Result |
|---|---|---|
| Backend unit tests | `.venv\Scripts\python.exe -m unittest discover -s backend -v` | **PASS** — 69 tests, 0 failures/errors. Includes auth, password strength, database migration, calendar owner isolation, provider mapping/error handling and profit/weather behavior. One Starlette deprecation warning notes that `httpx` with `TestClient` is deprecated. |
| Frontend tests | `cd frontend; node --experimental-strip-types --test tests/storageUtils.test.ts tests/assistantKeyboard.test.ts` | **PASS** — 8 tests across storage helpers and chat keyboard behavior. The package has no `npm test` script; tests were run directly with Node's test runner. |
| Frontend lint | `cd frontend; npm run lint` | **PASS (warnings)** — exit code 0; six `react(set-state-in-effect)` warnings in `src/App.tsx`. |
| Production build | `cd frontend; npm run build` | **PASS (warning)** — TypeScript and Vite build succeed. Vite warns the minified JS chunk is about 715 kB, above its 500 kB advisory threshold. |

## I. Browser verification

No browser automation or browser-control tool was available in this session. No browser workflow is claimed as tested. API tests use FastAPI `TestClient`; frontend checks were build/lint and code inspection only.

### Manual browser verification checklist

Run backend and frontend using the commands at the end of this report, then open `http://localhost:5173`. Check each item on desktop and a narrow mobile viewport; record pass/fail and browser console/network errors.

- [ ] Landing logo, anchors, login/signup links, feature cards, and mobile menu open/close.
- [ ] Signup validation: invalid email, weak password, password mismatch, duplicate email, successful signup.
- [ ] Login success and failure; refresh after login; logout; confirm a revoked session cannot access the calendar.
- [ ] Dashboard loads; every module link opens the right route; retry recovers from an induced API failure.
- [ ] Crop Doctor valid-photo upload, invalid-file feedback, remove/reselect, and safe provider errors. Use an approved sample before live PlantNet testing.
- [ ] Weather forecast, explicit unavailable/demo state, and retry action.
- [ ] Market state/commodity selectors, refresh, stale label/date, price-to-calculator action, calculator fields, and decision form.
- [ ] Storage search, type, sort, selection/details, clear filters, and directions link.
- [ ] Calendar login gate; create/edit/cancel/complete/delete; refresh persistence; verify another account cannot view/mutate a task; legacy demo rows stay read-only.
- [ ] News query via submit and Enter, language/country/sort filters, suggestion chips, retry, article links, empty and error states.
- [ ] Assistant starts blank; Enter sends once; Shift+Enter inserts a line; IME composition does not submit; live response/error renders; test a follow-up question.
- [ ] Notifications load/retry/read; document the current shared read state.
- [ ] Unknown dashboard and global URLs; browser back/forward; refresh on nested routes.
- [ ] Keyboard-only navigation, visible focus, screen reader labels, reduced motion, contrast, and desktop/tablet/mobile layout.
- [ ] Inspect browser console/network for unhandled errors, failed requests, exposed secrets, and incorrect source/freshness labels.

## 9. Fixes completed during this audit

1. Replaced the assistant's prefilled example with an empty draft; added Enter-to-send, Shift+Enter newline, and IME-composition protection. Eight frontend tests include four keyboard cases.
2. Scoped calendar create/read/update/delete operations to the authenticated owner. Added nullable task ownership migration; legacy ownerless tasks remain read-only demo rows. Added cross-account and migration tests.
3. Enforced frontend password complexity policy during backend signup and added policy tests.
4. Replaced default Vite favicon and brand mark with matching AgriSense SVG branding.
5. Closed a SQLite connection in an auth test, preventing a Windows file-lock error.

Gemini itself did not reproduce as a failing backend integration: a real request succeeded. Browser UI display remains unverified.

## J. Prioritised issue list

### Critical

- **No critical failure was observed in the checks performed.** This is not a security certification; browser and deployment checks remain outstanding.

### High

1. **Account privacy is only implemented for calendar tasks.** Reproduction: create two accounts; inspect dashboard and informational/demo endpoints, which still use shared seeded farm data. Fix: migrate any future user-specific farmer/crop/preferences/notification records to owner-linked tables, add authorization to those endpoints, and keep public data explicitly public.
2. **Bearer token is readable by page JavaScript.** Reproduction: inspect browser session storage after login. Fix: before deployment, use a reviewed secure session design with HTTPS, HttpOnly/Secure/SameSite cookies (and CSRF controls where applicable), or document/mitigate the XSS threat.
3. **Mandi freshness and provider reliability are uncertain.** A request returned HTTP 429; a later request returned 200 records flagged stale. Verify provider freshness/quota, show stale dates clearly, and do not rely on these records for current price decisions.

### Medium

1. **PlantNet was not tested live.** No suitable plant photo was available. Use an approved sample image for a controlled smoke test before relying on identification or screening.
2. **No profile/settings UI, password change, recovery, email verification or account deletion.** Fix: implement only with complete backend workflows and configured email delivery where needed.
3. **No browser, keyboard-only, mobile viewport or screen-reader verification.** Fix: add browser automation and exercise signup/login/logout, calendar ownership, each retry/error state, responsive menu, and back/refresh navigation.
4. **Rate limiting is in-memory.** Fix: use shared storage or gateway-level rate limiting for multi-worker deployment.
5. **Gemini chat is stateless across turns.** The frontend submits only the latest message, not prior conversation context. Send bounded history or present each question as independent.
6. **Live integration resilience varies.** Open-Meteo, GNews and Gemini each succeeded in a single check; Mandi returned 429 and stale results. Monitor provider status, freshness and limits; preserve explicit unavailable states.

### Low

1. **Frontend JS chunk exceeds Vite's advisory size.** Fix: lazy-load route modules/charts or split vendor chunks.
2. **Six lint warnings remain** for state updates inside React effects. Fix: revise those effects to avoid synchronous state updates where practical.
3. **No dedicated global 404 page.** Fix: add a useful not-found route with a return link.
4. **Localization is incomplete.** Dashboard labels have translations, while landing/auth copy is English. Fix: extend translations if multilingual use is required.

## K. Final readiness assessment

**Ready for:** a limited local demonstration of the landing page, account API, dashboard examples, Open-Meteo forecast, GNews search, live Gemini backend generation, profit calculations, and calendar ownership API. Mandi returned stale records after a rate limit; PlantNet was not live-tested. Browser workflows remain unverified.

**Before deployment:** address token storage and the scope of account-owned data, replace process-local rate limiting, test PlantNet with a suitable image, monitor Mandi freshness/rate limiting, implement intended account settings/recovery requirements, and complete browser/mobile/accessibility checks. The app must not be described as providing private farm profiles beyond its account-scoped calendar tasks.

**Local startup commands** (from the project root):

```powershell
# Backend
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload

# Frontend (in a second terminal)
cd frontend
npm run dev
```

The frontend defaults to `http://127.0.0.1:8000` for the backend. Provider values are configured only on the backend; see `.env.example` for variable names. Do not put backend provider keys in Vite/frontend environment variables.

## Gemini Markdown rendering repair

**Root cause:** `AssistantPage` rendered every message by inserting `message.text` directly as a React text child. React escaped HTML safely, but it also displayed Markdown delimiters as literal characters. Responses containing escaped delimiters such as `\*\*WAIT\*\*` had no normalization or Markdown pass.

**Files changed:**

- `frontend/src/assistantMarkdown.ts` — GFM Markdown renderer, conservative escaped-marker normalization, constrained links, image suppression, and explicit empty/error rendering helpers.
- `frontend/src/App.tsx` — routes assistant messages through the Markdown component and preserves user text, API calls, source labels, loading, and retry/error controls.
- `frontend/src/index.css` — readable heading/list/paragraph/quote/table styling, preserved line breaks, and horizontally scrollable tables for narrow screens.
- `frontend/tests/assistantMarkdown.test.ts` — rendered-output tests for requested Markdown, realistic agricultural context, hostile content, empty replies, and errors.
- `frontend/package.json` and `frontend/package-lock.json` — added `react-markdown` and `remark-gfm`.

**Supported formatting:** headings, paragraphs and line breaks, bold/italic, unordered/ordered lists, horizontal rules, links, and GFM tables. Escaped paired emphasis and escaped list markers are normalized; ordinary backslashes and path-like prose are preserved. Assistant bubbles have distinct heading hierarchy and spacing; tables scroll horizontally on narrow screens.

**Security handling:** Markdown is rendered as React elements; raw HTML is not enabled. URLs are restricted to HTTP(S), mailto, and relative links; dangerous schemes and protocol-relative links are rejected. External links open with `noopener noreferrer`. Model-provided images are suppressed. User messages and API errors stay plain React text and are escaped. Backend endpoint, request payload, Gemini key handling, and AgriSense context were not changed.

**Verification:**

- Frontend tests: **PASS — 18 tests**, including all Markdown/security cases plus existing keyboard and storage helper tests. Command: `node --experimental-strip-types --test tests/storageUtils.test.ts tests/assistantKeyboard.test.ts tests/assistantMarkdown.test.ts`.
- Lint: **PASS — exit code 0**, with six existing `react(set-state-in-effect)` warnings in `App.tsx`.
- Production build: **PASS**. Vite reports the main minified JavaScript chunk is about 873 kB, above its 500 kB advisory threshold.
- Browser/mobile visual verification was not performed; responsive table behavior is implemented in CSS and covered by structure tests, but should still be checked in a real browser.

**Remaining limitations:** conversation history is still not sent to the backend; this fix does not change that behavior. Markdown support intentionally excludes raw HTML and embedded images. Empty assistant text displays a clear placeholder. No backend files changed, so backend tests were not rerun for this frontend-only repair.

## Authenticated farmer identity repair

**Root cause:** signup correctly stored the submitted account name, and login/session restoration already returned the authenticated `app_user`. However, the dashboard greeting used `dashboard.farmer.name` from the shared seeded farmer record (`Ravi Kumar`). The same hero text combined that demo farmer/crop source with the account identity, making the seeded profile appear personalized. The existing profile update endpoint was not exposed in the UI.

**Changes made:**

- `backend/main.py` — public account responses now use the safe fallback `Farmer` when a legacy row has a null/empty name. No database migration or reset was needed.
- `backend/test_main.py` — added two-account login/session/profile isolation and legacy missing-name tests.
- `frontend/src/App.tsx` — dashboard greeting and header display authenticated session identity; dashboard no longer uses the seeded farmer name as a greeting. Added a small profile editor that calls the existing authenticated `/api/auth/profile` endpoint. Page refresh restores the name through `/api/auth/me`, and stale lookup responses are ignored after the session token changes or is cleared.
- `frontend/src/userIdentity.ts` and `frontend/tests/userIdentity.test.ts` — shared trimmed-name/`Farmer` fallback and unit coverage.

**Data ownership:** crop, farm size, crop stage, weather defaults, and other seeded farm records remain shared `DEMO DATA`; they are not linked to authenticated accounts. Dashboard farm/crop labels identify the demo records. This change personalizes only the account name and does not assign demo farm records to a user. Calendar tasks retain their existing separate account ownership behavior.

**Test results:**

- Backend: **PASS — 71 tests**, including two accounts with different names, refresh-equivalent `/api/auth/me` checks, profile update, logout followed by second-account login, account isolation, and a legacy empty-name fallback.
- Frontend: **PASS — 20 tests**, including account-name trimming and missing-name fallback, plus existing storage, keyboard, and Markdown suites.
- Lint: **PASS — exit code 0**, six `react(set-state-in-effect)` warnings remain in existing `App.tsx` effects.
- Production build: **PASS**; Vite warns the minified main chunk is about 874.5 kB, above its 500 kB advisory threshold.
- No browser session or refresh workflow was manually exercised. The identity restore request and account switching were verified in backend tests; browser visual behavior remains unverified.

The existing SQLite database and accounts were preserved.

## Website-wide dashboard design refresh

**Design implemented:** applied the requested black, forest-green, warm-cream and harvest-gold visual system across the existing dashboard and module pages. Added named CSS tokens for the supplied palette and reused them in the theme layer. The desktop app now uses a black fixed sidebar, gold inactive navigation icons, a green active item, cream content header, and responsive dashboard columns with a forest decision card and charcoal alert card. Page cards, forms, tables, charts, statuses, public landing page, auth forms, profile editor, storage, calendar, weather, market, news, Crop Doctor and Gemini chat use the same palette. Existing Lucide icons, AgriSense mark and favicon remain in use. Reduced-motion handling remains active.

The sidebar now has the eight primary destinations in the requested order. Notifications keep their existing route and are reachable from the dashboard alert panel's “View all” link. The recommendation, confidence, market, weather and notification elements remain bound to existing backend response data; no alert or price values were added. Demo farmer/crop and storage records remain labelled demo/sample data. Existing user identity continues to come from the authenticated account, not the seeded farmer record.

**Files changed for this refresh:**

- `frontend/src/index.css` — palette tokens, dark/cream/gold component styling and responsive theme rules.
- `frontend/src/App.tsx` — eight-item primary sidebar, dashboard alert route link, and chart accent variables. Existing routes and data handlers remain wired.
- `WEBSITE_FUNCTIONALITY_AUDIT.md` — this implementation and verification record.

**Verification results:**

- Backend suite: **PASS — 71 tests** (`.venv\Scripts\python.exe -m unittest discover -s backend -v`).
- Frontend suite: **PASS — 20 tests** (`node --experimental-strip-types --test tests/storageUtils.test.ts tests/assistantKeyboard.test.ts tests/assistantMarkdown.test.ts tests/userIdentity.test.ts`).
- Lint: **PASS — exit code 0**; six `react(set-state-in-effect)` warnings remain.
- Production build: **PASS**; Vite reports a 874.41 kB minified JavaScript chunk above its 500 kB advisory threshold.
- Code inspection confirms each of the eight sidebar entries still points to its existing route. API/backend implementation files were not changed for this design pass; automated backend integration tests pass. No live provider smoke tests were run as part of the CSS/component refresh.
- No separate dashboard screenshot was present in the supplied attachment folder; it contained only `Pasted text.txt`. No browser-control tool/browser binary was available, so desktop/tablet/mobile visual comparison and browser interactions were not performed.

**Remaining visual/functional checks:** compare against the actual screenshot once available; inspect desktop, tablet and mobile layouts in a browser; exercise navigation, account flows and each provider-backed page in the running app. External provider availability/freshness limitations documented earlier in this report still apply.

## Additive Farm Tools implementation

**Database and security:** Added the `farm_tool_record` table with a foreign key to `app_user`, a kind index and additive `CREATE TABLE IF NOT EXISTS` migration. Existing tables, accounts, shared records and seeded demo data were not reset or reassigned. Every API read, update and delete filters by the authenticated session's `user_id`; the client cannot choose an owner. Request values are validated server-side. Reports aggregate only account-owned records, include the authenticated account name, and explicitly exclude shared DEMO records. No new API keys or paid services are required.

**Files changed:**

- `backend/main.py` — additive owned-record schema, validation, deterministic profit calculation, CRUD APIs and account-scoped report API.
- `backend/test_main.py` — isolated temporary-database tests for private planner/journal/harvest/profit data, task edit/delete, invalid inputs, calculation units and account-scoped report results.
- `frontend/src/FarmTools.tsx` — responsive dashboard Farm Tools cards and dedicated planner, profit, journal, report, harvest, converter and local knowledge screens.
- `frontend/src/farmToolUtils.ts` and `frontend/tests/farmToolUtils.test.ts` — offline unit conversion and conversion tests.
- `frontend/src/services/api.ts` — typed client methods for the private farmer-record APIs.
- `frontend/src/App.tsx` — dedicated routes protected by existing login guard for private records; converter and bundled knowledge tools remain locally usable.
- `frontend/src/index.css` — scoped Farm Tools layout and print styles; existing sidebar and dashboard content remain in place.
- `WEBSITE_FUNCTIONALITY_AUDIT.md` — this record.

**Feature status:**

1. **Smart Farming Planner — PARTIALLY IMPLEMENTED.** Farmer-owned crop profiles and tasks support create, edit, delete, date/priority/status/crop filtering, due-state counts, chronological list display and a month-grid calendar. Task crops can be selected from the user's saved crop profiles. Bundled starter schedules are not included.
2. **Profit & Loss Simulator — IMPLEMENTED; core calculation tested.** Server arithmetic converts kg/tonnes and kg/quintal, applies estimated loss, sums expenses, calculates gross revenue, net estimate, profit per kg and break-even. Up to three saved user-entered scenarios are supported. Outputs are estimates and no mandi price is treated as verified input. The comparison is a saved result list, not a chart.
3. **Crop Health Journal — IMPLEMENTED for text records.** Records include date, stage, symptoms, observations, notes, action and follow-up, with crop/date filtering and newest inspection first. No images or disease diagnosis are included.
4. **Farm Report Generator — IMPLEMENTED for available private records.** Report includes the authenticated name, account records by category, unavailable/empty states, data-quality notes, print action and CSV export. CSV generation is client-side; browser printing provides the printable report. The CSV export interaction has not been browser-verified.
5. **Harvest & Inventory Tracker — IMPLEMENTED for manual inventory tracking.** Account-owned entries validate sold + stored + spoiled against harvest quantity and compute remaining stock in the selected kg or tonnes unit. Crop/unit summaries and a simple remaining-stock bar are shown. No fake harvest records are seeded.
6. **Agricultural Unit Converter — IMPLEMENTED and utility-tested.** Offline conversion supports kg/tonnes, acres/hectares, square metres to acres/hectares, litres/millilitres and price/kg/quintal. Invalid and unsupported conversions are rejected.
7. **Offline Knowledge Centre — IMPLEMENTED as a small bundled collection.** Search, category filtering and browser-local bookmarks require no API. Content is general educational guidance, not localised or personalised. The initial library is intentionally limited.
8. **Data Freshness & Confidence Indicators — PARTIALLY IMPLEMENTED.** New farmer-entered records carry a `USER ENTERED` provenance badge; existing pages retain their source labels. This change does not add a unified freshness-age classifier for all provider-backed weather, market and cached data, so a generic LIVE/CACHED/STALE confidence state is not claimed.

The eight existing sidebar items were not changed and no new sidebar entries were added. New private records are not demo farm data; existing seeded crop/farm records remain shared DEMO DATA and are excluded from personal reports. No image upload infrastructure was added. Existing calendar and other existing integrations were not replaced.

**Verification results for this change:**

- Backend: **PASS — 74 tests** (`.venv\Scripts\python.exe -m unittest discover -s backend -v`), using temporary SQLite databases for the new account tests. This verifies API ownership, CRUD, input validation, unit conversion in profit calculations and report identity/isolation.
- Frontend tests: **PASS — 24 tests** (`node --experimental-strip-types --test tests/storageUtils.test.ts tests/assistantKeyboard.test.ts tests/assistantMarkdown.test.ts tests/userIdentity.test.ts tests/farmToolUtils.test.ts`). The new tests cover conversion constants, decimal and reverse conversions, invalid inputs, and month-grid boundaries; they do not constitute browser interaction tests for every new page.
- Lint: **PASS — exit code 0**, with six pre-existing `react(set-state-in-effect)` warnings in `App.tsx`.
- Production build: **PASS** (`npm run build`). Vite reports the minified JavaScript bundle is about 899 kB, above its 500 kB advisory threshold.
- Browser verification: **NOT PERFORMED**. No browser automation session was available; direct route refresh and mobile layout are not claimed as manually verified.

**Remaining work:** add bundled planner starter templates, a richer side-by-side scenario comparison, and a provenance-based freshness classifier across provider modules. Test report CSV and route refresh behavior in a browser when browser automation is available.
