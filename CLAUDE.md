# RS Recruitment — Developer Guide

## Tech Stack

- **Frontend**: React 19 + TypeScript + Vite + Tailwind v4
- **Backend**: FastAPI (Python) + SQLModel async + PostgreSQL
- **Auth**: JWT access token in `localStorage` + HttpOnly refresh-token cookie. `AuthContext` resolves initial state synchronously from `localStorage` and verifies via `/api/auth/me` on mount.
- **i18n**: react-i18next, Hebrew-only (`he`), RTL forced globally via `<html dir="rtl" lang="he">`
- **Routing**: React Router v7

---

## Frontend Architecture

### Directory layout

```
backend/src/
├── api/
│   ├── auth/         login.py, registration.py, candidate_registration.py, activation.py,
│   │                 password_reset.py, password_change.py, invites.py
│   ├── admin/        companies.py, invites.py, jobs.py, applications.py, candidates.py, audit.py
│   ├── company/      jobs.py, profile.py, resumes.py
│   ├── public/       jobs.py (board), applications.py (apply flow)
│   ├── seo/          (prerender package)
│   └── sentry_tunnel.py
├── services/
│   ├── auth/         session.py, registration.py, activation.py, password_reset.py
│   ├── admin/        companies.py, company_approval.py, company_profiles.py, invites.py,
│   │                 jobs.py (CRUD), jobs_workflow.py (approve/reject/contact),
│   │                 applications.py, candidates.py
│   ├── company/      jobs.py, profile.py, candidates.py
│   ├── public/       jobs.py, applications.py
│   ├── utils/        audit.py, contract_pdf.py, legal.py
│   └── exceptions.py (flat — imported by 15+ files)

frontend/src/
├── components/
│   ├── guards/
│   │   ├── AdminRoute.tsx     # Route guard: requires role=ADMIN
│   │   ├── CompanyRoute.tsx   # Route guard: requires role=COMPANY
│   │   ├── CandidateRoute.tsx # Route guard: requires role=CANDIDATE
│   │   └── ProtectedRoute.tsx # Route guard: requires authenticated user
│   ├── layout/
│   │   ├── AppShell.tsx      # Root layout switcher (auth / public / bare)
│   │   ├── Header.tsx        # Authenticated top bar
│   │   └── Sidebar.tsx       # Authenticated nav sidebar (mobile drawer + desktop)
│   ├── dashboard/
│   │   ├── CandidateDashboard.tsx        # Candidate-role dashboard (composes sub-components below)
│   │   ├── DashboardHero.tsx             # Greeting + applications count + profile completion stats
│   │   ├── DashboardProfileCompletion.tsx # Inline completion strip with inline field editors
│   │   ├── DashboardRecentApplications.tsx
│   │   ├── DashboardBrowseJobsCta.tsx
│   │   ├── DashboardInlineEditor.tsx     # Phone / LinkedIn / resume inline-edit widget
│   │   └── dashboardUtils.ts             # profileCompletionPercent pure helper
│   ├── admin/
│   │   ├── ActiveFilterChip.tsx   # Copper chip with remove button
│   │   ├── AnimatedAccordion.tsx  # Accordion + CollapsibleSection + FormSection exports
│   │   ├── FunnelIcon.tsx
│   │   ├── MobileEntityCard.tsx
│   │   ├── MobileListSkeleton.tsx
│   │   ├── SearchableMultiSelect.tsx
│   │   └── SearchableSelect.tsx
│   └── ui/
│       ├── AutoGrowTextarea.tsx   # Textarea that auto-grows with content
│       ├── Button.tsx             # Action button — variants: primary/ghost/danger/success
│       ├── ConfirmDialog.tsx
│       ├── Dialog.tsx
│       ├── EmptyState.tsx
│       ├── ErrorState.tsx
│       ├── Eyebrow.tsx            # Copper section-label (10px, uppercase, tracking-widest)
│       ├── Field.tsx              # Unified form field — label/error/hint, label or div wrapper
│       ├── InfiniteScrollFooter.tsx # Sentinel + "loading more" for useInfiniteList
│       ├── KebabButton.tsx        # 3-dot DropdownMenu trigger (size sm|md)
│       ├── Logo.tsx
│       ├── LogoBanner.tsx
│       ├── NoResults.tsx          # Dashed-border filtered-empty placeholder
│       ├── PageHeader.tsx         # Copper eyebrow + gold rule + subtitle (reusable)
│       ├── StatusBadge.tsx        # Generic rounded-full badge — <StatusBadge label colorCls>
│       └── TableSkeleton.tsx
├── pages/
│   ├── admin/
│   │   ├── components/            # Co-located sub-components (dialogs, tabs, helpers)
│   │   ├── AdminApplicationsPage.tsx
│   │   ├── AdminCandidatesPage.tsx
│   │   ├── AdminCompaniesPage.tsx
│   │   └── AdminJobsPage.tsx
│   ├── public/
│   │   ├── components/            # Co-located sub-components (steps, modals, nav)
│   │   ├── ApplicationPage.tsx
│   │   ├── JobBoardPage.tsx
│   │   ├── JobDetailPage.tsx
│   │   └── LandingPage.tsx
│   ├── candidate/
│   │   ├── components/            # Co-located sub-components
│   │   ├── CandidateApplicationDetailPage.tsx
│   │   ├── CandidateApplicationsPage.tsx
│   │   └── CandidateProfilePage.tsx
│   └── …                          # Auth pages, company pages, DashboardPage
├── utils/
│   ├── formatDate.ts              # formatDate / formatDateLong (he-IL locale)
│   ├── validators.ts              # EMAIL_RE, MOBILE_RE (strict Israeli), COMPANY_ID_RE + validateCompanyProfile/validateJob
│   └── …                          # apiError, analytics, focusFirstError, mime, token
├── contexts/                      # AuthContext
├── styles/
│   └── forms.ts                   # inputCls, textareaCls, selectCls
├── locales/
│   └── he.json                    # All UI strings in Hebrew
└── index.css                      # Tailwind @theme tokens + global utilities
```

