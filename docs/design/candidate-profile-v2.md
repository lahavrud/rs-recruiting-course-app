# CandidateProfile v2 — Design

**Issue:** #415  
**Status:** Approved, ready to implement  
**Blocks:** #414 (candidate self-service)

---

## Problem

The current `CandidateProfile` mixes two concerns on the same row:

1. **Person identity** — who the candidate is (name, email, phone, LinkedIn, resume)
2. **Job answers** — free-text responses to interview questions (service concept, salary expectations, strengths, growth areas)

This causes a real bug: a candidate who applies to two jobs shares one set of answer fields. `update_candidate_profile` uses "set if None" semantics, so job #2's admin sees job #1's answers — or worse, sees nothing if the candidate left them blank the second time.

Additionally, two columns (`military_service_details`, `transportation`) exist on the model but are never exposed in any schema, API, or frontend. They are dead weight.

---

## Decision

**Move the four interview-answer fields from `CandidateProfile` to `Application`.**

`CandidateProfile` becomes a clean person-identity + consent record.  
`Application` becomes the per-job context record, carrying its own answers.

Matching is planned for a future slice but will use different signals — these four free-text fields are admin-review only and will not feed a scoring algorithm.

---

## New Model Shape

### `CandidateProfile` (after)

| Field | Type | Notes |
|---|---|---|
| `id` | `int` PK | |
| `full_name` | `str` | |
| `email` | `str` | unique, indexed |
| `phone` | `str` | |
| `linkedin_url` | `str \| None` | |
| `resume_path` | `str \| None` | |
| `consent_given_at` | `datetime \| None` | from #413 |
| `consent_policy_version` | `str \| None` | from #413 |
| `consent_ip` | `str \| None` | from #413 |
| `consent_user_agent` | `str \| None` | from #413 |
| `created_at` | `datetime` | |

**Removed:** `service_concept`, `salary_expectations`, `personality_strength`, `personality_weakness`, `military_service_details`, `transportation`

### `Application` (after)

Existing columns unchanged, plus:

| Field | Type | Notes |
|---|---|---|
| `service_concept` | `Text \| None` | moved from CandidateProfile |
| `salary_expectations` | `Text \| None` | moved from CandidateProfile |
| `strength` | `Text \| None` | renamed from `personality_strength` |
| `growth_area` | `Text \| None` | renamed from `personality_weakness` |

---

## Schema Changes

### `CandidateProfileCreate`
Remove: `service_concept`, `salary_expectations`, `personality_weakness`, `personality_strength`

### `CandidateProfileUpdate`
Remove same four fields. After this, admin can only edit identity fields.

### `CandidateProfileRead`
Remove same four fields.

### `ApplicationRead` (new fields)
Add: `service_concept`, `salary_expectations`, `strength`, `growth_area`

### `ApplicationWithDetails`
No structural change — already embeds `CandidateProfileRead` and `JobRead`. Will gain interview fields via `ApplicationRead`.

---

## Service Changes

### `src/services/applications.py`
- `_upsert_candidate_and_application`: pass interview fields to the `Application` row at creation instead of `CandidateProfile`
- `_apply_common` / `create_candidate_profile`: accept interview fields separately; no longer pass them to `CandidateProfileCreate`

### `src/services/candidates.py`
- `update_candidate_profile`: remove `service_concept`, `salary_expectations`, `personality_weakness`, `personality_strength` from update logic

### `src/services/candidates_admin.py`
- `update_candidate`: remove the four fields from the patch path (admin can no longer overwrite interview answers from the candidate panel — they belong to each application)

---

## API Changes

### `POST /api/jobs/{id}/apply`
Form fields unchanged from the caller's perspective — still accepts `service_concept`, `salary_expectations`, `strength` (renamed from `personality_strength`), `growth_area` (renamed from `personality_weakness`). Backend writes them to `Application` instead of `CandidateProfile`.

