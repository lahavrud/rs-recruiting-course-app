# Redis Failure Policy

Redis backs three security-critical surfaces in this application.
This document records the deliberate policy for each surface when Redis is unreachable.

## Policy table

| Surface | Function | On Redis failure | Rationale |
|---|---|---|---|
| JWT blacklist read | `is_access_token_blacklisted` | **Fail-closed** — raises `RedisUnavailableError` → HTTP 503 | A logged-out token staying valid is a security regression; better to reject all authenticated requests than to silently re-admit revoked sessions |
| JWT blacklist write | `blacklist_access_token` | **Fail-closed** — raises `RedisUnavailableError` → HTTP 503 | Logging-out successfully while the JTI is not blacklisted creates a false sense of security |
| Brute-force lockout check | `_check_lockout` | **Fail-open** — logs structured error, allows login | Locking out all users during a Redis blip is an availability regression worse than the brief loss of brute-force protection |
| Brute-force attempt recording | `_record_failed_attempt` | **Fail-open** — logs structured error, counter not incremented | Same rationale as lockout check; TTL-based expiry is the safety net |
| Brute-force counter clear | `_clear_failed_attempts` | **Fail-open** — logs structured error | Best-effort; keys expire naturally via TTL |
| Invite token generate | `generate_invite_token` | **Fail-closed** — exception propagates → HTTP 500 | Admin cannot issue invites without Redis; loud failure is correct |
| Invite token validate | `validate_invite_token` | **Fail-closed** — exception propagates → HTTP 500 | Cannot allow registration with an unverifiable token |
| Invite token consume / revoke | `consume_invite_token`, `revoke_invite_token` | **Fail-open** — swallowed silently | Registration already committed; TTL on the Redis key is the expiry safety net |

## Observable signals

Every fail-open path emits a structured log line with a stable key so CloudWatch / #231 alerting can trigger on it:

```
logger.error("redis_unavailable", extra={"surface": "<surface-name>", ...})
```

Surfaces:
- `blacklist_read` — JWT blacklist check
- `blacklist_write` — JWT blacklist write (logout)
- `lockout_check` — brute-force lockout read
- `record_failed_attempt` — brute-force counter increment
- `clear_failed_attempts` — brute-force counter clear

## Health endpoint

`GET /health` pings Redis and reports status in the response:

```json
{"status": "ok",       "environment": "production", "redis": "ok"}
{"status": "degraded", "environment": "production", "redis": "unavailable"}
```

HTTP 200 is returned in both cases so uptime monitors don't page on a Redis blip; the `status: degraded` field is what operators should alert on.