### AppShell routing logic

`AppShell` inspects `pathname` and renders one of three shells:

| Condition | Shell |
|---|---|
| `/`, `/login`, `/register`, `/register-candidate`, `/activate` | Bare — page owns its own layout |
| Authenticated (any role) | Header + Sidebar + `bg-page` main area |
| Unauthenticated (public) | `PublicHeader` + `bg-page` main area |

Note: `/jobs` and its sub-paths always render the public shell regardless of auth state — an authenticated candidate browsing jobs sees the same layout as an anonymous visitor (`PublicHeader` switches its CTA based on `isAuthenticated`).

### Routes (App.tsx)

| Path | Guard | Page |
|---|---|---|
| `/` | — | `LandingPage` |
| `/login` `/register` `/register-candidate` `/activate` | — | Auth pages |
| `/jobs` `/jobs/:id` `/jobs/:id/apply` | — | Public job board + apply |
| `/dashboard` | `ProtectedRoute` | Role-aware `DashboardPage` |
| `/admin/companies` `/admin/jobs` `/admin/applications` `/admin/candidates` | `AdminRoute` | Admin pages |
| `/company/jobs` | `CompanyRoute` | `CompanyJobsPage` |
| `/candidate/profile` | `CandidateRoute` | `CandidateProfilePage` |
| `/candidate/applications` | `CandidateRoute` | `CandidateApplicationsPage` |
| `/candidate/applications/:id` | `CandidateRoute` | `CandidateApplicationDetailPage` |

---

## Design System

### Philosophy
Dark luxury boutique aesthetic. Minimal, warm, metallic accents. Every color must come from the token system — **no hardcoded hex values in component files**.

### Color tokens (`index.css` `@theme`)

