# Infra hardening — Secret Management + Queue-Health Alerting — Rapport

Date : 2026-07-05
Objectif : renforcer l'infrastructure sans modifier la logique métier, les
endpoints existants (hors ajout strict) ni le comportement fonctionnel.

---

## P0 — Secret Management (GARMIN_PASSWORD)

### 1. Couche centralisée — `config/secrets.py`
- `get_secret(name, default=None, required=False)` : lecture **environnement
  uniquement** (chaîne vide = absente). `required=True` → `MissingSecretError`
  avec message clair et provider-agnostique.
- Secret-manager ready : Doppler / Vault / 1Password / Docker secrets injectent
  dans l'environnement au runtime → **aucun code spécifique provider** dans l'app.

### 2. Fail-fast **contextuel** (zéro régression)
Dans `garmin/bootstrap.py::ensure_logged_in()` :
- `GARMIN_PROVIDER != gccli` (ex. mock/absent) → aucun credential requis.
- gccli + **session OAuth valide déjà persistée** → démarrage OK sans
  `GARMIN_PASSWORD`.
- gccli **runner indisponible / check auth en échec** → skip best-effort (pas de crash).
- gccli devant réaliser une **vraie authentification** → `GARMIN_USERNAME` **et**
  `GARMIN_PASSWORD` deviennent obligatoires → `MissingSecretError` immédiate
  (message précisant le secret manquant). Propagée hors du `try/except` de
  startup dans `server.py` (les autres erreurs bootstrap restent best-effort).

Le backend ne crashe **jamais uniquement** parce que `GARMIN_PASSWORD` est absent
si une session existe. Vérifié en live : startup OK (`existing session found`).

### 3. Standardisation des accès
- `os.getenv/os.environ.get("GARMIN_PASSWORD")` → `get_secret(...)` dans
  `garmin/providers/gccli_provider.py` (username + password) et
  `garmin/bootstrap.py`. Aucune autre logique modifiée.

### 4. Sécurité repo
- `backend/.env.example` créé : **noms de variables uniquement, valeurs vides**.
- Aucun secret réel en clair. Toutes les credentials injectées au runtime.

---

## P1 — Alerting Queue Health — `monitoring/alerts.py`

### 1. `evaluate_queue_health(payload, state=None)` — **fonction pure**
- Entrée : snapshot `queue_health` (+ état de streak précédent). Sortie :
  `AlertEvaluation(state, level, message, fields)`. Aucun I/O, aucun global,
  **aucune boucle** — câblage worker/scheduler/service laissé au futur.
- Règles :
  - `unhealthy` **2×** consécutifs → `critical`.
  - `degraded` **5×** consécutifs → `warning`.
  - tout `healthy` **réinitialise** les deux compteurs (idem changement de statut).
  - statut inconnu/absent → no-op.

### 2. `send_alert(level, message, payload)` — notification provider-agnostique
- **Toujours** un log structuré.
- Si `ALERT_WEBHOOK_URL` défini → POST asynchrone (httpx) ; sinon skip silencieux.
- **Best-effort** : au plus **1 retry**, échec loggué puis avalé — n'impacte
  jamais l'app ni le worker. Aucun code Slack/Discord/Teams spécifique.
- Email : **non implémenté** (comme demandé).

Aucune intégration runtime (pas de polling, pas d'endpoint) à ce stade.

---

## Fichiers

| Fichier | Nature |
|---|---|
| `backend/config/__init__.py`, `config/secrets.py` | **nouveau** |
| `backend/monitoring/__init__.py`, `monitoring/alerts.py` | **nouveau** |
| `backend/.env.example` | **nouveau** (noms only) |
| `backend/garmin/bootstrap.py` | get_secret + fail-fast contextuel |
| `backend/garmin/providers/gccli_provider.py` | get_secret |
| `backend/server.py` | ne pas avaler `MissingSecretError` au startup |
| `backend/tests/test_secrets.py`, `tests/test_alerts.py` | **nouveau** |

---

## Impact & compatibilité
- **Performances** : nul. `get_secret` = lecture dict env. `evaluate_queue_health`
  = pure/O(1). `send_alert` = 1 log (+ POST optionnel best-effort).
- **Comportement fonctionnel** : inchangé. Queue/workers/endpoints existants
  intacts. Endpoint `/api/garmin/queue/health` toujours `healthy` en live.
- **Zéro régression** : startup live OK (session persistée), reliable-queue &
  queue-health tests toujours verts.

## Tests — résultats
- `python -m tests.test_secrets` → **ALL PASSED ✅** (présent, optionnel manquant,
  chaîne vide = absente, required manquant → erreur claire).
- `python -m tests.test_alerts` → **ALL PASSED ✅** (unhealthy 2×→critical,
  degraded 5×→warning, healthy reset, changement de statut casse le streak,
  statut inconnu no-op, send_alert sans webhook = no-op, échec webhook retry×1
  puis avalé).
- Fail-fast contextuel vérifié : gccli non-auth + secret absent → `MissingSecretError`
  (nomme `GARMIN_PASSWORD`) ; mock → pas de crédential requis ; gccli authentifié
  → pas de crash sans password.
