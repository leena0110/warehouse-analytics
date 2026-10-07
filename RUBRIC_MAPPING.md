# RUBRIC MAPPING — AI-Based Warehouse Slot Utilization Analyzer
### Academic Evaluation — 20 Marks Total

This document maps every rubric criterion to its specific implementation evidence.

---

## Rubric Coverage Table

| # | Rubric Category | Marks | Implemented Feature | Evidence Location | How to Demonstrate |
|---|----------------|-------|---------------------|------------------|--------------------|
| 1 | Project Objective & Requirements | 2 | Clear problem statement (warehouse capacity management), 10 objectives, functional + non-functional requirements | `README.md` §1–4 | Show README sections 1–4; explain why warehouse slot tracking matters |
| 2 | System Architecture & Design | 4 | 6-layer architecture: Frontend → App Service → Auth → Blob Storage → SQL DB → ML; each Azure service has documented purpose; scalable PaaS deployment | `README.md` §7–8, `app/main.py`, architecture diagram in Monitoring view | Open Monitoring page to show live architecture diagram; trace request flow |
| 3 | Implementation & Functionality | 4 | Working FastAPI backend, 25+ API endpoints, CSV upload+validation, slot classification, grid, forecast, recommendations, reports — all functional end-to-end | `backend/app/`, `frontend/` | Run live demo: login → create warehouse → upload CSV → run analysis → see dashboard |
| 4 | Security & Access Control | 2 | bcrypt password hashing, JWT (HS256) tokens, RBAC with ADMIN/WAREHOUSE_MANAGER, 403 enforcement on every protected route, CORS, .gitignore, .env.example | `app/core/security.py`, `app/api/auth.py`, `.gitignore` | Log in as manager → try to access Upload → get 403; show security.py |
| 5 | Database & Data Management | 2 | 6-table normalized schema with FK constraints + indexes, full CRUD via SQLAlchemy ORM, slot bulk insert, paginated queries, persistent analysis runs | `app/models/`, `app/api/datasets.py` | Show SQLite file after demo; open /api/docs and demonstrate CRUD |
| 6 | Deployment & DevOps | 2 | GitHub Actions CI/CD (test→lint→deploy), Azure App Service deployment configuration, `.env.example`, Procfile, startup.py, Azure CLI commands in README | `.github/workflows/ci-cd.yml`, `backend/Procfile`, `README.md` §16 | Show workflow file; walk through deploy steps; show GitHub Actions run |
| 7 | Monitoring, Performance & Optimization | 1 | Request logging middleware (all requests/responses logged), `/api/monitoring/metrics` endpoint, Azure App Insights hook, 5 documented optimizations (indexes, bulk insert, WAL, pagination, LRU cache) | `app/core/logger.py`, `app/api/monitoring.py`, `README.md` §18 | Open Monitoring view; show warehouse_app.log; explain bulk insert vs loop |
| 8 | Documentation & Presentation | 2 | 22-section README, architecture diagram (ASCII + visual in UI), API table, schema diagram, setup guide, demo flow, limitations, RUBRIC_MAPPING.md | `README.md`, `RUBRIC_MAPPING.md` | Show README; walk through demo procedure in §20 |
| 9 | Innovation & Problem Solving | 1 | Genuine scikit-learn LinearRegression forecast (7-day), rule-based recommendation engine (P1–P4 priority system), operational keyword classifier — all clearly documented | `app/services/ml_service.py`, forecast view, `README.md` §18 | Run analysis → open AI Forecast → show 7-day chart; open ml_service.py |

---

## Detailed Evidence per Criterion

### 1. Project Objective & Requirements (2 marks)

**Implemented:**
- Problem statement: warehouses lack real-time slot visibility → congestion, waste, reactive management
- 10 clear objectives in README
- 10 Functional Requirements (FR-01 to FR-10)
- 8 Non-Functional Requirements (NFR-01 to NFR-08)
- Direct relevance: slot status classification and utilization tracking are the core warehouse KPIs

**Files:**
- [`README.md`](README.md) — sections 1, 2, 3, 4

---

### 2. System Architecture & Design (4 marks)

