# AgriSense AI

AgriSense AI is an agriculture decision cockpit with a deterministic SELL/STORE/WAIT engine. Weather and mandi prices use keyless providers; PlantNet, Gemini and GNews integrations use backend credentials. Storage and news seed records are demo data and are labelled as such by the API. Mandi price data is fetched from the configured provider and is never replaced with demo prices when a request fails.

## Features

- Dashboard with a clear recommendation engine
- Crop Doctor image analysis flow
- Market and profit calculator with sell-vs-store simulation
- Weather and risk tracking
- Storage finder filtered by type and ranking
- Farming calendar with add, edit, complete, and delete flows
- Agri News with search and category filters
- AI decision assistant using the same backend logic
- SQLite-backed demo data and persistent task updates
- Multilingual UI in English, Hindi, Telugu, Kannada, and Tamil
- Demo mode for judge-friendly walkthroughs

## Architecture

- Frontend: React + TypeScript + Vite + Tailwind CSS + Recharts
- Backend: FastAPI + SQLite
- API layers: dashboard, crop analysis, market, profit calculation, weather, storage, calendar, assistant, and notifications
- Decision engine: deterministic scoring logic using crop, market, weather, and profit inputs

## Project structure

- `frontend/` — Vite React application
- `backend/` — FastAPI and SQLite backend service
- `README.md` — setup and demo instructions

## Local setup

1. Install frontend dependencies:
   `cd frontend && npm install`
2. Install backend dependencies:
   `cd backend && pip install -r requirements.txt`
3. Copy `.env.example` to `.env` in the repository root and add the API keys you have. Never put these keys in frontend environment files.
4. Start the backend:
   `cd backend && python main.py`
5. Start the frontend:
   `cd frontend && npm run dev -- --host 0.0.0.0`
6. Open the app at `http://localhost:5173`

## Backend environment variables

Place these in the repository root `.env` file. The backend reads them server-side; no key is included in the Vite bundle.

- `GEMINI_MODEL` (optional) selects the Gemini model; the default is `gemini-3.8-flash`.

- `PLANTNET_API_KEY` — Pl@ntNet plant identification. The API identifies plant species; it does not diagnose disease.
- `GEMINI_API_KEY` — Gemini farmer assistant.
- `GNEWS_API_KEY` — agriculture news search.
- `GOOGLE_MAPS_API_KEY` — reserved for Maps storage search (not yet integrated).
- `MANDI_API_BASE_URL` — keyless Mandi Price API base URL (`https://mandi-api.onrender.com/v1`).

Open-Meteo forecast uses Bengaluru coordinates by default and accepts `latitude` and `longitude` query parameters. Without API keys, optional integrations return clearly labelled demo data or setup/unavailable messages.

## Gemini assistant verification

Keep `GEMINI_API_KEY` in the repository root `.env` file. The backend reads it server-side; do not add it to a `VITE_*` variable or frontend file. Use `.env.example` as a placeholder reference.

Start the backend from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Start the frontend in a second terminal:

```powershell
cd frontend
npm run dev
```

Open `http://localhost:5173`, choose **Ask AgriSense**, and submit a short farming question. The badge says **AI CONFIGURED** when a key is present; it does not claim that a live Gemini request has succeeded. Check configuration without revealing the key at `http://localhost:8000/api/assistant/status` or with:

```powershell
Invoke-RestMethod http://localhost:8000/api/assistant/status
```

Run the backend regression tests from the repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest backend.test_main
```

If the assistant reports an invalid key, check that the root `.env` variable is named `GEMINI_API_KEY` and that the key is active. For HTTP 429, inspect the Google AI quota and wait before retrying. Timeouts and temporary 5xx errors are retried a limited number of times; retry later if they continue. The status endpoint only confirms configuration, not provider connectivity.

## Demo credentials

- Farmer: Ravi Kumar
- Location: Bengaluru
- Crop: Tomato
- Farm size: 2.5 acres
- Quantity: 500 kg

## API endpoints

- `GET /health`
- `GET /api/dashboard`
- `POST /api/crop/analyze`
- `GET /api/crops`
- `GET /api/markets`
- `GET /api/markets/{crop}`
- `POST /api/profit/calculate`
- `POST /api/decision/analyze`
- `GET /api/weather`
- `GET /api/weather/risk`
- `GET /api/storage`
- `GET /api/storage/{id}`
- `GET /api/calendar`
- `POST /api/calendar/tasks`
- `PUT /api/calendar/tasks/{id}`
- `DELETE /api/calendar/tasks/{id}`
- `GET /api/news`
- `POST /api/assistant`
- `GET /api/notifications`
- `PUT /api/notifications/{id}/read`

## Future improvements

- Connect to real weather, market, and storage APIs
- Add user authentication and profiles
- Add image-model integration for crop diagnosis
- Add localization tightening and deeper translation coverage
- Add more robust monitoring, analytics, and export features
