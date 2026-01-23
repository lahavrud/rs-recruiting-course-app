# Implementation Plan: Issue #88 - Shadow Profile Logic for Candidates

## 📋 Overview

**Issue:** [#88 - feat6: Shadow Profile Logic for Candidates](https://github.com/lahavrud/rs-recruitment/issues/88)

**Goal:** Implement logic to detect and merge duplicate candidate profiles. When a candidate applies for multiple jobs, the system should recognize them by email and link new applications to their existing profile rather than creating duplicates.

---

## 🔍 Current State Analysis

### Current Behavior
- `create_candidate_profile()` in `src/services/candidates.py` always creates a new `CandidateProfile`
- Email field has unique constraint (`email: str = Field(unique=True, index=True)`)
- Attempting to create duplicate email raises `IntegrityError` (see `test_create_candidate_profile_duplicate_email`)
- Application has unique constraint on `(job_id, candidate_id)` - prevents duplicate applications for same job

### Key Files
- `src/services/candidates.py` - Main service logic (166 lines)
- `src/api/candidates.py` - API endpoint (100 lines)
- `src/models.py` - Database models (179 lines)
- `src/schemas.py` - Pydantic schemas (includes `CandidateProfileCreate` and `CandidateProfileUpdate`)
- `tests/services/test_candidates.py` - Service tests (434 lines)
- `tests/models/test_candidate_profile.py` - Model tests (254 lines)

---

## 🎯 Required Changes

### 1. Service Layer (`src/services/candidates.py`)

#### 1.1 Create Helper Function: `find_candidate_by_email()`
**Purpose:** Query database for existing candidate by email address

```python
async def find_candidate_by_email(
    email: str,
    session: AsyncSession,
) -> CandidateProfile | None:
    """Find an existing candidate profile by email address.

    Args:
        email: Email address to search for
        session: Database session

    Returns:
        CandidateProfile if found, None otherwise
    """
```

**Implementation:**
- Use `select(CandidateProfile).where(CandidateProfile.email == email)`
- Return `scalar_one_or_none()`
- Keep it simple - exact email match only (no fuzzy matching for MVP)

#### 1.2 Create Helper Function: `update_candidate_profile()`
**Purpose:** Update existing candidate profile with new information from application

```python
async def update_candidate_profile(
    candidate: CandidateProfile,
    candidate_data: CandidateProfileCreate,
    resume_path: str | None = None,
    session: AsyncSession | None = None,
) -> CandidateProfile:
    """Update an existing candidate profile with new information.

    Update strategy:
    - Always update: full_name (may have changed)
    - Update if None: phone, linkedin_url, resume_path, interview fields
    - Never overwrite: email, created_at

    Args:
        candidate: Existing CandidateProfile to update
        candidate_data: New candidate data from form
        resume_path: Optional new resume path
        session: Database session (required)

    Returns:
        Updated CandidateProfile
    """
```

**Update Strategy:**
- **Always update:** `full_name` (person may have changed name)
- **Update if None:** `phone`, `linkedin_url`, `resume_path`, and all interview fields (`service_concept`, `salary_expectations`, etc.)
- **Never overwrite:** `email`, `created_at`, `id`
- **Resume handling:** If new resume is provided and existing `resume_path` is None, update it. If both exist, keep existing (don't overwrite).

#### 1.3 Refactor `create_candidate_profile()`
**New Flow:**
1. Verify job exists (existing logic)
2. Load company profile for email notification (existing logic)
3. Handle resume file upload if provided (existing logic)
4. **NEW:** Check if candidate exists by email
   - If exists:
     - Update candidate profile with new information (using `update_candidate_profile()`)
     - Check if Application already exists for this job+candidate
       - If exists: Raise appropriate error (or return existing? - need to decide)
       - If not exists: Create new Application
   - If not exists:
     - Create new CandidateProfile (existing logic)
     - Create new Application (existing logic)
5. Send email notification (existing logic)
6. Return CandidateProfileRead

**Key Considerations:**
- Application uniqueness: `(job_id, candidate_id)` constraint means candidate can only apply once per job
- If candidate exists and already applied to this job, we need to decide behavior:
  - Option A: Raise exception (e.g., `ApplicationAlreadyExistsError`)
  - Option B: Return existing application (idempotent)
  - **Recommendation:** Option A - raise exception (explicit is better than silent)

### 2. Exception Handling (`src/services/exceptions.py`)

#### 2.1 Add New Exception
```python
class ApplicationAlreadyExistsError(Exception):
    """Raised when attempting to create an application that already exists."""

    def __init__(self, job_id: int, candidate_id: int) -> None:
        self.job_id = job_id
        self.candidate_id = candidate_id
        super().__init__(
            f"Application already exists for job {job_id} and candidate {candidate_id}"
        )
```

### 3. API Layer (`src/api/candidates.py`)

#### 3.1 Update Error Handling
- Add handler for `ApplicationAlreadyExistsError` → `HTTP 409 Conflict`
- Keep existing handlers for `JobNotFoundError` and `ValueError`

### 4. Tests (`tests/services/test_candidates.py`)

#### 4.1 Update Existing Test: `test_create_candidate_profile_duplicate_email`
**Current:** Expects `IntegrityError` when duplicate email
**New:** Should NOT raise error, should reuse existing profile and create new Application

#### 4.2 Add New Tests

**Test: `test_create_candidate_profile_reuses_existing_profile`**
- Create candidate with email "john@example.com" for Job A
- Create another application with same email for Job B
- Verify: Same candidate profile ID, two applications exist

**Test: `test_create_candidate_profile_updates_existing_profile`**
- Create candidate with minimal data (no phone, no linkedin)
- Create second application with same email but more data (phone, linkedin)
- Verify: Profile updated with new data, original data preserved where appropriate

**Test: `test_create_candidate_profile_does_not_overwrite_resume`**
- Create candidate with resume_path = "resume1.pdf"
- Create second application with same email, new resume = "resume2.pdf"
- Verify: Profile keeps original resume_path (don't overwrite existing resume)

**Test: `test_create_candidate_profile_always_updates_full_name`**
- Create candidate with full_name = "John Doe"
- Create second application with same email, full_name = "John Smith"
- Verify: Profile updated with "John Smith"

**Test: `test_create_candidate_profile_duplicate_application_raises_error`**
- Create candidate application for Job A
- Try to create another application for same Job A with same email
- Verify: Raises `ApplicationAlreadyExistsError`

**Test: `test_find_candidate_by_email_exists`**
- Create candidate
- Call `find_candidate_by_email()`
- Verify: Returns correct candidate

**Test: `test_find_candidate_by_email_not_exists`**
- Call `find_candidate_by_email()` with non-existent email
- Verify: Returns None

### 5. API Tests (`tests/api/test_candidates.py`)

#### 5.1 Add Test: `test_apply_endpoint_reuses_existing_profile`
- Test that API endpoint correctly handles duplicate email scenario
- Verify HTTP 201 response (not error)

#### 5.2 Add Test: `test_apply_endpoint_duplicate_application_conflict`
- Test that applying twice to same job returns HTTP 409 Conflict

---

## 📝 Implementation Steps

### Phase 1: Core Service Logic
1. ✅ Add `ApplicationAlreadyExistsError` to `src/services/exceptions.py`
2. ✅ Create `find_candidate_by_email()` helper function
3. ✅ Create `update_candidate_profile()` helper function
4. ✅ Refactor `create_candidate_profile()` to use shadow profile logic
5. ✅ Handle Application uniqueness check (raise error if duplicate application)

### Phase 2: API Layer Updates
6. ✅ Update `src/api/candidates.py` to handle `ApplicationAlreadyExistsError` → HTTP 409

### Phase 3: Tests
7. ✅ Update `test_create_candidate_profile_duplicate_email` test
8. ✅ Add `test_create_candidate_profile_reuses_existing_profile`
9. ✅ Add `test_create_candidate_profile_updates_existing_profile`
10. ✅ Add `test_create_candidate_profile_does_not_overwrite_resume`
11. ✅ Add `test_create_candidate_profile_always_updates_full_name`
12. ✅ Add `test_create_candidate_profile_duplicate_application_raises_error`
13. ✅ Add `test_find_candidate_by_email_exists`
14. ✅ Add `test_find_candidate_by_email_not_exists`
15. ✅ Add API tests for duplicate scenarios

### Phase 4: Verification
16. ✅ Run all tests (`pytest`)
17. ✅ Verify no breaking changes
18. ✅ Check code coverage
19. ✅ Run linter (`ruff check`)

---

## 🔒 Edge Cases & Considerations

### 1. Application Uniqueness
- **Constraint:** `UniqueConstraint("job_id", "candidate_id")` prevents duplicate applications
- **Behavior:** If candidate already applied to same job, raise `ApplicationAlreadyExistsError`
- **Alternative considered:** Return existing application (idempotent) - **REJECTED** (explicit is better)

### 2. Resume Handling
- **Current:** If new resume provided, upload and store path
- **Update Strategy:**
  - If existing profile has no resume (`resume_path is None`): Update with new resume
  - If existing profile has resume: Keep existing resume (don't overwrite)
  - **Rationale:** Existing resume may be more complete/current

### 3. Profile Update Strategy
- **Always update:** `full_name` (person may have changed name)
- **Update if None:** All optional fields (phone, linkedin_url, interview fields)
- **Never overwrite:** `email`, `created_at`, `id`
- **Rationale:** Preserve original data while allowing profile enrichment

### 4. Email Case Sensitivity
- **Current:** Database unique constraint is case-sensitive (PostgreSQL default)
- **Consideration:** Should we normalize email to lowercase?
- **Decision:** Keep as-is for MVP (exact match only). Future enhancement: normalize to lowercase.

### 5. Transaction Safety
- All operations must be within same transaction
- If Application creation fails, profile update should rollback
- Use existing session management (no changes needed)

---

## ✅ Definition of Done Checklist

- [ ] Duplicate candidates detected by email
- [ ] New applications linked to existing profiles when email matches
- [ ] New profiles created only when email doesn't exist
- [ ] Application history maintained per candidate
- [ ] Profile updates work correctly (merge strategy implemented)
- [ ] Duplicate application attempts raise appropriate error
- [ ] Tests added or updated (service unit tests + API tests)
- [ ] No breaking changes introduced
- [ ] All existing tests pass
- [ ] Code follows project standards (type hints, docstrings, async patterns)
- [ ] Linter passes (`ruff check`)
- [ ] Test coverage maintained or improved

---

## 📚 Related Documentation

- **Architecture:** `docs/ARCHITECTURE.md` - Database schema, service layer pattern
- **Coding Standards:** `docs/CONTEXT.md` - Service layer rules, async patterns
- **Issue:** [#88](https://github.com/lahavrud/rs-recruitment/issues/88) - Original issue
- **Milestone:** "04 - Candidate Slice" - Part of candidate slice feature set

---

## 🚀 Next Steps

1. Review this plan with team/stakeholder
2. Start with Phase 1 (Core Service Logic)
3. Implement incrementally with tests
4. Verify each phase before moving to next
5. Update documentation if needed
