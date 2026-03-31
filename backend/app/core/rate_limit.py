from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, Response, status
from redis.asyncio import Redis

from backend.app.core.config import get_settings


@dataclass(frozen=True)
class RateLimitPolicy:
    bucket: str
    limit: int
    window_seconds: int


def _resolve_client_id(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


async def _consume_request(
    *,
    policy: RateLimitPolicy,
    request: Request,
    response: Response,
) -> None:
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    key = f"rate-limit:{policy.bucket}:{_resolve_client_id(request)}"
    try:
        current = int(await redis.incr(key))
        ttl = await redis.ttl(key)
        if current == 1 or ttl < 0:
            await redis.expire(key, policy.window_seconds)
            ttl = policy.window_seconds
    finally:
        await redis.aclose()

    remaining = max(policy.limit - current, 0)
    response.headers["X-RateLimit-Limit"] = str(policy.limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Window"] = str(policy.window_seconds)

    if current > policy.limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(max(ttl, 1))},
        )


def rate_limit(policy: RateLimitPolicy):
    async def _check(
        request: Request,
        response: Response,
    ) -> None:
        await _consume_request(policy=policy, request=request, response=response)

    return Depends(_check)