**Implemented:**
- **Azure App Service** — hosts FastAPI backend; chosen for Python 3.13 support and zero-config autoscaling
- **Azure Blob Storage** — stores uploaded CSV files; chosen over database storage for cost and scalability
- **Azure SQL Database** — relational data (users, slots, analysis runs); chosen for ACID compliance and FK constraints
- **Azure Logic Apps** — event-driven trigger when blob is uploaded; chosen to decouple upload from processing
- **Azure Monitor / App Insights** — production observability; chosen to avoid custom metrics infrastructure
- Clear data flow documented in README §7 and architecture diagram

**Architecture layers:**
```
Browser → App Service → Auth → Business Logic → Blob + SQL → ML → Dashboard
```

**Files:**
- [`backend/app/main.py`](backend/app/main.py) — app structure
- [`backend/app/core/config.py`](backend/app/core/config.py) — Azure service configuration
- [`README.md`](README.md) — §6, 7

---

### 3. Implementation & Functionality (4 marks)

**Implemented features (all working):**

| Feature | Endpoint/File | Status |
|---------|-------------|--------|
| User authentication | `POST /api/auth/token` | ✅ Working |
| Dataset upload + validation | `POST /api/datasets/upload` | ✅ Working |
| Azure Blob Storage | `app/services/storage_service.py` | ✅ (Local fallback in dev) |
| Slot classification | `app/services/csv_service.py` | ✅ Working |
| Utilization calculation | `classify_slots()` | ✅ Working |
| Warehouse grid | `GET /api/analysis/grid/{id}` | ✅ Working |
| ML forecast | `app/services/ml_service.py` | ✅ LinearRegression |
| Recommendations | `generate_recommendations()` | ✅ Working |
| Operational reports | `POST /api/reports/` | ✅ Working |
| Role-based access | All API routes | ✅ Enforced |
| Dashboard charts | `frontend/js/dashboard.js` | ✅ Working |

**Files:**
- `backend/app/api/` — all routes
- `backend/app/services/` — all business logic
- `frontend/` — working SPA

---

### 4. Security & Access Control (2 marks)

**Implemented:**
- **Password hashing:** `passlib.CryptContext` with bcrypt scheme
- **JWT tokens:** `python-jose`, HS256 algorithm, 60-min expiry, secret from env
- **RBAC:** Two roles enforced via FastAPI `Depends()` injection:
  - `require_admin` — upload, delete, run analysis, user management
  - `require_manager_or_admin` — dashboard, grid, forecast, reports
- **Input validation:** Pydantic schemas on all request bodies
- **File validation:** Type, size, CSV structure validated before any storage
- **SQLAlchemy ORM:** Parameterized queries, no raw SQL concatenation
- **CORS:** Explicit origins whitelist in config
- **Secrets:** No credentials in any committed file; `.gitignore` excludes `.env`
- **Audit logging:** Every security event logged with user and details

**Files:**
- [`backend/app/core/security.py`](backend/app/core/security.py)
- [`backend/app/api/auth.py`](backend/app/api/auth.py)
- [`.gitignore`](.gitignore)
- [`.env.example`](.env.example)

**Test:** `tests/test_auth.py` — 12 security tests, all passing

---

### 5. Database & Data Management (2 marks)

**Schema:** 6 normalized tables with foreign keys and indexes:

```
users ←── datasets ←── slots
  |           |
  └── warehouses ←── analysis_runs
         |
         └── operational_reports
```

**CRUD operations:**
- Users: create, read, deactivate
- Warehouses: create, read, update, delete
- Datasets: create, read, delete (with blob cleanup)
- Slots: bulk create, read (paginated, filtered)
- Analysis Runs: create, read, list history
- Reports: create, read, update (resolve), delete

**Optimizations:**
- Composite indexes: `(warehouse_id, zone)`, `(warehouse_id, status)`
- Bulk insert for slots
- FK cascade deletes configured

**Files:**
- [`backend/app/models/`](backend/app/models/) — all ORM models
- [`backend/app/api/datasets.py`](backend/app/api/datasets.py)

---

### 6. Deployment & DevOps (2 marks)

**Implemented:**
- **GitHub Actions** — `.github/workflows/ci-cd.yml`: test → lint → deploy
- **Azure App Service** — `backend/Procfile` and `backend/startup.py`
- **Environment management** — `.env.example`, no secrets in Git
- **Reproducible setup** — documented `pip install -r requirements.txt`
- **Azure CLI commands** — full setup in README §13

