import logging
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import agency, auth, clients, inbox, intake, projects, workflows
from app.db import database_ready
from app.logging_config import configure_logging

configure_logging()
app = FastAPI(title="CREATIVE OS", version="0.1.0")
log = logging.getLogger("creativeos.api")


for router in (
    auth.router,
    agency.router,
    clients.router,
    inbox.router,
    intake.router,
    projects.router,
    workflows.router,
):
    app.include_router(router, prefix="/api/v1")


@app.exception_handler(StarletteHTTPException)
async def http_problem(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    codes = {
        400: "INVALID_REQUEST",
        401: "AUTHENTICATION_REQUIRED",
        403: "PERMISSION_DENIED",
        404: "RESOURCE_NOT_FOUND",
        409: "CONFLICT",
        429: "RATE_LIMIT_EXCEEDED",
        503: "SERVICE_UNAVAILABLE",
    }
    return JSONResponse(
        {
            "error": {"code": codes.get(exc.status_code, "HTTP_ERROR"), "message": str(exc.detail)},
            "meta": {"request_id": request.state.request_id},
        },
        status_code=exc.status_code,
    )


@app.exception_handler(RequestValidationError)
async def invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Validation errors can include the submitted password or invitation token.
    return JSONResponse(
        {
            "error": {"code": "VALIDATION_ERROR", "message": "Invalid request fields"},
            "meta": {"request_id": request.state.request_id},
        },
        status_code=422,
    )


@app.middleware("http")
async def log_request(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Request-ID"] = request_id
    log.info(
        "request",
        extra={
            "fields": {
                "request_id": request_id,
                "method": request.method,
                "route": getattr(request.scope.get("route"), "path", "unmatched"),
                "status": response.status_code,
            }
        },
    )
    return response


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready")
def ready() -> dict[str, str]:
    try:
        if database_ready():
            return {"status": "ready"}
    except SQLAlchemyError:
        log.warning("database_unavailable")
    raise HTTPException(status_code=503, detail="Database unavailable or migrations pending")
