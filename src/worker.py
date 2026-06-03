"""SQS worker — polls the task queue and dispatches to registered task functions.

Entry point:
    python -m src.worker

Message format (JSON):
    {"task": "<registry_key>", ...kwargs}

The worker handles SIGTERM gracefully: it finishes the current batch then exits.
Visibility timeout matches the maximum task duration (300 s) so a task that is
still running when its visibility expires gets redelivered to the DLQ rather
than running twice.
"""

import asyncio
import base64
import json
import logging
import signal
import sys

import aioboto3

from src.core.infrastructure.config import settings
from src.core.tasks import TASK_REGISTRY

logger = logging.getLogger(__name__)

_VISIBILITY_TIMEOUT = 300  # seconds — must match job_timeout in infra config
_LONG_POLL_SECONDS = 20
_MAX_MESSAGES = 10


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","message":"%(message)s"}',
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def _deserialize_message(body: dict) -> tuple[str, dict]:
    """Extract task name and kwargs from the parsed SQS message body.

    Attachments are base64-encoded strings in transit; decode them back to
    bytes before passing to send_email_task.
    """
    task_name = body.pop("task")
    if "attachments" in body and body["attachments"]:
        body["attachments"] = [
            (name, base64.b64decode(data), mime)
            for name, data, mime in body["attachments"]
        ]
    return task_name, body


async def _process_message(raw_body: str) -> str:
    body = json.loads(raw_body)
    task_name, kwargs = _deserialize_message(body)

    fn = TASK_REGISTRY.get(task_name)
    if fn is None:
        logger.warning("unknown_task", extra={"task": task_name})
        return task_name

    logger.info("task_start", extra={"task": task_name})
    await fn(**kwargs)
    logger.info("task_done", extra={"task": task_name})
    return task_name


async def run(stop_event: asyncio.Event) -> None:
    if not settings.sqs_queue_url:
        logger.error("SQS_QUEUE_URL is not configured — worker cannot start")
        sys.exit(1)

    logger.info("worker_starting", extra={"queue": settings.sqs_queue_url})

    session = aioboto3.Session()
    async with session.client("sqs", region_name=settings.aws_region) as sqs:
        while not stop_event.is_set():
            resp = await sqs.receive_message(
                QueueUrl=settings.sqs_queue_url,
                MaxNumberOfMessages=_MAX_MESSAGES,
                WaitTimeSeconds=_LONG_POLL_SECONDS,
                VisibilityTimeout=_VISIBILITY_TIMEOUT,
            )
            for msg in resp.get("Messages", []):
                receipt = msg["ReceiptHandle"]
                try:
                    task_name = await _process_message(msg["Body"])
                    await sqs.delete_message(
                        QueueUrl=settings.sqs_queue_url,
                        ReceiptHandle=receipt,
                    )
                    delay = settings.email_send_delay_seconds
                    if task_name == "send_email" and delay > 0:
                        await asyncio.sleep(delay)
                except Exception:
                    logger.exception(
                        "task_failed",
                        extra={"receipt_prefix": receipt[:20]},
                    )
                    # Do NOT delete — SQS redelivers after visibility timeout.
                    # The DLQ captures messages that exceed max receive count.

    logger.info("worker_stopped")


def main() -> None:
    _configure_logging()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    stop_event = asyncio.Event()

    def _handle_sigterm(*_) -> None:
        logger.info("worker_shutting_down")
        loop.call_soon_threadsafe(stop_event.set)

    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigterm)

    try:
        loop.run_until_complete(run(stop_event))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
