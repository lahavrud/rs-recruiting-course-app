# Architecture Decisions

This document captures all architectural decisions made for the RS Recruitment MVP, with references to GitHub Issues where decisions were discussed and implemented.

---

## Table of Contents

1. [Design Principles](#design-principles)
2. [Authentication Model](#authentication-model)
3. [Infrastructure Decisions](#infrastructure-decisions)
4. [Frontend Architecture](#frontend-architecture)
5. [Backend Architecture](#backend-architecture)
6. [Database Schema](#database-schema)
7. [Deployment & DevOps](#deployment--devops)
8. [Code Quality & Standards](#code-quality--standards)

---

## Design Principles

These principles guide all architectural decisions:

- **Monolith First** – Single deployable service with clear domain boundaries
- **Vertical Slices** – Features are developed end-to-end (DB → Business Logic → API → Tests)
- **Admin as Gatekeeper** – All public data requires admin approval
- **Match is the Product** – The Application entity is the system core
- **Low friction MVP** – Minimal auth surface, minimal public access
- **Future-ready** – Decisions documented, refactors anticipated
- **Architecture-First** – Critical infrastructure decisions made before dependent features

**Related Issues:**
- [#15](https://github.com/lahavrud/rs-recruitment/issues/15) - docs: setup project architecture, roadmap, and ai context

---

## Authentication Model

### Hybrid Auth Model

**Decision:** Implement a hybrid authentication model where authenticated Users (Admins and Companies) can log in, while Candidates remain unauthenticated leads.

**Rationale:** This model reduces security risk and complexity while keeping the system flexible for future enhancements.

**Implementation:**
- **Users** authenticate and log in
  - Admins (role: `ADMIN`)
  - Companies (role: `COMPANY`)
- **Candidates** do NOT authenticate
  - They are treated as leads / data entities
  - Future authentication is optional and non-breaking

**Related Issues:**
- [#25](https://github.com/lahavrud/rs-recruitment/issues/25) - feat: minimal auth system (registration + login)
- [#23](https://github.com/lahavrud/rs-recruitment/issues/23) - feat: company onboarding (auth + db)

**Status:** ✅ Implemented

---

## Infrastructure Decisions

### 1. File Storage Strategy

**Problem:** `CandidateProfile.resume_path` implies file storage, but Docker containers are ephemeral. Local file storage will be lost on container restart/redeploy.

**Decision:** Implement a storage abstraction layer supporting multiple providers (Local, S3, MinIO) to enable resume uploads without vendor lock-in.

**Options Considered:**
- **AWS S3** – Production-ready, scalable, pay-per-use
- **Cloudinary** – Image/document optimization built-in
- **MinIO** – Self-hosted S3-compatible, good for dev/staging
- **Local Volume Mount** – Only for development, not production

**Chosen Solution:** Storage abstraction layer with provider abstraction interface
- **Local Storage** – For development and tests (`src/core/services/storage.py::LocalStorageProvider`)
- **S3/MinIO Storage** – For production (`src/core/services/storage.py::S3StorageProvider`)
- Provider selection via `STORAGE_PROVIDER` environment variable (`local` or `s3`)

**Implementation:**
- Abstract base class: `StorageProvider` in `src/core/services/storage.py`
- Methods: `upload_file()`, `get_file_url()`, `delete_file()`
- File validation: Size limits and file type checking
- Configuration: `src/core/infrastructure/config.py` with `storage_provider`, `aws_s3_bucket_name`, `local_storage_path`

**Related Issues:**
- [#43](https://github.com/lahavrud/rs-recruitment/issues/43) - feat(infra): Implement storage abstraction layer for file uploads (S3/MinIO/Local) ✅ CLOSED
- [#30](https://github.com/lahavrud/rs-recruitment/issues/30) - infra: integrate AWS S3 and SES services ✅ CLOSED

**Status:** ✅ Implemented

---

### 2. Email/Notification Service

**Problem:** Notifications are scheduled late (Phase 4), but admins need real-time alerts when candidates apply. Without email service, admins must manually refresh dashboard.

**Decision:** Integrate email service early (Infrastructure phase) with async task processing for guaranteed delivery.

**Options Considered:**
- **SMTP (Gmail/SendGrid)** – Simple, reliable, works with any provider
- **SendGrid API** – Transactional email service, better deliverability
- **AWS SES** – Cost-effective at scale
- **Postmark** – Developer-friendly, great deliverability

**Chosen Solution:** Email abstraction layer with async task queue (Arq + Redis)
- **Email Providers:** Abstract interface supporting SES and SMTP (`src/core/services/email.py`)
- **Task Queue:** Arq with Redis for async email processing (`src/core/tasks.py`)
- **Retry Logic:** Automatic retries for failed email sends
- Provider selection via `EMAIL_PROVIDER` environment variable (`ses` or `smtp`)

**Implementation:**
- Abstract base class: `EmailProvider` in `src/core/services/email.py`
- Implementations: `SESEmailProvider`, `SMTPEmailProvider`
- Async task: `send_email_task()` in `src/core/tasks.py`
- Redis integration: Redis service in `docker-compose.yml`
- Configuration: `src/core/infrastructure/config.py` with email provider settings

**Notification Triggers:**
- New candidate application → Email admin
- Company registration → Email admin (approval needed)
- Job posted → Email admin (approval needed)
- Application status changed → Email candidate/company

**Related Issues:**
- [#44](https://github.com/lahavrud/rs-recruitment/issues/44) - feat(infra): Implement async task processing with Arq for guaranteed email delivery ✅ CLOSED
- [#30](https://github.com/lahavrud/rs-recruitment/issues/30) - infra: integrate AWS S3 and SES services ✅ CLOSED
- [#90](https://github.com/lahavrud/rs-recruitment/issues/90) - feat8: Notifications Integration (pending)

**Status:** ✅ Implemented (email service), 🔄 Pending (notification integration)

---

### 3. Containerization Strategy

**Problem:** Need consistent runtime environment across all stages (Dev, Test, Prod) to avoid "it works on my machine" issues.

**Decision:** Containerize the application using Docker with multi-stage builds for optimized image size.

**Implementation:**
- **Dockerfile:** Multi-stage build with Python 3.12 base image
- **docker-compose.yml:** Includes API service, Redis service, and Arq worker
- **Health Checks:** Configured for all services
- **Volume Mounts:** Persistent data storage for SQLite (dev) and local storage

**Related Issues:**
- [#9](https://github.com/lahavrud/rs-recruitment/issues/9) - Containerize application with docker ✅ CLOSED

**Status:** ✅ Implemented

---

### 4. CI/CD Pipeline

**Problem:** Need automated quality checks and testing on every push to prevent regressions.

**Decision:** Implement GitHub Actions CI/CD pipeline with linting, testing, and Docker build verification.

**Implementation:**
- **Workflow:** `.github/workflows/ci.yml`
- **Jobs:**
  - `lint`: Ruff linter, Ruff formatter, custom validation scripts
  - `test`: Pytest with parallel execution
  - `docker-build`: Docker image build and health check verification
- **Validation Scripts:**
  - `validate_imports.py` - SOC enforcement (separation of concerns)
  - `check_file_sizes.py` - File size limits
  - `validate_type_hints.py` - Type hint validation
  - `validate_blocking_io.py` - Blocking I/O detection in async functions
  - `validate_test_files.py` - Test file existence checks

**Related Issues:**
- [#21](https://github.com/lahavrud/rs-recruitment/issues/21) - infra: ci/cd pipeline ✅ CLOSED
- [#80](https://github.com/lahavrud/rs-recruitment/issues/80) - chore(infra): Add type hints, blocking I/O, and test file validation to CI ✅ CLOSED

**Status:** ✅ Implemented

---

## Frontend Architecture

### 1. Frontend Architecture Decision

**Problem:** Roadmap mentions "Public Job Board" and "Admin Dashboard" but doesn't specify if FastAPI serves HTML or acts as headless API.

**Decision:** Use a separate SPA (Single Page Application) with FastAPI as a headless API.

**Options Considered:**

**A. Server-Side Rendering (SSR) with Jinja2**
- FastAPI serves HTML templates
- Simpler deployment (single service)
- SEO-friendly
- Less interactive, harder to scale frontend separately

**B. Separate SPA (React/Vue/Svelte)** ✅ **CHOSEN**
- FastAPI as headless API only
- Better UX, more interactive
- Separate deployment, CORS configuration needed
- Better for future mobile apps

**C. Hybrid (SSR + API)**
- FastAPI serves public pages (SSR)
- Admin/Company dashboards as SPA
- More complex but flexible

**Rationale:** Better separation of concerns, easier to scale frontend independently, better UX for dashboards.

**API Structure:** All endpoints return JSON. Frontend consumes REST API with JWT authentication.

**Related Issues:**
- Frontend issues pending: [#91](https://github.com/lahavrud/rs-recruitment/issues/91), [#92](https://github.com/lahavrud/rs-recruitment/issues/92), [#93](https://github.com/lahavrud/rs-recruitment/issues/93)

**Status:** ✅ Decision made, 🔄 Implementation pending

---

### 2. CORS Configuration

**Problem:** With a separate SPA frontend, browsers enforce Same-Origin Policy. Frontend requests to backend API will be blocked unless CORS is properly configured.

**Decision:** Configure CORS middleware in FastAPI with environment-based origin whitelisting.

**Implementation:**
- **Middleware:** FastAPI `CORSMiddleware` in `src/main.py`
- **Configuration:** `ALLOWED_ORIGINS` environment variable (comma-separated list)
- **Default:** `http://localhost:3000` (development)
- **Security:** Never use wildcard (`*`) in production

**Configuration Requirements:**
- **Allowed Origins:** Environment-specific (dev/staging/prod)
- **Allowed Methods:** `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS`
- **Allowed Headers:** `Content-Type`, `Authorization` (for JWT tokens)
- **Credentials:** `True` (to allow cookies/auth headers)

**Code Location:** `src/main.py` lines 27-34

**Related Issues:**
- Architecture decision documented in this file (no specific issue, part of frontend architecture)

**Status:** ✅ Implemented

---

## Backend Architecture

### 1. Service Layer Pattern

**Problem:** Business logic was mixed with API routes, making code harder to test and maintain.

**Decision:** Extract business logic into a dedicated service layer, keeping routers thin.

**Implementation:**
- **Structure:** `src/services/` directory with domain-specific services
- **Pattern:** Routers delegate to services, services contain business logic
- **Benefits:** Better testability, separation of concerns, reusable business logic

**Example Structure:**
```
src/
├── api/              # Thin routers (FastAPI endpoints)
│   ├── auth.py
│   └── admin.py
└── services/         # Business logic
    ├── auth.py
    └── admin.py
```

**Related Issues:**
- [#41](https://github.com/lahavrud/rs-recruitment/issues/41) - refactor(services): Extract auth business logic into service layer ✅ CLOSED

**Status:** ✅ Implemented

---

### 2. Database Models & Schema

**Problem:** Need to implement domain models matching the architecture ERD.

**Decision:** Use SQLModel (SQLAlchemy + Pydantic) for database models with Alembic for migrations.

**Implementation:**
- **Models:** `src/models.py` with User, CompanyProfile, Job, CandidateProfile, Application
- **Enums:** `src/enums.py` with UserRole, JobStatus, ApplicationStatus
- **Schemas:** `src/schemas.py` with Pydantic schemas for API validation
- **Migrations:** Alembic for database schema versioning
- **Async:** Async SQLModel engine for async/await support

**Related Issues:**
- [#42](https://github.com/lahavrud/rs-recruitment/issues/42) - feat(models): Add Job, CandidateProfile, and Application models with relationships ✅ CLOSED
- [#23](https://github.com/lahavrud/rs-recruitment/issues/23) - feat: company onboarding (auth + db) ✅ CLOSED

**Status:** ✅ Implemented

---

### 3. Error Handling & Transaction Management

**Problem:** Race conditions and transaction rollback issues in user registration.

**Decision:** Implement proper error handling with explicit transaction rollbacks and IntegrityError handling.

**Implementation:**
- **Transaction Rollback:** Explicit `session.rollback()` on all error paths
- **IntegrityError Handling:** Catch database constraint violations and convert to domain exceptions
- **Error Types:** Custom exceptions in `src/services/exceptions.py`

**Related Issues:**
- [#47](https://github.com/lahavrud/rs-recruitment/issues/47) - fix(auth): Handle race condition in user registration (TOCTOU) ✅ CLOSED
- [#48](https://github.com/lahavrud/rs-recruitment/issues/48) - fix(auth): Add explicit transaction rollback on registration failure ✅ CLOSED

**Status:** ✅ Implemented

---

## Database Schema

### Entity Relationship Diagram

```mermaid
erDiagram
    User ||--o| CompanyProfile : owns
    CompanyProfile ||--o{ Job : posts
    Job ||--o{ Application : receives
    CandidateProfile ||--o{ Application : submits

    %% Auth System (Admins & Companies)
    User {
        int id
        string email
        string hashed_password
        enum role "ADMIN, COMPANY"
        bool is_active "False until Admin approves"
        datetime created_at
    }

    %% Company Data
    CompanyProfile {
        int id
        int user_id "FK to User"
        string name
        string logo_url
        string contact_person
        string contact_phone
        datetime created_at
    }

    %% Job Inventory
    Job {
        int id
        int company_id
        string title
        string description
        string requirements
        string location
        enum status "PENDING_APPROVAL, PUBLISHED, CLOSED"
        datetime created_at
    }

    %% Candidate Lead (No Authentication)
    CandidateProfile {
        int id
        string full_name
        string email
        string phone
        string resume_path
        string linkedin_url

        %% Interview Form (Subject to Change)
        text service_concept
        text salary_expectations
        text military_service_details
        text transportation
        text personality_weakness
        text personality_strength

        datetime created_at
    }

    %% Match (Core Business Entity)
    Application {
        int id
        int job_id
        int candidate_id
        datetime created_at
        enum status "NEW, APPROVED_BY_ADMIN, REJECTED, HIRED"
        text admin_notes
    }
```

**Key Relationships:**
- `User` 1:1 `CompanyProfile` (one user owns one company profile)
- `CompanyProfile` 1:N `Job` (one company posts many jobs)
- `Job` 1:N `Application` (one job receives many applications)
- `CandidateProfile` 1:N `Application` (one candidate submits many applications)

**Status:** ✅ Implemented

---

## Deployment & DevOps

### 1. Database Backup Strategy

**Problem:** Production will use PostgreSQL. Docker volumes are insufficient for production safety. Need automated backup strategy to prevent data loss.

**Decision:** Use managed PostgreSQL service with automated backups for staging/production.

**Options Considered:**
- **Automated PostgreSQL Backups** – pg_dump scheduled via cron/kubernetes job
- **Managed Database Service** ✅ **CHOSEN** – AWS RDS Managed DB (built-in backups)
- **Point-in-Time Recovery** – WAL archiving for PostgreSQL
- **Backup to S3** – Store dumps in object storage

**Recommendation:**
- **Development:** Manual backups or Docker volume snapshots
- **Staging/Production:** Use managed PostgreSQL (RDS/DO) with automated daily backups + point-in-time recovery
- **Backup Retention:** 7 days daily, 4 weeks weekly, 12 months monthly

**Implementation Requirements:**
- Document backup/restore procedures
- Test restore process regularly
- Monitor backup success/failure
- Store backups in separate region/account

**Related Issues:**
- [#94](https://github.com/lahavrud/rs-recruitment/issues/94) - devops1: Database Backup Strategy 🔄 OPEN

**Status:** 🔄 Decision made, implementation pending

---

### 2. Environment Deployment Strategy

**Problem:** Need deployment strategy for dev, staging, and production environments.

**Decision:** Deploy to separate environments with environment-specific configurations.

**Environments:**
1. **Development** – Shared dev environment for testing
2. **Staging** – Mirrors production for final validation
3. **Production** – Live production environment

**Deployment Requirements:**
- Environment-specific configuration (env vars, CORS origins, database URLs)
- CI/CD pipeline for automatic deployment
- SSL/TLS certificates for staging/production
- Basic monitoring and alerting

**Related Issues:**
- [#95](https://github.com/lahavrud/rs-recruitment/issues/95) - devops2: Dev Environment Deployment 🔄 OPEN
- [#96](https://github.com/lahavrud/rs-recruitment/issues/96) - devops3: Staging Environment Deployment 🔄 OPEN
- [#97](https://github.com/lahavrud/rs-recruitment/issues/97) - deploy1: Production Deployment 🔄 OPEN

**Status:** 🔄 Decisions made, implementation pending

---

## Code Quality & Standards

### 1. Pre-commit Hooks

**Problem:** Need to enforce code quality and security standards before code reaches the repository.

**Decision:** Implement comprehensive pre-commit hooks for code quality, security, and commit message validation.

**Implementation:**
- **File Quality:** Trailing whitespace, end-of-file, YAML/JSON validation
- **Security:** detect-secrets to prevent credential commits
- **Commit Messages:** Conventional Commits format validation
- **Linting:** Ruff auto-fix enabled
- **Secrets Baseline:** Baseline file for false positives

**Related Issues:**
- [#75](https://github.com/lahavrud/rs-recruitment/issues/75) - chore(infra): Enhance pre-commit hooks configuration ✅ CLOSED

**Status:** ✅ Implemented

---

### 2. Code Validation Standards

**Problem:** Need automated validation to enforce code quality standards and prevent common issues.

**Decision:** Implement validation scripts in CI to check for:
- Type hints on public functions
- Blocking I/O in async functions
- Test file existence (matching source structure)
- Import patterns (SOC enforcement)
- File size limits

**Implementation:**
- **Scripts:** `scripts/validate_*.py` for various validations
- **CI Integration:** All validations run in CI `lint` job
- **Fast Execution:** All validations run in < 5 seconds

**Related Issues:**
- [#80](https://github.com/lahavrud/rs-recruitment/issues/80) - chore(infra): Add type hints, blocking I/O, and test file validation to CI ✅ CLOSED

**Status:** ✅ Implemented

---

## Decision Log

This section tracks when decisions were made and implemented:

| Decision | Issue | Status | Date |
|----------|-------|--------|------|
| File Storage Strategy | [#43](https://github.com/lahavrud/rs-recruitment/issues/43) | ✅ Implemented | - |
| Email/Notification Service | [#44](https://github.com/lahavrud/rs-recruitment/issues/44) | ✅ Implemented | - |
| Containerization | [#9](https://github.com/lahavrud/rs-recruitment/issues/9) | ✅ Implemented | - |
| CI/CD Pipeline | [#21](https://github.com/lahavrud/rs-recruitment/issues/21) | ✅ Implemented | - |
| Frontend Architecture | Architecture doc | ✅ Decision made | - |
| CORS Configuration | Architecture doc | ✅ Implemented | - |
| Service Layer Pattern | [#41](https://github.com/lahavrud/rs-recruitment/issues/41) | ✅ Implemented | - |
| Database Models | [#42](https://github.com/lahavrud/rs-recruitment/issues/42) | ✅ Implemented | - |
| Error Handling | [#47](https://github.com/lahavrud/rs-recruitment/issues/47), [#48](https://github.com/lahavrud/rs-recruitment/issues/48) | ✅ Implemented | - |
| Database Backup Strategy | [#94](https://github.com/lahavrud/rs-recruitment/issues/94) | 🔄 Pending | - |
| Environment Deployment | [#95](https://github.com/lahavrud/rs-recruitment/issues/95), [#96](https://github.com/lahavrud/rs-recruitment/issues/96), [#97](https://github.com/lahavrud/rs-recruitment/issues/97) | 🔄 Pending | - |
| Pre-commit Hooks | [#75](https://github.com/lahavrud/rs-recruitment/issues/75) | ✅ Implemented | - |
| Code Validation | [#80](https://github.com/lahavrud/rs-recruitment/issues/80) | ✅ Implemented | - |

---

## Future Considerations

These are potential future architecture decisions that may need to be made:

1. **Candidate Authentication** – Currently candidates are unauthenticated leads. Future authentication would be optional and non-breaking.
2. **Microservices** – Currently a monolith. Future microservices would require careful planning.
3. **Advanced Monitoring** – Basic monitoring is planned. Advanced observability (tracing, metrics) may be needed.
4. **Caching Strategy** – No caching layer currently. Redis could be used for caching in addition to task queue.
5. **API Versioning** – No versioning strategy currently. May be needed for future API changes.

---

## References

- [GitHub Issues](https://github.com/lahavrud/rs-recruitment/issues) - All architecture-related issues
- [Roadmap](ROADMAP.md) - Development timeline and dependencies
- [Context](CONTEXT.md) - Project context and standards
- [GitHub Organization](GITHUB_ORGANIZATION.md) - Issue templates and project management