### `PUT /api/admin/candidates/{id}`
Accepts only identity fields: `full_name`, `email`, `phone`, `linkedin_url`. Interview fields are no longer part of the candidate edit form.

### `GET /api/admin/applications` / `GET /api/admin/applications/{id}`
Response already includes `ApplicationWithDetails`; will now carry interview answers directly on the application object rather than nested under the candidate.

---

## Frontend Changes

### `ApplicationPage.tsx` (public form)
- Step 3 field names: `personality_strength` → `strength`, `personality_weakness` → `growth_area`
- Form submission: update `submitApplication` to send `strength` / `growth_area` instead of old names
- `CandidateApplicationForm` type updated accordingly

### `AdminCandidatesPage.tsx`
- **Detail modal — remove** the "Answers" section (`service_concept`, `salary_expectations`, `personality_strength`, `personality_weakness`). These no longer live on the candidate.
- **Detail modal — applications list**: expand each application row to show its own `service_concept`, `salary_expectations`, `strength`, `growth_area` inline (collapsed by default, expandable). Admin can see per-job answers in context.
- **Edit modal — remove** the four interview-answer textareas. Admin can only edit identity fields: `full_name`, `email`, `phone`, `linkedin_url`.

### `AdminApplicationsPage.tsx`
- **Detail modal answers section**: source changes from `app.candidate.service_concept` etc → `app.service_concept`, `app.salary_expectations`, `app.strength`, `app.growth_area`. No visual change to the admin — answers still appear in the same place.
- Update answer field labels to match renamed fields (`strength` / `growth_area`).

### `he.json`
- Rename keys: `publicJobs.application.strength` stays, `publicJobs.application.weakness` → `publicJobs.application.growthArea`
- `placeholders.weakness` → `placeholders.growthArea`

---

## Migration

Two Alembic revisions:

### Revision A — add columns to `application`
```sql
ALTER TABLE application ADD COLUMN service_concept TEXT;
ALTER TABLE application ADD COLUMN salary_expectations TEXT;
ALTER TABLE application ADD COLUMN strength TEXT;
ALTER TABLE application ADD COLUMN growth_area TEXT;
```

### Revision B — data backfill + drop from `candidateprofile`
```sql
-- Copy each candidate's current answers to all their applications.
-- For multi-application candidates the same values land on each application
-- row — the "set if None" upsert means the stored value is from the first
-- application anyway, so this is the best possible approximation.
UPDATE application a
SET
    service_concept    = cp.service_concept,
    salary_expectations = cp.salary_expectations,
    strength           = cp.personality_strength,
    growth_area        = cp.personality_weakness
FROM candidateprofile cp
WHERE a.candidate_id = cp.id;

-- Drop moved + dead columns
ALTER TABLE candidateprofile DROP COLUMN service_concept;
ALTER TABLE candidateprofile DROP COLUMN salary_expectations;
ALTER TABLE candidateprofile DROP COLUMN personality_strength;
ALTER TABLE candidateprofile DROP COLUMN personality_weakness;
ALTER TABLE candidateprofile DROP COLUMN military_service_details;
ALTER TABLE candidateprofile DROP COLUMN transportation;
```

SQLite (test path) handles both as plain DDL since the column types are untyped TEXT.

---

## What Does NOT Change

- The public form still has three steps; step 3 still has four optional textarea fields
- Resume upload, file validation, and storage paths are untouched
- Consent capture (#413) is untouched
- `purge_expired_candidates` only touches identity + resume — no changes needed
- The `candidate.delete` audit event is untouched
- Matching is a future feature using different signals; these four fields are admin-display only

---

## Ship Order

1. Alembic revision A (add columns to `application`)
2. Backend: model + schema + service + API changes
3. Alembic revision B (backfill + drop from `candidateprofile`)
4. Frontend: form field renames, admin page cleanup
5. Tests end-to-end

Can ship as one PR; if CI time is a concern, A+backend and B+frontend can be two sequential PRs against the same feature branch.
