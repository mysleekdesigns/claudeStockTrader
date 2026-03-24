"""Global exception handler middleware for FastAPI."""

from __future__ import annotations

import logging
import time

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class ExceptionHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        try:
            response = await call_next(request)
            elapsed = time.monotonic() - start
            logger.debug(
                "%s %s completed in %.3fs with status %d",
                request.method,
                request.url.path,
                elapsed,
                response.status_code,
            )
            return response
        except Exception:
            elapsed = time.monotonic() - start
            logger.exception(
                "Unhandled exception on %s %s after %.3fs",
                request.method,
                request.url.path,
                elapsed,
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )
