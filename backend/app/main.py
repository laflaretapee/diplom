from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import get_settings
from backend.app.core.logging import configure_logging
from backend.app.modules.analytics.router import router as analytics_router
from backend.app.modules.auth.router import router as auth_router
from backend.app.modules.customers.router import router as customers_router
from backend.app.modules.documents.router import router as documents_router
from backend.app.modules.franchisee.router import router as franchisee_router
from backend.app.modules.inbound.router import router as inbound_router
from backend.app.modules.kanban.router import router as kanban_router
from backend.app.modules.notifications.router import router as notifications_router
from backend.app.modules.orders.router import router as orders_router
from backend.app.modules.points.router import router as points_router
from backend.app.modules.realtime.router import router as realtime_router
from backend.app.modules.shop.router import router as shop_router
from backend.app.modules.telegram_bot.router import router as telegram_bot_router
from backend.app.modules.users.router import router as users_router
from backend.app.modules.warehouse.router import router as warehouse_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.app.modules.telegram_bot.router import setup_webhook
    await setup_webhook()
    yield


def create_application() -> FastAPI:
    configure_logging()
    app = FastAPI(
        lifespan=lifespan,
        title=settings.app_name,
        version="0.1.0",
        description=(
            "Джейсан: modular FastAPI backend for auth, orders, warehouse, "
            "franchisee onboarding, notifications and analytics."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-CSRF-Token",
            "X-Requested-With",
        ],
        expose_headers=[
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Window",
            "Retry-After",
        ],
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if settings.cookie_secure:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains; preload",
            )
        return response

    @app.get("/health", tags=["system"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(users_router, prefix=settings.api_prefix)
    app.include_router(orders_router, prefix=settings.api_prefix)
    app.include_router(points_router, prefix=settings.api_prefix)
    app.include_router(customers_router, prefix=settings.api_prefix)
    app.include_router(warehouse_router, prefix=settings.api_prefix)
    app.include_router(franchisee_router, prefix=settings.api_prefix)
    app.include_router(documents_router, prefix=settings.api_prefix)
    app.include_router(kanban_router, prefix=settings.api_prefix)
    app.include_router(notifications_router, prefix=settings.api_prefix)
    app.include_router(analytics_router, prefix=settings.api_prefix)
    app.include_router(inbound_router, prefix=settings.api_prefix)
    app.include_router(shop_router, prefix=settings.api_prefix)
    app.include_router(telegram_bot_router, prefix=settings.api_prefix)
    app.include_router(realtime_router, prefix=settings.api_prefix)
    return app


app = create_application()
