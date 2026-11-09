"""Root.sh daemon — FastAPI + uvicorn.

Exposes ``POST /score`` which receives ``(user_request, proposed_action,
source)`` and returns ``allow`` / ``confirm`` / ``block`` with a risk score and
reason.  Every call is logged to SQLite.  Malformed input, an invalid source, a
missing model or any other failure produces a block response.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, ConfigDict

from rootguard import __version__
from rootguard.config import MAX_TEXT_LENGTH
from rootguard.model.infer import ScoringError, score_command

app = FastAPI(title="Root.sh Defense Layer", version=__version__)

DECISION_EXIT_STATUS: dict[str, int] = {"allow": 200, "confirm": 200, "block": 403}


class ScoreRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    user_request: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    proposed_action: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    source: str = Field(max_length=32)

    @field_validator("source")
    @classmethod
    def _validate_source(cls, value: str) -> str:
        from rootguard.db.models import SOURCES

        if value not in SOURCES:
            raise ValueError(f"invalid source {value!r}; expected one of {', '.join(SOURCES)}")
        return value

    @field_validator("user_request", "proposed_action")
    @classmethod
    def _validate_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value


class ScoreResponse(BaseModel):
    decision: str
    risk_score: float
    reason: str
    features: dict[str, Any]
    intent_class: str
    action_class: str


@app.post("/score", response_model=ScoreResponse)
async def score(request: ScoreRequest) -> ScoreResponse:
    """Score one proposed action and return the authorization decision."""
    try:
        result = score_command(
            user_request=request.user_request,
            proposed_action=request.proposed_action,
            source=request.source,
            save_to_db=True,
        )
    except ScoringError as exc:
        return ScoreResponse(
            decision="block",
            risk_score=1.0,
            reason=f"blocked: {exc}",
            features={},
            intent_class="other",
            action_class="other",
        )

    return ScoreResponse(
        decision=result["decision"],
        risk_score=result["risk_score"],
        reason=result["reason"],
        features=result["features"],
        intent_class=result["intent_class"],
        action_class=result["action_class"],
    )


def _block_response(reason: str) -> ScoreResponse:
    return ScoreResponse(
        decision="block",
        risk_score=1.0,
        reason=reason,
        features={},
        intent_class="other",
        action_class="other",
    )


@app.exception_handler(HTTPException)
async def _http_exception_handler(_request: Any, exc: HTTPException) -> Any:
    # Default deny: turn client errors into block responses instead of
    # leaking details.
    return JSONResponse(
        status_code=200,
        content=_block_response(f"blocked: {exc.detail}").model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(_request: Request, exc: RequestValidationError) -> Any:
    # Default deny: malformed input must be blocked, not returned as 422.
    details = "; ".join(str(err.get("msg", "")) for err in exc.errors())
    return JSONResponse(
        status_code=200,
        content=_block_response(f"blocked: malformed input ({details})").model_dump(),
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "Root.sh Defense Layer", "version": __version__}
