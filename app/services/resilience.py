import asyncio
import importlib
import logging
import os
import random
from time import perf_counter
from typing import Any, Awaitable, Callable, TypeVar

from app.services.ai_service import GeminiServiceError

logger = logging.getLogger(__name__)
Result = TypeVar("Result")


class CircuitOpenError(GeminiServiceError):
    pass


def _transient_error(exc: Exception) -> bool:
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError, ConnectionError, OSError)):
        return True
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    return code in {408, 425, 429, 500, 502, 503, 504}


async def call_gemini_resilient(
    *,
    clinic_id: int,
    gateway: str,
    operation: Callable[[], Awaitable[Result]],
    timeout_seconds: float = 8.0,
    max_attempts: int = 2,
) -> tuple[Result, int]:
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise GeminiServiceError("REDIS_URL is required for Gemini circuit-breaker protection")
    try:
        redis_async = importlib.import_module("redis.asyncio")
        redis_client: Any = redis_async.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    except Exception as exc:
        raise GeminiServiceError("Redis circuit-breaker client is unavailable") from exc

    safe_gateway = "".join(character for character in gateway.lower() if character.isalnum() or character in "-_")[:64]
    circuit_key = f"gfi:llm:circuit:{clinic_id}:{safe_gateway}"
    failures_key = f"gfi:llm:failures:{clinic_id}:{safe_gateway}"
    started = perf_counter()
    attempts = max(1, min(max_attempts, 3))
    timeout = max(0.5, min(timeout_seconds, 30.0))

    try:
        if await redis_client.exists(circuit_key):
            raise CircuitOpenError("Gemini circuit is open; retry after cooldown")

        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                result = await asyncio.wait_for(operation(), timeout=timeout)
                await redis_client.delete(failures_key, circuit_key)
                return result, round((perf_counter() - started) * 1000)
            except Exception as exc:
                last_error = exc
                script = (
                    "local n=redis.call('INCR', KEYS[1]); "
                    "if n==1 then redis.call('EXPIRE', KEYS[1], ARGV[1]); end; "
                    "return n"
                )
                try:
                    failures = int(await redis_client.eval(script, 1, failures_key, 60))
                    if failures >= 5:
                        await redis_client.set(circuit_key, "open", ex=30)
                except Exception as breaker_exc:
                    logger.exception("Unable to record Gemini breaker state for clinic %s", clinic_id)
                    raise GeminiServiceError("Gemini circuit-breaker state is unavailable") from breaker_exc

                retryable = _transient_error(exc) and attempt + 1 < attempts
                if not retryable:
                    break
                delay = min(0.25 * (2 ** attempt), 2.0)
                await asyncio.sleep(delay + random.random() * delay * 0.25)

        raise GeminiServiceError("Gemini request failed after bounded retries") from last_error
    finally:
        try:
            await redis_client.aclose()
        except Exception:
            logger.exception("Failed to close Redis circuit-breaker client")