All tokens are available as Tailwind utilities (`bg-*`, `text-*`, `border-*`, `from-*`, etc.).

#### Dark surfaces (light → deep)
| Token | Value | Usage |
|---|---|---|
| `card-raised` | `#1E1C1A` | Modals, elevated cards, section backgrounds, hover targets |
| `card` | `#1A1816` | Default card and panel surfaces |
| `section` | `#181614` | Landing page dark section backgrounds |
| `well` | `#141210` | Form inputs, table headers (sunken surface) |
| `page` | `#121110` | Main app / content area background |
| `void` | `#0D0B09` | Navigation bars, header, auth page backgrounds |

#### Brand metals
| Token | Usage |
|---|---|
| `copper` (`#B87333`) | Primary brand accent, CTAs, active states, eyebrow text |
| `gold` (`#C9A84C`) | Hover state for copper elements, gradient highlights |
| `copper-dark` | Pressed/dark variant |
| `nickel` | Neutral metallic text |

#### Light palette (admin/company shell)
The light tokens (`canvas`, `surface`, `ink`, `line`, etc.) are defined but currently only used in the authenticated shell for potential future light-mode admin views.

#### Status
`success`, `warning`, `danger`, `info`, `hired` — semantic status colors.

### Typography
- **Body / headings**: Inter (weights 300, 400, 500, 600) — hierarchy via weight and size only, no separate display typeface
- **Brand wordmark**: Cormorant Garamond (`font-wordmark`, `font-light tracking-widest text-gold/60`) — used for "RS Recruiting" in LogoBanner and landing hero only. Never apply to body text or UI headings.
- Hebrew text renders RTL automatically

### Spacing / shape conventions
- Cards: `rounded-xl border border-white/8 bg-card`
- Inputs: import `inputCls` from `@/styles/forms` — never define locally
- Buttons: use `<Button>` from `@/components/ui/Button` — never write button classes inline
- Eyebrow section labels: use `<Eyebrow>` from `@/components/ui/Eyebrow` — never write the class string inline

### PageHeader component

Use `<PageHeader>` for all page headings in authenticated and public-shell pages:

```tsx
<PageHeader
  eyebrow={t("page.title")}          // small caps copper label
  subtitle={t("page.subtitle")}      // optional muted description
  action={<Button />}                // optional right-side element (badge, CTA)
/>
```

The `action` slot is for badges (pending count) or primary action buttons. For pages with a large `<h1>` below the eyebrow (like `JobBoardPage`), inline the eyebrow + rule pattern directly.

### CompanyName component

Use `<CompanyName>` wherever a company name is rendered in the UI — it is the canonical copper-accent treatment:

```tsx
import CompanyName from "@/components/ui/CompanyName";

<CompanyName name={row.company_profile.name} />
// optional className for layout (e.g. "truncate block")
<CompanyName name={row.company_profile.name} className="truncate block" />
```

`text-copper font-medium`, inherits surrounding text size. Never render company names as plain text in tables, cards, or detail views.

In email templates (`src/templates/email.py`) use the `_company(name)` helper — it produces the equivalent inline-style copper span.

### Button

```tsx
import Button from "@/components/ui/Button";

<Button variant="primary">Save</Button>                  // bg-copper → hover:bg-gold
<Button variant="ghost" onClick={onClose}>Cancel</Button> // white/20 border, white/60 text
<Button variant="danger" disabled={saving}>Delete</Button>
<Button variant="success">Approve</Button>               // success/15 bg

// Sizes: "sm" (px-3 py-1.5), "md" (default, px-4 py-2), "lg" (px-6 py-2.5)
// Extra layout classes go in className:
<Button variant="primary" className="flex-1">Submit</Button>
// All HTML button props (type, form, disabled, onClick) pass through
```

**Never write button Tailwind classes inline** — always use `<Button>`.

### Eyebrow

