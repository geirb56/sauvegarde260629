# CardioCoach - Product Requirements Document

## Original Problem Statement
CardioCoach is a full-stack AI-powered sports coaching app for endurance athletes (running, cycling). It features dynamic training plans, VMA/VO2MAX estimations, race predictions, readiness scores (Terra API integration), conversational AI coach, subscription paywalls, and multilingual support (EN/FR/ES).

## User Personas
- **Endurance Athletes**: Runners and cyclists looking for personalized training plans
- **Goal-Oriented Users**: Athletes training for specific races (5K, 10K, Semi, Marathon)

## Core Requirements
1. Dashboard with physiological data visualization
2. Training plan generation and tracking
3. VMA/VO2MAX estimation and history
4. Race time predictions based on fitness level
5. AI Coach for conversational guidance
6. Subscription management (with DEMO_MODE for testing)
7. Multilingual support (EN/FR/ES)

## Architecture
```
/app/
├── backend/
│   ├── api/                 # API routers (dashboard.py, mock_runner.py)
│   ├── engine/              # Physiological engines (readiness, training load)
│   ├── services/            # Orchestration layer (adaptation_engine.py)
│   ├── demo_mode.py         # Paywall bypass patch
│   ├── server.py            # Main FastAPI app
│   ├── terra_integration.py # Wearables integration
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # UI Components (Layout, LanguageSelector)
│   │   ├── context/         # React Contexts (Language, Subscription)
│   │   ├── lib/             # Utilities (i18n.js)
│   │   ├── pages/           # Pages (Dashboard, Progress, TrainingPlan, Coach)
│   │   ├── config.js        # Environment config loader
│   │   └── App.js
│   ├── package.json
│   └── tailwind.config.js
```

## Key API Endpoints
- `GET /api/dashboard` - Main dashboard data
- `GET /api/mock-runner` - Dynamic fallback demo data
- `GET /api/mock-runner/vma-history` - VMA history mock data
- `GET /api/mock-runner/race-predictions` - Race predictions mock data
- `GET /api/training/vma-history` - Real VMA history
- `GET /api/training/race-predictions` - Real race predictions

## 3rd Party Integrations
- **Terra API**: Wearable data aggregation (requires user API key)
- **Stripe**: Payments (requires API key, currently bypassed via DEMO_MODE)
- **OpenAI GPT-4o-mini**: AI Coach via LiteLLM (uses Emergent LLM Key)

## Tech Stack
- Frontend: React 19, Tailwind CSS, Shadcn UI, i18n
- Backend: FastAPI, Python, MongoDB
- External: Terra API

---

# Changelog

## 2025-07 — Garmin connector (invisible, gccli-ready)
- **Phase 1**: Invisible Garmin connection in onboarding device step. Provider pattern (`backend/garmin/`), MockProvider default (`GARMIN_PROVIDER=mock`), isolated GccliRunner, ephemeral encrypted vault. Endpoints `/api/garmin/connect|sync|status|activities|disconnect`. NON-NEGOTIABLE: no Garmin password ever collected in UI (OAuth-like). MFA Mode 2 supported (mfa_required -> reconnect). 8/8 backend + frontend E2E tests passed.
- **Phase 2**: Sync now also imports daily health metrics (HRV / resting HR / sleep) into `garmin_daily_metrics` and mirrors activities into the main `workouts` collection (data_source='garmin', id 'garmin-{ext}') so they appear automatically in Dashboard (Recent Workouts) and Progress (All Workouts). New endpoint `GET /api/garmin/daily-metrics`. New "Garmin Health · 7 days" card on Progress (HRV/Resting HR/Sleep). Disconnect cleans garmin metrics + garmin workouts only. 10/10 backend tests passed.

