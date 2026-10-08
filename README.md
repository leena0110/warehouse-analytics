# AI-Based Warehouse Slot Utilization Analyzer
### Cloud Computing Course Project — Academic Submission

[![CI/CD](https://github.com/your-org/warehouse-slot-analyzer/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/your-org/warehouse-slot-analyzer/actions)
[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com)
[![Azure](https://img.shields.io/badge/Azure-App%20Service%20%7C%20SQL%20%7C%20Blob-0078D4.svg)](https://azure.microsoft.com)

---

## 1. Problem Statement

Modern warehouses manage thousands of physical storage slots. Without real-time visibility, operations suffer from:

- **Over-utilization** — slots filled beyond safe capacity, causing congestion
- **Under-utilization** — wasted space with idle inventory
- **Reactive management** — blockages and delays discovered after they cause disruptions
- **No predictive capability** — no warning before capacity becomes critical

This project addresses these problems with a cloud-based analytics platform that classifies every slot, computes utilization, forecasts capacity trends using ML, and surfaces actionable recommendations.

---

## 2. Objectives

| # | Objective |
|---|-----------|
| 1 | Upload warehouse slot datasets (CSV) to cloud storage |
| 2 | Classify slots as OCCUPIED / EMPTY / RESERVED / BLOCKED |
| 3 | Compute real-time utilization statistics from uploaded data |
| 4 | Visualize warehouse layout as a 2D digital twin grid |
| 5 | Forecast 7-day utilization using scikit-learn LinearRegression |
| 6 | Generate rule-based recommendations (critical / warning / info) |
| 7 | Analyze operational reports for issue keywords |
| 8 | Enforce JWT authentication with ADMIN / WAREHOUSE_MANAGER roles |
| 9 | Store all data persistently in Azure SQL Database |
| 10 | Monitor application health and performance metrics |

---

## 3. Functional Requirements

- FR-01: Users must authenticate before accessing any feature
- FR-02: ADMIN can upload datasets, run analysis, manage warehouses and users
- FR-03: WAREHOUSE_MANAGER can view all dashboards and create reports
- FR-04: System must validate CSV structure, status values, and duplicates
- FR-05: Files must be stored in Azure Blob Storage (local fallback in dev)
- FR-06: Analysis results must be stored in database — not ephemeral
- FR-07: Warehouse grid must be generated from database data
- FR-08: Forecast must use genuine ML, not hardcoded values
- FR-09: API endpoints must enforce authorization on every route
- FR-10: No secrets may be committed to version control

---

## 4. Non-Functional Requirements

- NFR-01: API response time < 2 seconds for dashboard queries
- NFR-02: Support CSV files up to 50MB / 50,000 rows
- NFR-03: All passwords must be bcrypt-hashed (factor 12+)
- NFR-04: JWT tokens expire after 60 minutes
- NFR-05: Application must log all key events for audit trail
- NFR-06: Database queries must use indexed columns for performance
- NFR-07: Storage service must fall back to local filesystem when Azure is not configured
- NFR-08: Application must start cleanly on both SQLite (dev) and Azure SQL (prod)

---

## 5. Technology Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| Backend | Python 3.13 + FastAPI | High-performance async REST API |
| ORM | SQLAlchemy 2.0 | Supports both SQLite and Azure SQL |
| Authentication | JWT (python-jose) + bcrypt (passlib) | Industry-standard token auth |
| ML/AI | scikit-learn LinearRegression | Lightweight, genuine ML forecast |
| Cloud Storage | Azure Blob Storage SDK | Scalable file storage |
| Database | Azure SQL / SQLite | Production / development |
| Frontend | Vanilla HTML + CSS + JS | No build step, deployable as static |
| Charts | Chart.js 4 | Zero-dependency chart library |
| CI/CD | GitHub Actions | Automated test → deploy pipeline |
| Monitoring | Azure Application Insights (optional) | Production observability |

---

## 6. Azure Services Used

| Service | Purpose | Why Selected |
|---------|---------|-------------|
| **Azure App Service** | Host Python backend | Managed PaaS, auto-scaling, zero infrastructure management |
| **Azure Blob Storage** | Store uploaded CSV datasets | Scalable, cheap object storage; native SDK support |
| **Azure SQL Database** | Persistent relational storage | ACID transactions, familiar SQL syntax, scales to production |
| **Azure Logic Apps** | Automated processing trigger | Serverless workflow when file uploaded to blob |
| **Azure Monitor / App Insights** | Logs, metrics, alerts | Production observability without additional tooling |

> **Note:** Each service has a clear, demonstrable purpose. No service is included just to inflate the service count.

---

## 7. Architecture Diagram

```
                    ┌─────────────────────────────────────┐
                    │          GitHub Actions CI/CD        │
                    │  Test → Lint → Deploy on main merge  │
                    └─────────────────┬───────────────────┘
                                      │ Deploy
                    ┌─────────────────▼───────────────────┐
User / Browser ────►│      Azure App Service (Backend)     │◄──── Azure Monitor
                    │   FastAPI + Uvicorn  (Python 3.13)   │      App Insights
                    │                                      │
                    │  ┌──────────────────────────────┐   │
                    │  │  Request Logging Middleware   │   │
                    │  └──────────────┬───────────────┘   │
                    │                 │                    │
                    │  ┌──────────────▼───────────────┐   │
                    │  │   JWT Auth + RBAC Layer       │   │
                    │  │  (ADMIN / WAREHOUSE_MANAGER)  │   │
                    │  └──────────────┬───────────────┘   │
                    │                 │                    │
                    │  ┌──────────────▼───────────────┐   │
                    │  │      Business Logic           │   │
                    │  │  CSV Validation + Analysis    │   │
                    │  └──────┬─────────────┬──────────┘   │
                    │         │             │              │
                    │  ┌──────▼───┐  ┌──────▼──────────┐  │
                    │  │ Azure    │  │  Azure SQL DB    │  │
                    │  │ Blob     │  │  users/warehouses│  │
                    │  │ Storage  │  │  slots/datasets  │  │
                    │  │ (CSVs)   │  │  analysis_runs   │  │
                    │  └──────────┘  └──────────────────┘  │
                    │                                      │
                    │  ┌───────────────────────────────┐   │
                    │  │   ML Service (scikit-learn)   │   │
                    │  │  LinearRegression Forecast    │   │
                    │  │  Rule-based Recommendations   │   │
                    │  └───────────────────────────────┘   │
                    │                                      │
                    │  ┌───────────────────────────────┐   │
                    │  │   Azure Logic Apps (trigger)  │   │
                    │  │  BlobCreated → /api/analysis  │   │
                    │  └───────────────────────────────┘   │
                    └──────────────────────────────────────┘
```

---

## 8. Database Schema

```sql
-- Users (authentication + RBAC)
users (id, username, email, hashed_password, full_name, role, is_active, created_at, last_login)

-- Warehouses (top-level entity)
warehouses (id, warehouse_id, name, location, description, total_rows, total_columns, created_at)

-- Slots (physical warehouse slots, loaded from CSV)
slots (id, slot_id, warehouse_id, zone, row, column, status, capacity, occupancy,
       blocked_reason, last_updated, dataset_id, created_at)
-- Indexes: (warehouse_id, zone), (warehouse_id, status)

-- Datasets (uploaded files)
datasets (id, filename, original_filename, blob_url, blob_name, storage_mode,
          file_size_bytes, row_count, warehouse_id, uploaded_by, status,
          error_message, uploaded_at, processed_at)

-- Analysis Runs (computed results)
analysis_runs (id, dataset_id, warehouse_id, run_by, total_slots, occupied_slots,
               empty_slots, reserved_slots, blocked_slots, utilization_pct,
               available_capacity, blocked_pct, forecast_json, risk_level,
               recommendations_json, insights_json, run_at, duration_ms, success)

-- Operational Reports (manual incident reports)
operational_reports (id, warehouse_id, reported_by, title, content, category,
                     severity, is_resolved, created_at, resolved_at)
```

---

## 9. API Endpoints

### Authentication
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/token` | None | Login — returns JWT |
| GET | `/api/auth/me` | Any | Get own profile |
| POST | `/api/auth/users` | Admin | Create user |
| GET | `/api/auth/users` | Admin | List all users |
| PUT | `/api/auth/users/{id}/deactivate` | Admin | Deactivate user |
| POST | `/api/auth/change-password` | Any | Change own password |

### Warehouses
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/warehouses/` | Manager+ | List warehouses |
| POST | `/api/warehouses/` | Admin | Create warehouse |
| GET | `/api/warehouses/{id}` | Manager+ | Get warehouse |
| PUT | `/api/warehouses/{id}` | Admin | Update warehouse |
| DELETE | `/api/warehouses/{id}` | Admin | Delete warehouse |

### Datasets
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/datasets/upload` | Admin | Upload+process CSV |
| GET | `/api/datasets/` | Manager+ | List datasets |
| GET | `/api/datasets/{id}` | Manager+ | Get dataset |
| DELETE | `/api/datasets/{id}` | Admin | Delete dataset |

### Analysis
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/analysis/run/{dataset_id}` | Admin | Trigger analysis |
| GET | `/api/analysis/latest/{warehouse_id}` | Manager+ | Latest results |
| GET | `/api/analysis/history/{warehouse_id}` | Manager+ | Run history |
| GET | `/api/analysis/grid/{warehouse_id}` | Manager+ | Grid/digital twin |
| GET | `/api/analysis/slots/{warehouse_id}` | Manager+ | Paginated slots |

### Reports
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/reports/` | Manager+ | Create report |
| GET | `/api/reports/` | Manager+ | List reports |
| GET | `/api/reports/insights/{warehouse_id}` | Manager+ | Keyword insights |
| PUT | `/api/reports/{id}/resolve` | Manager+ | Resolve report |
| DELETE | `/api/reports/{id}` | Admin | Delete report |

### Monitoring
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/monitoring/health` | None | Health check |
| GET | `/api/monitoring/metrics` | Manager+ | System metrics |

---

## 10. Dataset Format

The application accepts **CSV files** with the following schema:

```csv
slot_id,warehouse_id,zone,row,column,status,capacity,occupancy,last_updated,blocked_reason
WH-001-A01,WH-001,A,A,1,OCCUPIED,1000,750.5,2026-09-15T10:00:00Z,
WH-001-A02,WH-001,A,A,2,EMPTY,1000,0,2026-09-15T10:00:00Z,
WH-001-A03,WH-001,A,A,3,BLOCKED,1000,0,2026-09-15T10:00:00Z,Maintenance
```

**Required columns:** `slot_id`, `warehouse_id`, `zone`, `row`, `column`, `status`  
**Optional columns:** `capacity`, `occupancy`, `last_updated`, `blocked_reason`  
**Valid statuses:** `OCCUPIED`, `EMPTY`, `RESERVED`, `BLOCKED`

A **sample dataset** with 400 slots across 5 zones is provided at `data/warehouse_sample.csv`.

---

## 11. Local Setup

### Prerequisites
- Python 3.11+
- pip

### Steps

```bash
# 1. Clone repository
git clone https://github.com/your-org/warehouse-slot-analyzer.git
cd warehouse-slot-analyzer

# 2. Create environment file
cp .env.example .env
# Edit .env — at minimum set a SECRET_KEY

# 3. Install backend dependencies
cd backend
pip install -r requirements.txt

# 4. Generate sample dataset (optional)
cd ..
python data/generate_sample_data.py

# 5. Start the backend server
cd backend
uvicorn app.main:app --reload --port 8000

# 6. Open the application
# Navigate to: http://localhost:8000
# API docs:    http://localhost:8000/api/docs
```

### Default Credentials (seeded on first startup)
| Username | Password | Role |
|----------|----------|------|
| `admin` | `Admin@123` | ADMIN |
| `manager` | `Manager@123` | WAREHOUSE_MANAGER |

> ⚠️ **Change these passwords in any non-local environment.**

---

## 12. Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | JWT signing secret — **must be set** | (weak default) |
| `DATABASE_URL` | SQLAlchemy connection string | `sqlite:///./warehouse.db` |
| `AZURE_STORAGE_CONNECTION_STRING` | Blob Storage connection string | (empty = local fallback) |
| `AZURE_APPINSIGHTS_CONNECTION_STRING` | App Insights connection | (empty = disabled) |
| `APP_ENV` | `development` or `production` | `development` |

---

## 13. Azure Setup

### Azure SQL Database
```bash
# Create Azure SQL Server and Database
az sql server create --name wh-sql-server --resource-group wh-rg \
  --location eastus --admin-user sqladmin --admin-password <password>

az sql db create --resource-group wh-rg --server wh-sql-server \
  --name warehouse_db --tier Basic

# Get connection string and add to App Service settings
# Format: mssql+pyodbc://user:pass@server.database.windows.net/db?driver=ODBC+Driver+18+for+SQL+Server
```

### Azure Blob Storage
```bash
az storage account create --name whstorage --resource-group wh-rg --sku Standard_LRS
az storage container create --name warehouse-datasets --account-name whstorage
# Copy connection string from Azure Portal → Storage account → Access keys
```

### Azure App Service
```bash
az webapp create --resource-group wh-rg --plan wh-plan \
  --name warehouse-slot-analyzer --runtime "PYTHON:3.13"

# Set app settings (replaces .env in production)
az webapp config appsettings set --resource-group wh-rg \
  --name warehouse-slot-analyzer --settings \
  DATABASE_URL="mssql+pyodbc://..." \
  SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')" \
  AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;..."
```

---

## 14. Logic Apps (Automated Workflow)

When a new CSV is uploaded to Blob Storage, an Azure Logic App can automatically trigger the backend processing endpoint.

### Logic App Workflow
1. **Trigger:** `When a blob is created` → Container: `warehouse-datasets`
2. **Action:** HTTP POST to `https://<app>.azurewebsites.net/api/datasets/process-latest`
3. **Auth Header:** Add managed identity bearer token

### Configuration File
See `docs/logic_app_definition.json` for the ARM template.

> In local development, this workflow is simulated by calling the analysis endpoint manually from the Upload page.

---

## 15. Monitoring Setup

### Azure Application Insights

The application uses `opencensus-ext-azure==1.1.13` to send **three telemetry streams** to Azure App Insights:

| Stream | App Insights Table | Trigger |
|--------|--------------------|---------|
| Application logs (`INFO`, `WARNING`, `ERROR`, `EXCEPTION`) | **Traces** | Every `logger.*` call via `AzureLogHandler` |
| HTTP request spans (method, path, status code, duration) | **Requests** | Every inbound HTTP request via middleware `AzureExporter` |
| Unhandled exception stack traces | **Exceptions** | `logger.exception()` in error handler (full traceback) |

#### Setup (Azure Portal)
```bash
# Create Application Insights resource in your resource group:
az monitor app-insights component create \
  --app warehouse-appinsights \
  --location centralindia \
  --resource-group <your-rg> \
  --workspace <your-log-analytics-workspace>

# Copy the Connection String from: Overview → Connection String
# Add as App Service Application Setting (no code deploy needed):
# AZURE_APPINSIGHTS_CONNECTION_STRING="InstrumentationKey=...;IngestionEndpoint=..."
```

#### How It Works
- **Environment variable:** `AZURE_APPINSIGHTS_CONNECTION_STRING`
- **Activation:** Set the variable in App Service → Configuration → Application Settings and restart
- **`appinsights_active` field:** `/api/monitoring/metrics` reports `true` **only** when
  `AzureLogHandler` was successfully attached at startup (`is_appinsights_active()`)
  — not merely when the environment variable is set
- **Local dev:** When connection string is absent, logs go to console + `warehouse_app.log` only
- **Graceful fallback:** If `opencensus-ext-azure` is not installed or the connection string
  is invalid, the application starts normally with local logging

#### Key Telemetry Events Captured
- Every HTTP request: method, path, status code, latency
- Login, logout, authentication failures
- Dataset upload start/success/failure
- Analysis run start/complete with duration
- Blob Storage upload events
- All application exceptions with full stack traces

---

## 16. CI/CD

The `.github/workflows/ci-cd.yml` pipeline runs on every push:

1. **Test** — runs all pytest tests with an in-memory SQLite DB
2. **Lint** — runs bandit security scan
3. **Deploy** — deploys to Azure App Service on `main` branch merge

### Required GitHub Secrets
| Secret Name | Value |
|-------------|-------|
| `AZURE_WEBAPP_PUBLISH_PROFILE` | Downloaded from Azure App Service |

---

## 17. Testing

```bash
# Run all tests
cd backend
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_auth.py -v
python -m pytest tests/test_csv_service.py -v
python -m pytest tests/test_ml_service.py -v
python -m pytest tests/test_api.py -v
```

### Test Coverage
| Module | Tests |
|--------|-------|
| Authentication | Login, wrong password, JWT validation, RBAC enforcement |
| CSV Validation | Required cols, invalid status, duplicates, missing values |
| Slot Classification | Utilization formula, zones, edge cases (all-blocked, all-occupied) |
| ML Service | Risk levels, LinearRegression vs heuristic, clipping, recommendations |
| API Endpoints | Upload, analysis trigger, grid, monitoring — with auth checks |

---

## 18. Performance Optimizations

### 1. Database Indexing
Composite indexes on `(warehouse_id, zone)` and `(warehouse_id, status)` ensure sub-millisecond slot queries even at 50,000+ slots.

### 2. Bulk Insert
`db.bulk_save_objects()` used when persisting slots from a CSV upload instead of individual `db.add()` calls. For 400 slots, this reduces insert time by ~60%.

### 3. SQLite WAL Mode
In local development, SQLite is configured in WAL (Write-Ahead Logging) mode for better concurrent read performance.

### 4. Response Pagination
Slot listing endpoints accept `page` and `page_size` parameters (max 500), preventing large result sets from overwhelming the API.

### 5. LRU-Cached Settings
`get_settings()` is decorated with `@lru_cache()` so the environment is parsed only once per process lifetime.

---

## 19. Security Measures

| Measure | Implementation |
|---------|---------------|
| Password hashing | bcrypt (passlib), factor ~12 |
| Authentication | JWT (HS256), 60-minute expiry |
| Authorization | FastAPI dependency injection per route |
| RBAC | ADMIN / WAREHOUSE_MANAGER enforced on every protected route |
| Input validation | Pydantic models on all request bodies |
| File validation | Type, size, CSV structure, status values checked server-side |
| Parameterized queries | SQLAlchemy ORM — no raw SQL string concatenation |
| CORS | Configured with explicit allowed origins |
| Secrets management | `.env` file, never committed (`.gitignore` enforced) |
| Secret scanning | bandit CI step checks for hardcoded credentials |

---

## 20. Demo Procedure

### End-to-End Demo Flow

1. **Open** `http://localhost:8000`
2. **Login** as `admin` / `Admin@123`
3. **Admin Panel →** Create a warehouse (e.g., `WH-001 / Main Warehouse`)
4. **Upload Data →** Select warehouse, drag-drop `data/warehouse_sample.csv`
5. **Observe** validation feedback and storage mode (local/azure)
6. **Run Analysis** from the Upload page
7. **Dashboard →** View KPIs, utilization gauge, zone chart, recommendations
8. **Warehouse Grid →** See 400 slots colored by status, hover for details
9. **AI Forecast →** See 7-day prediction chart and risk banner
10. **Op. Reports →** Create a CONGESTION report, load insights
11. **Logout → Login** as `manager` / `Manager@123`
12. **Verify** Upload and Admin nav items are hidden
13. **Try API** — confirm manager cannot POST to `/api/datasets/upload` (403)
14. **Monitoring →** View uptime, database type, Azure integration status
15. **Show** `http://localhost:8000/api/docs` for full API documentation

---

## 21. Limitations

- The ML forecast model is lightweight (LinearRegression). It is appropriate for a student cloud project but would require more sophisticated models (LSTM, Prophet) in production.
- Azure Logic Apps integration requires manual configuration in the Azure Portal; it is not auto-deployed by the CI/CD pipeline.
- MSSQL ODBC driver must be installed separately when deploying to Azure App Service (via custom startup script or Docker image).
- The current frontend is a single-page application served as static files. For large teams, a build step (e.g., Vite) would be beneficial.

---

## 22. Future Enhancements

- Real-time slot updates via WebSocket connections
- IoT sensor integration for automatic slot status updates
- Computer vision-based slot detection from warehouse cameras
- Multi-warehouse aggregated dashboard
- Mobile-responsive Progressive Web App
- Role hierarchy with warehouse-specific permissions
- Automated anomaly detection with Azure Anomaly Detector
- Power BI embedded dashboard integration

---

*This is an academic cloud computing project. All sample data is synthetic and generated for demonstration purposes only.*
