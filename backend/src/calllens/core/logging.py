"""Structured JSON logging setup and request correlation-ID middleware."""

import logging
import uuid
from typing import Any

from pythonjsonlogger.json import JsonFormatter
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

CORRELATION_ID_HEADER = "X-Correlation-ID"


def configure_logging(level: int = logging.INFO) -> None:
    """Configure the root logger to emit structured JSON.

    Args:
        level: The logging level to apply to the root logger.
    """
    handler = logging.StreamHandler()
    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Attach a correlation ID to every request and propagate it in response headers.

    The ID is taken from the incoming ``X-Correlation-ID`` header if present,
    otherwise a new UUID4 is generated.  The ID is injected into every log
    record emitted during the request via a custom record factory.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process request, adding correlation ID to logs and response headers.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            The HTTP response with the correlation ID header attached.
        """
        correlation_id = request.headers.get(CORRELATION_ID_HEADER) or str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        old_factory = logging.getLogRecordFactory()

        def record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
            record = old_factory(*args, **kwargs)
            record.__dict__["correlation_id"] = correlation_id
            return record

        logging.setLogRecordFactory(record_factory)

        try:
            response = await call_next(request)
        finally:
            logging.setLogRecordFactory(old_factory)

        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response
