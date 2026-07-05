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

### Dashboard block now powered by REAL Garmin data (DONE)
`GET /api/cardio-coach` (the Dashboard "Run Readiness" + metrics block) no longer returns `_CARDIO_COACH_MOCK_DATA` when Garmin is connected. New `backend/garmin/insights.py::compute_cardio_coach`:
- **Resting HR + Sleep**: real values from `garmin_daily_metrics` (gccli `health hr` / `health sleep`).
- **Training load / ACWR**: computed from real `garmin_activities` (ACWR = 7-day vs 28-day daily-load average, load proxy = session minutes).
- **Fatigue ratio / readiness / recommendation**: computed with the existing formula; `fatigue_ratio` clamped >= 0.
- **HRV**: if the device reports real HRV it is USED (full 0.5/0.3/0.2 formula, most-recent non-null reading); if absent (this account), the model gracefully reweights to RHR+sleep+load, HRV fields are null (UI shows "—"), reason "HRV not recorded by your Garmin device". Verified both paths.
- Mock kept only as a last-resort fallback (Garmin not connected). VMA history & race predictions already compute from real activities (has_data:true). Tested: 16/16 + regression passed; Dashboard renders real data.

### Frontend mock fallbacks REMOVED + mock_runner endpoints deleted (DONE)
- Removed `Dashboard.jsx` fallback to `/api/mock-runner` (on cardio-coach error → now shows a clean error state, no fake demo).
- Removed `Progress.jsx` fallbacks to `/api/mock-runner/vma-history` and `/api/mock-runner/race-predictions` (real `/training/*` endpoints return has_data:true from real activities).
- Deleted `backend/api/mock_runner.py` and its router registration; `/api/mock-runner*` now returns 404.
- `/api/training/today` no longer depends on mock_runner — uses neutral defaults if cardio-coach is unavailable.
- Verified: `/api/mock-runner` → 404, cardio-coach still real (source:garmin), `/training/today` → success, Dashboard + Progress render real data (VO2max 54.7, race predictions, Garmin Health). Kept (separate, out of scope): `_CARDIO_COACH_MOCK_DATA` (cardio-coach fallback when Garmin not connected), `get_mock_workouts` (workouts fallback), `DEMO_MODE` (Stripe bypass).

### get_mock_workouts() fully removed (DONE)
Deleted the `get_mock_workouts()` function and removed its fallback from all 8 endpoints (GET /api/workouts, GET /api/workouts/{id}, dashboard insight, /coach/guidance, /coach/digest, /coach/workout-analysis/{id}, /coach/detailed-analysis/{id}, /coach chat). The analysis endpoints query the global workouts collection (now filled with real Garmin activities) and the local engines handle empty lists. Verified (14/14 backend tests): no 500s, empty-user → [] , bogus workout id → 404, all coach/dashboard endpoints 200 with real Garmin data, cardio-coach still source=garmin. Remaining mocks: `_CARDIO_COACH_MOCK_DATA` (cardio-coach fallback only when Garmin not connected) and `DEMO_MODE` (Stripe subscription bypass).

