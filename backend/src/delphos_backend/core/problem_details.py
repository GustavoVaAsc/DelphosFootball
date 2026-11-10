"""RFC 9457 problem-details handlers for the FastAPI application.

Input: HTTPException and RequestValidationError raised by the API.
Output: JSONResponse bodies served with the application/problem+json media type.
Responsibility: formats every error path of the API as RFC 9457 problem
details, so no response falls back to FastAPI's default `{"detail": [...]}`
JSON body.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from delphos_backend.schemas.errors import ProblemDetails

HTTP_TITLES: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "Bad Request",
    status.HTTP_404_NOT_FOUND: "Not Found",
    status.HTTP_422_UNPROCESSABLE_CONTENT: "Unprocessable Content",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "Internal Server Error",
    status.HTTP_503_SERVICE_UNAVAILABLE: "Service Unavailable",
}


async def problem_details_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Format exceptions as RFC 9457 problem details."""
    title = HTTP_TITLES.get(exc.status_code, "Error")
    problem = ProblemDetails(
        type="about:blank",
        title=title,
        status=exc.status_code,
        detail=str(exc.detail),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=problem.model_dump(),
        media_type="application/problem+json",
    )


async def validation_problem_details_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Format request-validation failures as RFC 9457 problem details."""
    problem = ProblemDetails(
        type="about:blank",
        title=HTTP_TITLES[status.HTTP_422_UNPROCESSABLE_CONTENT],
        status=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=_format_validation_errors(exc.errors()),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=problem.model_dump(),
        media_type="application/problem+json",
    )


def _format_validation_errors(errors: list[dict[str, Any]]) -> str:
    """Summarise pydantic validation errors as a single readable line."""
    parts = []
    for error in errors:
        location = ".".join(str(part) for part in error.get("loc", ()))
        message = error.get("msg", "invalid value")
        parts.append(f"{location or 'body'}: {message}")
    return "Request validation failed: " + "; ".join(parts)


def register_problem_details(app: FastAPI) -> None:
    """Register the RFC 9457 exception handlers on the application."""
    app.add_exception_handler(HTTPException, problem_details_handler)
    app.add_exception_handler(RequestValidationError, validation_problem_details_handler)
