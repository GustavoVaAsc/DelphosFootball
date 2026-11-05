"""RFC 9457 Problem Details schema for standardized API error responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProblemDetails(BaseModel):
    """RFC 9457 Problem Details object."""

    type: str = Field(default="about:blank", description="URI identifying the problem type")
    title: str = Field(description="Short human-readable summary of problem")
    status: int = Field(description="HTTP status code")
    detail: str = Field(description="Explanation specific to this occurrence")
    trace_id: str | None = Field(default=None, description="Optional tracing identifier")

