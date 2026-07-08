# Candidate Data Retention — Runbook

The 12-month candidate retention purge: what it does, how to verify it ran, how to investigate when it didn't, and how to extend it.

---

## What it is

A nightly background job that deletes candidate data past the 12-month retention window mandated by our privacy policy.

- **Schedule:** 03:00 UTC nightly — an **EventBridge Scheduler** rule
  (`<queue>-nightly-purge`, `cron(0 3 * * ? *)`) puts `{"task": "purge_expired_candidates"}`
  onto the task **SQS** queue.
- **Runs in:** the `worker` Deployment (an EKS pod) — the same SQS consumer that
  handles every other task.
- **Defined in:** `libs/shared/rs_shared/core/tasks.py::purge_expired_candidate_data_task`
- **Eligibility logic:** `libs/shared/rs_shared/services/admin/_candidates_purge.py::purge_expired_candidates`

---

## Eligibility rule

A candidate is purged **only if every one of their applications** satisfies all three conditions:

1. Linked `Job.status == CLOSED`
2. `Job.updated_at < now - 365 days`
3. `Application.status != HIRED`

If even one application fails any condition, the candidate is preserved — companies may still need that data for payroll or dispute resolution. New candidates with zero applications are also preserved (no expiry has started).

The query is in `purge_expired_candidates`; it is the **single source of truth** for who gets deleted. Any change to retention policy goes there.

---

## What gets deleted, in order

For each eligible candidate:

1. The resume file in storage — via the storage abstraction (`storage_s3` in the cluster). Best-effort: failures are logged and ignored so a partial storage outage cannot block compliance deletions.
2. All `Application` rows where `candidate_id` matches.
3. The `CandidateProfile` row itself.
4. An audit log line: `INFO retention.purge candidate_id=<id>`.

All DB writes happen inside one transaction (`transactional(session)`); a failure mid-batch rolls back cleanly. Because SQS is at-least-once, the task is idempotent — a redelivered message simply finds nothing left to purge.

---

## Observability

### Audit log

Every deletion emits one structured log line — ID only, no PII — and the wrapper logs a summary:

```
INFO  retention.purge candidate_id=42
INFO  purge_complete count=3
```

These are the auditor evidence trail. The worker's stdout is shipped by the **Alloy DaemonSet** into **Loki**; browse it in Grafana (in-cluster kube-prometheus-stack).

### Metrics (OpenTelemetry → Prometheus)

The task wrapper records two OTel metrics (attribute `environment`), scraped into Prometheus by the kube-prometheus-stack:

| Metric | Type | Meaning |
|---|---|---|
| `purged_candidates` | Counter | Candidates removed per run |
| `last_purge_ran_at` | Gauge | Unix timestamp of the last successful run |

`last_purge_ran_at` is the liveness signal: alert in Prometheus/Grafana when
`time() - last_purge_ran_at > 26h` (the cron runs every 24h, so a stale gauge means
the worker isn't draining the purge message).

---

## Verifying it ran

```bash
# 1. Audit + summary lines in the last 24h (Grafana → Explore → Loki), e.g. LogQL:
#    {app="worker"} |= "purge_complete"
#    {app="worker"} |= "retention.purge candidate_id"

# 2. Liveness gauge is fresh (Grafana → Explore → Prometheus):
#    time() - max(last_purge_ran_at)      # should be < ~90000 (26h)

# 3. Purge volume over time:
#    increase(purged_candidates[7d])
```

---

## Investigating when it didn't run

Decision tree when `last_purge_ran_at` goes stale:

```
last_purge_ran_at stale (> 26h)
│
├── Worker pod healthy? (kubectl -n <env> get pods -l app=worker)
│   ├── No  → check `kubectl describe pod` / `kubectl logs` for CrashLoop / OOM
│   └── Yes ↓
│
├── Message stuck / failing? (check the SQS DLQ depth)
│   ├── DLQ > 0 → the task raised repeatedly; pull a DLQ message and read the
│   │             worker logs for the traceback (Loki: {app="worker"} |= "purge")
│   └── DLQ empty ↓
│
├── Did the scheduler fire? (EventBridge Scheduler `<queue>-nightly-purge`
│   last-run / the queue's ReceiveMessage metrics)
│   ├── No  → scheduler disabled or IAM (scheduler role → sqs:SendMessage) regressed
│   └── Yes ↓
│
└── Message enqueued but never processed → worker not polling this queue
    (check SQS_QUEUE_URL in the env Secret); escalate and run a manual purge.
```

---

## Manual one-off purge

If you need to run the purge outside the cron schedule (e.g. a compliance request to expedite a deletion), send the same message the scheduler sends, or run it in a worker pod:

```bash
# Option A — enqueue the task (worker picks it up):
aws sqs send-message --queue-url "$SQS_QUEUE_URL" \
  --message-body '{"task": "purge_expired_candidates"}'

# Option B — run directly inside a worker pod:
kubectl -n <env> exec -it deploy/worker -- python -c "
import asyncio
from rs_shared.core.infrastructure.database import async_session
from rs_shared.core.infrastructure.transactions import transactional
from rs_shared.services.admin.candidates import purge_expired_candidates

async def run():
    async with async_session() as s:
        async with transactional(s):
            n = await purge_expired_candidates(s)
    print(f'purged {n}')

asyncio.run(run())
"
```

Option B bypasses the task wrapper, so it won't move the `last_purge_ran_at` gauge — capture the `purged` count and the `retention.purge candidate_id=` log lines for the audit trail.

---

## What's intentionally not here

- **No dry-run mode.** Eligibility is a pure query; the audit log already proves what would have been deleted.
- **No batch limit.** The eligible set is small (the long tail of inactive candidates). If volume ever grows past tens of thousands per night, add `LIMIT` + repeat-until-empty.
- **No alarm for "the cron ran but deleted zero rows when it shouldn't have."** That's a correctness bug in `purge_expired_candidates`, not a runtime failure — covered by tests, not metrics.

---

## Related

- Service logic: `libs/shared/rs_shared/services/admin/_candidates_purge.py`
- Task wrapper: `libs/shared/rs_shared/core/tasks.py`
- Schedule: `rs-recruiting-course-infra` → `modules/task-queue` (`aws_scheduler_schedule.nightly_purge`)
- Tests: `tests/core/test_tasks.py`