```tsx
import Eyebrow from "@/components/ui/Eyebrow";

<Eyebrow>Section title</Eyebrow>
<Eyebrow className="mb-3">With spacing</Eyebrow>
```

Renders a `<p>` styled `text-[10px] font-semibold uppercase tracking-widest text-copper`. Use for all section labels inside dialogs, cards, and form sections. **Never write the class string inline.**

### StatusBadge

```tsx
import StatusBadge from "@/components/ui/StatusBadge";

<StatusBadge label={STATUS_LABELS[status]} colorCls={STATUS_COLORS[status]} />
```

Color maps (`STATUS_COLORS`) stay domain-specific in the page or component that knows the domain. `StatusBadge` only handles the rendering.

### Field

Canonical form field wrapper. Tag switches between `<div>` (when `id` is
set, with explicit `htmlFor`) and `<label>` (implicit association).

```tsx
import Field from "@/components/ui/Field";

// Public / auth — explicit `id` mode (div + label htmlFor)
<Field label="Email" id="email" required error={fieldErrors.email}>
  <input id="email" ... />
</Field>

// Admin dialogs — implicit mode (label wraps input). `name` sets data-field
// for focusFirstError lookups; `full` spans 2 cols in a grid.
<Field label="Title" name="title" full required error={errors.title}>
  <input ... />
</Field>
```

**Never define a local `Field` component** — always import this one.

### Shared form styles

```ts
import { inputCls, textareaCls, selectCls } from "@/styles/forms";
```

These produce dark-themed inputs consistent with `bg-well`, copper focus ring, and white/85 text. Always import from here — never copy the class string.

### Shared utilities

```ts
import { formatDate, formatDateLong } from "@/utils/formatDate";
// formatDate  → "3 ינו׳ 2026"  (month: "short")
// formatDateLong → "3 ינואר 2026" (month: "long")

import { EMAIL_RE, MOBILE_RE, COMPANY_ID_RE } from "@/utils/validators";
// MOBILE_RE = strict Israeli 05XXXXXXXX — use everywhere, not loose patterns
```

**Never define these locally** — import from the shared utils.

---

## Patterns & Conventions

### Component size & co-location

ESLint enforces a **600-line hard limit** (`max-lines`, blank lines and comments excluded). Files approaching that limit must be split before they trip the error.

**Where to put extracted components:**

| Parent page / file | Co-located components folder |
|---|---|
| `pages/admin/AdminXxxPage.tsx` | `pages/admin/components/` |
| `pages/company/CompanyXxxPage.tsx` | `pages/company/components/` |
| `pages/candidate/CandidateXxxPage.tsx` | `pages/candidate/components/` |
| `pages/public/XxxPage.tsx` | `pages/public/components/` |
| `pages/RegisterPage.tsx` / `pages/LoginPage.tsx` | `pages/components/` |
| `components/dashboard/CandidateDashboard.tsx` | `components/dashboard/` (sibling files) |

**Rules for extracted components:**
- Extracted components receive state values + callbacks as typed props; the parent owns all state, data-fetching, and handlers.
- Utility functions (non-React helpers) that are shared across sibling files go in a `*Utils.ts` file (e.g. `jobBoardUtils.ts`, `dashboardUtils.ts`). Do **not** export utility functions from component files — `react-refresh/only-export-components` will error.
- Always use the global UI primitives instead of creating local copies: `@/components/ui/Field`, `@/components/ui/Button`, `@/components/ui/FilterPill`, `@/components/ui/AutoGrowTextarea`, `@/components/ui/InfiniteScrollFooter`, `@/components/ui/NoResults`, `@/components/ui/KebabButton`, `@/components/ui/StatusBadge`, `@/components/ui/Eyebrow`.

### Error handling
- Never pass raw backend `detail` strings to the UI — they may be English
- Map HTTP status codes to Hebrew `t()` keys:
  - `429` → `errors.tooManyAttempts`
  - `409` → `errors.emailExists` / `errors.alreadyApplied`
  - `404` → `errors.notFound` / `errors.unavailable`
  - `403` → `errors.accountInactive`
  - default → generic Hebrew error key

