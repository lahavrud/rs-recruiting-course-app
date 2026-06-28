# Auth Rules

## Token model
- Access token: 10min TTL, stored in `localStorage`
- Refresh token: 7-day TTL, HttpOnly cookie, **single-use** — deleted on use, logout, or password reset
- No blacklist — short access TTL is the post-logout tolerance window
- Refresh rotation: delete consumed token, issue new pair → prevents replay attacks

## Account lockout
5 failed login attempts → locked for 15 minutes. Tracked on `User.locked_until` column.

## Rate limiting (slowapi)
- Login: 5 / minute · Register: 3 / hour
- Never surface the raw slowapi detail string (`"5 per 1 minute"`) in the UI — map to Hebrew error key

## Activation flows

**Company:** admin approves invite → activation email → `/activate?token=` → 48h TTL → user activated + company profile linked

**Candidate:** `/register-candidate` → activation email (2h TTL) → `/activate?token=` → `CandidateProfile` created + consent (timestamp, policy version, IP, UA) written from the activation request, not the registration request

- Unactivated login (any role): `401 detail=account_pending_activation`
- Login page surfaces "resend activation" affordance for candidates: `POST /api/auth/candidate/resend-activation`

## AuthContext invariant
Resolves initial state synchronously from `localStorage`, then verifies via `/api/auth/me` on mount. Never block render waiting for the verify call — the sync read is the optimistic state.

## What lives where
- Session logic: `libs/shared/rs_shared/services/auth/session.py`
- Registration: `libs/shared/rs_shared/services/auth/registration.py` (company) + `.../candidate_registration.py`
- Activation: `libs/shared/rs_shared/services/auth/activation.py`
- Password reset: `libs/shared/rs_shared/services/auth/password_reset.py`
- Auth API routers: `services/api/rs_api/api/auth/`; web infra (auth deps, slowapi limiter): `services/api/rs_api/infrastructure/`
- Route guards: `frontend/src/components/guards/`
