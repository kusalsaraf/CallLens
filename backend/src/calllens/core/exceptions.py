"""Custom exception hierarchy and FastAPI exception handlers."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base class for all application errors.

    Args:
        message: Human-readable error description.
        status_code: HTTP status code to return to the client.
        error_code: Machine-readable error identifier.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "internal_error",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, status_code=404, error_code="not_found")


class ValidationError(AppError):
    """Raised when input data fails business-level validation."""

    def __init__(self, message: str = "Validation failed") -> None:
        super().__init__(message, status_code=422, error_code="validation_error")


class AuthenticationError(AppError):
    """Raised when a request cannot be authenticated."""

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message, status_code=401, error_code="authentication_required")


class AuthorizationError(AppError):
    """Raised when a request is authenticated but not authorized."""

    def __init__(self, message: str = "Permission denied") -> None:
        super().__init__(message, status_code=403, error_code="permission_denied")


class ConflictError(AppError):
    """Raised when an operation conflicts with existing state."""

    def __init__(self, message: str = "Conflict") -> None:
        super().__init__(message, status_code=409, error_code="conflict")


def _error_body(error_code: str, message: str) -> dict[str, str]:
    return {"error": error_code, "message": message}


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI app instance.

    Args:
        app: The FastAPI application to register handlers on.
    """

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.error_code, exc.message),
        )

    @app.exception_handler(Exception)
    async def handle_unhandled(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=_error_body("internal_error", "An unexpected error occurred."),
        )