### Translations
All strings live in `frontend/src/locales/he.json`. Keys are namespaced by feature:
- `auth.login.*`, `auth.register.*`
- `landing.*`, `publicJobs.*`
- `admin.*`, `company.*`, `dashboard.*`

Write production-quality Hebrew — not literal translations. Prefer warm, direct phrasing.

### Rate limiting
The backend uses `slowapi` with:
- Login: 5 / minute
- Register: 3 / hour

The frontend handles `429` explicitly with Hebrew messages. The raw slowapi detail string (`"5 per 1 minute"`) is never shown.

### Authentication flow
- Access token in `localStorage`; refresh token in HttpOnly cookie set by backend
- `AuthContext` resolves initial state synchronously from `localStorage`, then verifies via `/api/auth/me` on mount
- `ProtectedRoute`, `AdminRoute`, `CompanyRoute`, `CandidateRoute` enforce role-based access
- Login redirects to `/dashboard`; unauthenticated access redirects to `/login`
- **Company activation:** admin approves → activation email → `/activate?token=` → 48h TTL.
- **Candidate activation (Sprint 11 / #605):** self-register at `/register-candidate` → activation email (2h TTL) → `/activate?token=` → `CandidateProfile` created + consent written from activation request's IP/UA.
- Unactivated logins return `401 detail=account_pending_activation` regardless of role; the login page surfaces a "resend activation" affordance for candidates that calls `POST /api/auth/candidate/resend-activation`.

### Logo loading
`Logo.tsx` renders `opacity-0` until the SVG `onLoad` fires, then fades to `opacity-1` (0.25s ease). This prevents the flash of broken-image placeholder on first load.

### Eager loading (avoiding N+1)
When a service flow accesses related rows (e.g. `Job.company.user`), load them in the original SELECT with `selectinload` at the call site:

```python
select(Job)
    .options(selectinload(Job.company).selectinload(CompanyProfile.user))
    .where(Job.id == job_id)
```

Prefer `selectinload` at the call site over `lazy="selectin"` on the model unless the relationship is *always* needed wherever the parent is loaded — relationship-level eager loading pollutes list endpoints and other paths that don't need the child rows. For ad-hoc one-shot joins where no SQLModel relationship exists (e.g. `ActivationToken` → `User`), a plain `.join(User, User.id == ActivationToken.company_user_id)` returning a tuple is fine.

---

## Adding a New Page

1. Create the page in the appropriate `pages/` subdirectory
2. Use `PageHeader` for the heading
3. Use `<Button>` for all action buttons — never inline button Tailwind classes
4. Use `<Eyebrow>` for section labels — never write the class string inline
5. Use `inputCls` / `textareaCls` from `@/styles/forms` for inputs
6. Use `Field` from `@/components/ui/Field` — pass `id` for explicit `htmlFor` mode, or omit for `<label>`-wrap mode
7. Use `formatDate` / `formatDateLong` from `@/utils/formatDate` — never define locally
8. Use only token-based Tailwind classes — no `bg-[#hex]` or inline style colors
9. Map all error states to `t()` keys in `he.json`
10. Register the route in `App.tsx` with the appropriate route guard

### Co-locating sub-components

When a page grows large, extract dialogs and helpers to a `components/` folder next to the page:

```
pages/admin/
├── AdminJobsPage.tsx          # orchestration only — state, handlers, layout
└── components/
    ├── JobDetailDialog.tsx
    ├── JobEditDialog.tsx
    └── JobFormHelpers.tsx      # shared helpers used by multiple dialogs
```

**Rule:** page files should stay under ~400 lines. If a component is used only within one page's subtree, co-locate it. If it's used across multiple pages, promote it to `components/ui/` or `components/admin/`.

---

## Running Locally

Dependencies are managed with **uv**. `pyproject.toml` declares direct deps, `uv.lock` pins the full resolved graph (commit both). Sync your venv with `uv sync` (adds default `dev` group) or `uv sync --frozen --group test` to match CI exactly. There is no `requirements.txt`.

```bash
# Backend
uv sync                          # one-time / after pulling
uv run uvicorn src.main:app --reload

# Frontend
cd frontend && npm run dev
```

The frontend proxies `/api/*` to `http://localhost:8000` (configured in `vite.config.ts`).

### Managing Python deps

- **Add a runtime dep**: `uv add <package>` (writes to `[project].dependencies`)
- **Add a test/dev dep**: `uv add --group test <package>` or `--group dev`
- **Upgrade**: `uv lock --upgrade-package <name>` then commit `uv.lock`
- **Refresh everything**: `uv lock --upgrade` (deliberate, separate PR)

CI uses `uv sync --frozen --group test`. The Dockerfile uses `uv sync --frozen --no-dev`. `--frozen` fails loudly if the lock is stale — always commit `uv.lock` after touching `pyproject.toml`.

---

## GitHub workflow conventions — MUST follow

This project has its own templates and naming conventions. **Always use them; do not fall back to generic GitHub defaults.**

### Branch names
Format: `<type>/<short-kebab-summary>`. Types observed in `git log`: `feat`, `fix`, `chore`, `docs`, `hotfix`, `feature`, `refactor`. Match an existing type rather than inventing one.

### Commit messages
**Conventional Commits**, with optional scope. Examples from `main`:
- `feat(auth): refresh tokens, account lockout, password rules`
- `fix(email): SMTP timeout + production config from SSM`
- `docs: refresh CLAUDE.md and docs/* to match current state`
- `chore: bump python-jose for security patches`

Do **not** add `Co-Authored-By:` trailers — they don't appear on commits in this repo.

### Pull requests
Title matches the commit message style (Conventional Commits). Body **must** follow `.github/pull_request_template.md`:

```
## Summary
Short description of the change.

## Why
What problem does this PR solve?

## Changes
-
-

## How to Test
Steps to verify the changes.

## Related Issue
Closes #
```

If there is no related issue, write `N/A` — don't omit the section. Don't add other top-level sections (no "Test plan", no "Generated with…" footers).

### Issues
Three templates exist in `.github/ISSUE_TEMPLATE/`: `bug_report.md`, `feature_request.md`, `task.md`. Pick the matching one and fill every section. Each template includes a `🎯 Milestone` selector — pick from the listed phases (Infrastructure / Company / Job / Candidate / Match / Frontend / Deployment).

---

## Linting — MUST run before every commit

**Always run both linters before committing. CI will fail if either fails.**

```bash
# Backend — ruff (lint + format check)
uv run ruff check .
uv run ruff format --check .

# Auto-fix format
uv run ruff format .

# Frontend — TypeScript + ESLint
cd frontend && npx tsc --noEmit && npm run lint
```

Common pitfalls:
- `E501` line too long (88 char limit) — wrap long strings with implicit concatenation
- `ruff format` must also pass (not just `ruff check`) — run `uv run ruff format .` to auto-fix
- ESLint `no-unused-expressions` — use `if/else` instead of ternary side-effects
- ESLint `react-hooks/set-state-in-effect` — don't call `setState` synchronously in `useEffect` body; use lazy `useState` initializer or a callback instead
- ESLint `max-lines` — error at 600 lines (blank/comment lines excluded). Extract JSX sections into co-located components per the "Component size & co-location" conventions above.
- ESLint `no-magic-numbers` — warn on unexplained numeric literals. Extract to a named constant. HTTP status codes (200, 404, 429, …) and small integers (0, 1, 2, 3) are pre-allowed.
- ESLint `react-refresh/only-export-components` — a file must not export both React components and plain values/functions. Move utility exports to a sibling `*Utils.ts` file.