### Real gccli activation (DONE — replaced mock)
The Garmin connector now uses the REAL `gccli` binary (v1.9.0) — the MockProvider and ephemeral vault have been REMOVED.
- Binary installed at `/usr/local/bin/gccli` (linux arm64 from github bpauli/gccli releases).
- Auth: ONE-TIME headless login (email/password via pseudo-TTY) stores an OAuth token under `GCCLI_HOME=/app/backend/.gccli_home` with `GCCLI_KEYRING_BACKEND=file`; gccli auto-refreshes it, so connect is instant and no password is needed afterwards. The first `connect` call auto-logs-in using backend env creds if the token is missing.
- Backend env (server-side only, NEVER in UI): `GARMIN_PROVIDER=gccli`, `GARMIN_USERNAME`, `GARMIN_PASSWORD`, `GCCLI_HOME`, `GCCLI_KEYRING_BACKEND=file`, optional `GCCLI_PATH`.
- Data sources: activities via `gccli activities list -j`; resting HR via `gccli health hr <date>` (the `health rhr` endpoint 404s on this account); sleep via `gccli health sleep <date>`; HRV via `gccli health hrv <date>` (empty for accounts without HRV — stored as null).
- Verified end-to-end: 30 REAL activities + 7 daily metrics (resting_hr 44-49 bpm, sleep 7-9.8h) synced; mirrored into workouts; 8/8 backend tests passed.

### ⚠️ Production deployment requirement for gccli
A fresh production container will NOT have the gccli binary or the token. Before/at deploy you must:
1. Install the `gccli` binary for the TARGET architecture (prod may be amd64, not arm64) and put it on PATH (or set `GCCLI_PATH`).
2. Provide `GARMIN_USERNAME`/`GARMIN_PASSWORD` env (already in backend/.env). The first `connect` will auto-login and persist the token (no MFA on this account). If the account ever enables MFA, an interactive one-time `--mfa-code` login on the server is required.

## 2025-04-12
- **Dashboard layout reordered**: Components now appear in user-requested order: 1) Recommandation du jour (score + RUN HARD/EASY/REST), 2) Métriques du jour (6 widgets), 3) Séance du jour, 4) Séances récentes. Animation delays updated accordingly.

## 2025-04-04
- **Moved "Today's Session" card to Dashboard**: The interactive session card with adaptation, recommendation badge, and feedback buttons is now on the Dashboard instead of Training Plan page.
- **Fixed session adaptation logic**: Now uses `recommendation` (RUN HARD/EASY RUN/REST) instead of `fatigue_ratio` alone. Ensures consistency between displayed recommendation and applied adaptation (e.g., EASY RUN now correctly converts Tempo → Endurance).
- **Refactored training plan generation**: Removed LLM dependency for session generation. Plans are now generated **deterministically** by code with mathematically consistent duration/distance/pace values. LLM removed from this flow = faster, cheaper, always accurate.
- **Fixed /api/training/today endpoint**: Added mock_runner fallback when cardio-coach fails (no Terra data). Interactive training plan now displays correctly with fatigue-based recommendations.

## 2025-04-02
- **Fixed Dashboard translations**: Added 16 new i18n keys for metrics section (todaysMetrics, hrvDeviation, restingHR, etc.) in EN/FR/ES
- **Fixed Coach LLM chat**: Added missing `EMERGENT_LLM_KEY` to backend .env - chat now works with GPT-4.1-mini
- Fixed rate limiting (burst 10→30, requests/min 60→120) for SPA parallel API calls
- VMA and Race Predictions now display correctly in Progress tab using mock fallback data
- Git pull successful - repo already up to date with PR #38

## Previous Session
- Translated entire codebase from French to English
- Removed Strava & Garmin integrations, transitioned to Terra API
- Cleaned up ~5000 lines of dead code
- Added mock_runner.py for dynamic fallback demo data
- Added DEMO_MODE to bypass subscription paywalls
- Added Spanish (ES) translation support
- Fixed "Domain: undefined" API errors via config.js

---

# Roadmap

## P0 (Critical) - Completed
- ✅ VMA/Race Predictions display in Progress tab
- ✅ Demo mode with mock data
- ✅ Multilingual support (EN/FR/ES)
- ✅ Dashboard layout reordering: Recommandation → Métriques → Séance du jour → Séances récentes

## P1 (High Priority) - Backlog
- Real Terra API integration (requires user API key)
- Stripe payment integration (requires API key)
- User authentication system
- Refactoring Dashboard.jsx into smaller components (SessionCard, MetricWidgets, etc.)

## P2 (Nice to Have)
- Custom training plan editor
- Social sharing of achievements
- Export data to CSV/PDF
