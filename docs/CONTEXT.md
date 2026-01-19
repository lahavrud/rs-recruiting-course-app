# 🧠 AI Context & Coding Standards

**Project:** RS Recruitment – Boutique Recruitment Agency CRM  
**Architecture:** Modular Monolith, Vertical Slices  
**Primary Goal:** Ship a clean, maintainable MVP

---

## 1. Core Philosophy

- **Vertical Slices**
  Build features end-to-end (DB → business logic → API).
  Do NOT build by technical layers.

- **Admin as Gatekeeper**
  Companies, Jobs, and Matches require Admin approval.
  Public input is never auto-trusted.

- **Hybrid Auth Model**
  - Admins & Companies are authenticated `Users`
  - Candidates are unauthenticated `CandidateProfile` leads
  - Do NOT add Candidate authentication unless explicitly requested

- **MVP First**
  Prefer simple, explicit solutions over abstractions.
  Avoid over-engineering and premature optimization.

---

## 2. Coding Standards

- **Language & Typing**
  - Python 3.12+
  - Strict type hints required
  - Prefer explicit return types

- **Project Structure**
  - `src/models.py` – All SQLModel database tables
  - `src/enums.py` – All enumeration types (UserRole, JobStatus, ApplicationStatus)
  - `src/schemas.py` – All Pydantic schemas for request/response validation
  - `src/api/` – API routers, split by domain (vertical slice)
    - `api/auth.py` – Authentication endpoints (register/login)
    - `api/admin.py` – Admin endpoints (company approval workflow)
    - `api/jobs_read.py` – Job read endpoints (GET operations)
    - `api/jobs_write.py` – Job write endpoints (POST, PUT, DELETE operations)
  - `src/services/` – Domain-specific business logic services
    - `services/auth.py` – Authentication business logic
    - `services/admin.py` – Admin approval business logic
    - `services/jobs.py` – Job management business logic
    - `services/exceptions.py` – Domain-specific exceptions
  - `src/core/` – Cross-cutting infrastructure
    - `core/tasks.py` – Arq task definitions for async background jobs
    - `core/infrastructure/` – Pure infrastructure (config, database, security, limiter, dependencies)
    - `core/services/` – Infrastructure services for external systems (email, storage)
    - See `ARCHITECTURE.md` for infrastructure decision details (storage, email, CORS, etc.)
  - `src/main.py` – FastAPI app entry point

- **Test Structure** (mirrors source structure)
  - `tests/api/` – Integration tests for API routers
  - `tests/services/` – Unit tests for domain services
  - `tests/core/` – Tests for core infrastructure
    - `core/infrastructure/` – Tests for infrastructure modules
    - `core/services/` – Tests for infrastructure services
    - `core/test_tasks.py` – Tests for async task processing

- **Business Logic & Service Layer**
  - Keep logic close to the domain
  - Avoid "fat routers"

  **When to use services (`src/services/`):**
  - Complex business logic (multi-step operations, validations, domain rules)
  - Logic that needs to be reused across multiple endpoints
  - Logic that should be testable without HTTP layer
  - Domain-specific operations (e.g., `services/auth.py`, `services/jobs.py`)

  **When to keep logic in routers:**
  - Simple CRUD operations (single model, no complex validation)
  - Trivial transformations
  - Direct pass-through to database

  **Service Layer Rules:**
  - Services should NOT import FastAPI (keep HTTP-agnostic)
  - Services raise domain exceptions (`services/exceptions.py`)
  - Routers convert domain exceptions to HTTP responses
  - Services accept `AsyncSession` as parameter (dependency injection)

- **Docstrings**
  - Use Google-style docstrings
  - Only for non-trivial logic

- **Testing**
  - `pytest` must pass before merging
  - Prefer simple unit tests over complex mocks
  - **SQLite FK Constraints:** Test databases use `enable_sqlite_foreign_keys()` from `tests/conftest.py` to enforce foreign key constraints, ensuring test behavior matches PostgreSQL production behavior