**CI/CD Pipeline:**
```yaml
push to main → Test (53 tests) → Bandit Security Scan → Deploy to Azure
```

**Files:**
- [`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml)
- [`backend/Procfile`](backend/Procfile)
- [`README.md`](README.md) — §16

---

### 7. Monitoring, Performance & Optimization (1 mark)

**Monitoring:**
- Structured logging to file + console (`app/core/logger.py`)
- Azure App Insights hook (activates when connection string provided)
- `/api/monitoring/health` — public endpoint for uptime checks
- `/api/monitoring/metrics` — authenticated endpoint for full metrics

**Logged events:** login, logout, upload_start, upload_success, analysis_start, analysis_complete, blob_upload_success, authz_failure, login_failed, password_changed, warehouse_created/deleted, report_created/resolved

**Performance optimizations (5 documented):**
1. Composite DB indexes (warehouse_id + zone/status)
2. Bulk slot insert vs row-by-row
3. SQLite WAL mode for concurrent reads
4. Paginated slot queries (page, page_size params)
5. LRU-cached settings singleton

**Files:**
- [`backend/app/core/logger.py`](backend/app/core/logger.py)
- [`backend/app/api/monitoring.py`](backend/app/api/monitoring.py)
- [`README.md`](README.md) — §18

---

### 8. Documentation & Presentation (2 marks)

**README sections:** 22 sections covering all 30 required items  
**Architecture diagram:** ASCII diagram in README + interactive diagram in Monitoring UI  
**API documentation:** Auto-generated at `/api/docs` (Swagger UI)  
**Dataset format:** Documented with example CSV  
**Demo flow:** Step-by-step 15-step procedure in README §20  
**RUBRIC_MAPPING.md:** This file — maps every mark to evidence

**Files:**
- [`README.md`](README.md) — all 22 sections
- [`RUBRIC_MAPPING.md`](RUBRIC_MAPPING.md) — this file
- `/api/docs` — live Swagger UI

---

### 9. Innovation & Problem Solving (1 mark)

**AI/ML Feature: Genuine LinearRegression Forecast**

The technical challenge: warehouse utilization data has temporal patterns but limited history in early deployment. The solution uses:

- **scikit-learn LinearRegression** when ≥5 historical analysis runs exist
- **Exponential heuristic** as transparent fallback for new warehouses
- Predictions are clipped to [0, 100] with risk level assigned per day
- Method is clearly documented — not claimed as Azure AI

**Innovation beyond CRUD:**
1. 7-day forward utilization forecast with risk classification
2. Priority-ordered recommendation engine (P1 CRITICAL → P4 INFO)
3. Zone-level utilization breakdown surfacing hot zones
4. Keyword-based operational insight classifier from free-text reports
5. Digital twin grid visualization from live DB data

**Files:**
- [`backend/app/services/ml_service.py`](backend/app/services/ml_service.py)
- Forecast view in frontend

---

## Final Audit Checklist

| Item | Status |
|------|--------|
| ✅ Objective & requirements | Documented |
| ✅ Architecture | Documented + visual |
| ✅ Scalability | Azure App Service + SQL |
| ✅ Reliability | Error handling, graceful fallbacks |
| ✅ Working functionality | 53 tests pass, live demo works |
| ✅ Authentication | JWT + bcrypt |
| ✅ Authorization | RBAC on all routes |
| ✅ Access control | Admin vs Manager enforced |
| ✅ Data protection | Hashed passwords, parameterized queries |
| ✅ Database | 6-table normalized schema |
| ✅ CRUD | All entities |
| ✅ Blob storage | Azure Blob + local fallback |
| ✅ Cloud deployment | Azure App Service (README §13) |
| ✅ CI/CD | GitHub Actions workflow |
| ✅ Configuration management | .env, .env.example |
| ✅ Monitoring | Logger + /api/monitoring/metrics |
| ✅ Logging | Structured audit events |
| ✅ Performance | 5 documented optimizations |
| ✅ Optimization | Indexes, bulk insert, WAL, pagination |
| ✅ Architecture diagram | ASCII + UI |
| ✅ Documentation | 22-section README |
| ✅ Screenshots | Live demo (see §20) |
| ✅ Demonstration workflow | README §20 |
| ✅ Innovation | ML forecast + recommendations |
| ✅ Rubric mapping | This file |