### No-data state when Garmin not connected (DONE — replaced last mock)
`_CARDIO_COACH_MOCK_DATA` deleted. When no wearable is connected, `GET /api/cardio-coach` now returns an explicit no-data payload `{mock:false, no_data:true, connected:false, metrics:null, message:"Connect your Garmin…"}` instead of fabricated data. The Dashboard renders a "No data yet / Connect Garmin" panel (links to /onboarding) instead of fake metrics. Added i18n keys (en/fr/es): dashboard.noData, connectGarmin, connectGarminPrompt. Verified by frontend testing agent: PART 1 disconnected → no-data panel with NO mock metrics; PART 2 connect via onboarding → real data (RHR 44, ACWR 1.57) appears. Only remaining mock: DEMO_MODE (Stripe subscription bypass).

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
- ✅ [2026-06-30] Fixed Training Plan mileage mismatch: unified weekly-volume logic into a single source of truth `compute_target_km` / `compute_long_run_km` in training_engine.py, used by /training/full-cycle (server.py), generate_cycle_week (llm_coach.py, now VOLUME-DRIVEN sessions) and _deterministic_plan (coach_service.py). Cycle cards now match the sum of detailed sessions exactly.
- ✅ [2026-06-30] Aligned ACWR & TSB across Dashboard and Training (single source of truth `compute_load_metrics` in garmin/insights.py, duration-based on garmin_activities). Both show ACWR 1.57.
- ✅ [2026-06-30] Made "Today's Metrics" coherent: removed duplicate "Current Form" widget (contradicted Run Readiness); week stats now use a rolling 7-day window (matches /training/metrics THIS WEEK = 31.7 km); /dashboard/insight is now user-scoped. Fixed latent "ok"/"moderate" status label mismatch (widget removed).
- ✅ [2026-07-01] Scaling upgrade (200-1000 users) WITHOUT architecture rewrite: added Redis job queue (`jobs/queue.py`, `jobs/redis_client.py`), out-of-process worker (`workers/sync_worker.py`, supervisor `sync-worker`), non-blocking `/api/garmin/sync` (returns `{"status":"queued"}`, local latency ~2ms) and `/connect` (fast auth + enqueue initial sync). Service layer sync() now worker-only. Hardened GccliRunner (timeout clamp 15-60s, 3 retries + backoff, isolated subprocess). Throttling: max concurrency 5 (semaphore), per-user Redis lock `sync_lock:{uid}`, enqueue dedupe `sync_pending:{uid}`. Structured logs (start/success/retry/failure/duration, no creds). Optional periodic scheduler (SYNC_SCHEDULE_INTERVAL, disabled by default, staggered). Provider pattern / gccli / frontend / Terra untouched. Verified E2E: enqueue→worker→30 activities+5 metrics in ~4.9s, queue drains, dedupe returns already_queued.
- ✅ [2026-07-01] Reliable Queue (at-least-once delivery): replaced destructive BRPOP with BLMOVE + `processing` list + `claims` hash + ACK-on-success + watchdog (`recover_orphans`, ORPHAN_TIMEOUT=120s). No Celery, native Redis only. Enabled Redis AOF persistence in `/app/data/redis` + persisted binary at `/app/bin/redis-server` (fixes apt-package volatility on container restart). Fixed `redis_client` socket_timeout=None (BLMOVE was raising client TimeoutError). Tests `tests/test_reliable_queue.py` (+`_mock_worker.py`) PASS: mock kill -9 recovery, ACK-once, Redis-restart durability; REAL gccli proof: killed worker mid-sync, watchdog recovered exact job, re-ran, Mongo activity count unchanged (idempotent, no loss/no dup). Report: `memory/RELIABLE_QUEUE_report.md`.
- ✅ [2026-07-02] Monitoring endpoint `GET /api/garmin/queue/health` (READ-ONLY Redis, latency avg 0.16ms/max 0.18ms). Additive instrumentation only (no business/queue logic change): worker heartbeat key `cardiocoach:worker:heartbeat:{pid}` (TTL 15s, refresh 10s) → active_workers; INCR counters `cardiocoach:stats:orphans_recovered` (watchdog) & `cardiocoach:stats:failed_jobs` (terminal failure). Returns status healthy/degraded/unhealthy (thresholds: workers==0/oldest>=120s/queue>=2000 → unhealthy; queue>=500/oldest>=96s → degraded). New `jobs/health.py`. Tests `tests/test_queue_health.py` (6 cases: redis ok/down, empty/loaded queue, worker absent, orphan counter, latency) ALL PASS; reliable-queue tests still pass (no regression). Infra: persisted redis libs to `/app/lib` + `LD_LIBRARY_PATH` (liblzf/libjemalloc vanished on container restart). Report: `memory/QUEUE_HEALTH_report.md`.
- ✅ [2026-07-05] Infra hardening (no business-logic change). P0 Secret Management: new `config/secrets.py` `get_secret(name, default, required)` (env-only, secret-manager ready: Doppler/Vault/1Password/Docker). Contextual fail-fast in `garmin/bootstrap.py::ensure_logged_in` — startup never crashes solely for a missing GARMIN_PASSWORD when an OAuth session exists (mock=no creds; gccli+session=ok; gccli needing real auth → GARMIN_USERNAME+PASSWORD mandatory → MissingSecretError propagated past server.py startup try/except). Standardized GARMIN_PASSWORD/USERNAME access via get_secret in gccli_provider.py + bootstrap.py. Added `.env.example` (variable NAMES only, no real secrets). P1 Alerting: new `monitoring/alerts.py` — `evaluate_queue_health(payload, state)` PURE function (unhealthy 2x→critical, degraded 5x→warning, healthy resets; no runtime loop) + `send_alert(level,message,payload)` always logs, POSTs to `ALERT_WEBHOOK_URL` if set (async, 1 retry, best-effort, provider-agnostic; no email). Tests `tests/test_secrets.py` & `tests/test_alerts.py` ALL PASS; live startup OK (existing session). Report: `memory/INFRA_SECRETS_ALERTING_report.md`.
- ✅ [2026-07-05] Dedicated monitor process `workers/monitor_worker.py` (supervisor `monitor-worker`, separate from sync_worker & FastAPI, decoupled from gccli/sync, Redis-read only). Loop: queue_health → evaluate_queue_health → send_alert. Adaptive interval 30s(unhealthy)/60s(degraded)/120s(healthy). Alerts on STATE CHANGE only (last level in `cardiocoach:alert:last_level`, + `info` recovery on return to healthy) → no spam. Horizontally scalable via Redis leader lock `cardiocoach:alert:leader` (TTL 150s); extra monitors are hot standbys; streaks in `cardiocoach:alert:state` shared. Tests `tests/test_monitor_worker.py` ALL PASS (adaptive interval, single-emit + suppression, recovery, warning→critical escalation, leader election). Live: monitor running, ticked healthy next=120s.

## P1 (High Priority) - Backlog
- Real Terra API integration (requires user API key)
- Stripe payment integration (requires API key)
- User authentication system
- Refactoring Dashboard.jsx into smaller components (SessionCard, MetricWidgets, etc.)

## P2 (Nice to Have)
- Custom training plan editor
- Social sharing of achievements
- Export data to CSV/PDF