- **Async Database Rules**
  - ALWAYS use `await session.execute(...)` or `await session.get(...)`
  - NEVER use blocking I/O inside async functions
  - ALWAYS inject DB session via `get_session` dependency
  - Services must not manage DB lifecycle directly

- **Pydantic & SQLModel**
  - Keep **schemas** (`schemas.py`) separate from **models** (`models.py`)
  - Use `Create / Read / Update` schema patterns
  - Never expose sensitive fields (passwords, tokens)
  - All DB tables must use `table=True`

- **Security Baseline**
  - Passwords must be hashed using `bcrypt`
  - JWT secrets must come from environment variables
  - Auth logic lives only in `src/core/infrastructure/security.py`
  - Never return credentials or tokens in logs or responses

---

## 3. Domain Model (Source of Truth)

This summary reflects the authoritative domain model.
If there is a conflict, defer to `ARCHITECTURE.md`.

- **User**
  Authenticated entity  
  Roles: `ADMIN`, `COMPANY`

- **CompanyProfile**
  1:1 with User

- **CandidateProfile**
  Unauthenticated lead  
  Contains interview-related fields

- **Job**
  Linked to Company  
  Status: `PENDING_APPROVAL` → `PUBLISHED` → `CLOSED`

- **Application**
  Core business entity (Match)  
  Links Candidate ↔ Job  
  Status: `NEW` → `APPROVED_BY_ADMIN` → `REJECTED` → `HIRED`

---

## 4. What NOT To Do (Unless Explicitly Requested)

- Do NOT add Candidate authentication
- Do NOT introduce microservices
- Do NOT create generic abstraction layers
- Do NOT add tables or enums not defined in the domain
- Do NOT optimize for scale prematurely

---

## 5. Git & GitHub Workflow

### Commit Messages
Always use **Conventional Commits**:
- `feat(scope): description`
- `fix(scope): description`
- `chore(infra): description`
- `refactor(scope): description`
- `docs(scope): description`

### Branch Naming
- Features: `feat/short-description`
- Fixes: `fix/short-description`
- Chores: `chore/short-description`
- Documentation: `docs/short-description`
- Refactoring: `refactor/short-description`

### Trunk-Based Development
- Short-lived branches (hours → 1 day), merged via PR
- Keep `main` always deployable
- All changes to `main` must go through PR (no direct pushes)

### GitHub CLI (`gh`) Defaults
When performing GitHub actions, use the following:

#### Creating Issues (`gh issue create`)
- `--assignee "@me"`
- `--project "RS Recruitment - MVP"`
- `--label` (Choose appropriately, always include P1 / P2 / P3)
- **Body:** Use `.github/ISSUE_TEMPLATE/task.md`
  - Goal
  - Tasks (Checklist)
  - Definition of Done

#### Creating Pull Requests (`gh pr create`)
- `--assignee "@me"`
- `--base main`
- **Body:** Clear summary of changes + related issue

### Branch Protection (Repository Ruleset)
- `main` branch is protected via GitHub Repository Ruleset
- **Required:** CI checks must pass (`lint`, `test`)
- **Required:** Branch must be up to date before merging
- **Required:** Pull requests required (no direct pushes)
- **No bypass:** Even administrators cannot bypass rules
- **No force pushes:** Non-fast-forward protection enabled
- **No deletion:** Branch deletion prevented

### CI/CD Expectations
- Code must pass CI before merge to `main`
- Wait for CI to complete before merging PRs
- Fix failing CI before adding new features
- Never bypass failing tests

---

## 6. Environment Notes

- SQLite is used for local development only
- Database engine may change without impacting domain logic
- **Stack:** Python 3.12+, FastAPI, SQLModel (Async), Alembic
- **Database:** PostgreSQL (Prod) / SQLite (Dev & Tests)
- **Environment:** WSL (Ubuntu)

---

## 7. Immediate Goal

Focus exclusively on the **current active vertical slice**.
Deliver working functionality over theoretical completeness.
