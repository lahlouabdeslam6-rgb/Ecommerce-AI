import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_permission, require_roles
from app.db.sqlite import get_sqlite_session
from app.models.user import User
from app.repositories.operations import OperationsRepository
from app.schemas.orchestrator import (
    AgentResult,
    OrchestratorHistoryItem,
    OrchestratorHistoryListResponse,
    OrchestratorRequest,
    OrchestratorResponse,
)
from app.services.orchestrator_service import OrchestratorService


router = APIRouter(prefix="/orchestrator", tags=["AI Orchestrator"])
logger = logging.getLogger("nutrifit.orchestrator.api")


@router.post("/execute", response_model=OrchestratorResponse)
async def execute(
    payload: OrchestratorRequest,
    user: Annotated[User, Depends(require_permission("products:read"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> OrchestratorResponse:
    try:
        service = OrchestratorService(session=session, user=user)
        result = await service.execute(payload)
    except HTTPException:
        raise
    except Exception:
        await session.rollback()
        logger.exception("Orchestrator execution failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI Orchestrator is temporarily unavailable",
        )

    # The orchestrator is proposal-only. A temporary audit storage problem must
    # never turn a valid, read-only AI answer into an HTTP 500 response.
    try:
        OperationsRepository(session).add_audit(
            actor_id=user.id,
            actor_role=user.role,
            action="ai.orchestrator.execute",
            entity_type="ai_orchestrator",
            details={
                "message": payload.message,
                **result.model_dump(mode="json"),
            },
        )
        await session.commit()
    except Exception:
        await session.rollback()
        logger.warning("Orchestrator audit could not be stored", exc_info=True)
    return result


@router.get("/history", response_model=OrchestratorHistoryListResponse)
async def history(
    _: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
) -> OrchestratorHistoryListResponse:
    rows, total = await OperationsRepository(session).list_orchestrator_runs(
        page,
        page_size,
    )
    items: list[OrchestratorHistoryItem] = []
    for item, actor_email in rows:
        try:
            details = json.loads(item.details or "{}")
        except (json.JSONDecodeError, TypeError):
            details = {}
        items.append(
            OrchestratorHistoryItem(
                id=item.id,
                actor_id=item.actor_id,
                actor_email=actor_email,
                actor_role=item.actor_role,
                message=str(details.get("message") or ""),
                detected_intent=str(
                    details.get("detected_intent") or "unknown"
                ),
                selected_agents=list(details.get("selected_agents") or []),
                results=[
                    AgentResult.model_validate(result)
                    for result in details.get("results") or []
                ],
                requires_confirmation=bool(
                    details.get("requires_confirmation")
                ),
                proposed_action=details.get("proposed_action"),
                created_at=item.created_at,
            )
        )
    return OrchestratorHistoryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )
