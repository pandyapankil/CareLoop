"""CareLoop — Structured logging service."""

import structlog
import logging
import sys
from datetime import datetime, timezone

logging.basicConfig(
    format="%(message)s",
    stream=sys.stdout,
    level=logging.INFO,
)

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)


def get_logger(name: str = "careloop"):
    return structlog.get_logger(name)


async def log_event(
    event_type: str,
    patient_id: str = None,
    user_id: str = None,
    **kwargs,
):
    log = get_logger()
    log.info(
        event_type,
        patient_id=patient_id,
        user_id=user_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        **kwargs,
    )


async def log_glm_call(
    call_type: str,
    prompt_length: int,
    response_length: int,
    thinking: str = None,
    duration_ms: float = None,
    error: str = None,
):
    log = get_logger()
    log.info(
        f"glm_{call_type}",
        prompt_tokens=prompt_length,
        response_tokens=response_length,
        thinking=thinking[:500] if thinking else None,
        duration_ms=duration_ms,
        error=error,
    )


async def log_error(error_type: str, error_message: str, **context):
    log = get_logger()
    log.error(
        error_type,
        error_message=error_message,
        **context,
    )
