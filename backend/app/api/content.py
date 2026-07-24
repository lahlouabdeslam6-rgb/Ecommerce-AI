from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.sqlite import get_sqlite_session
from app.models.user import User
from app.repositories.operations import OperationsRepository
from app.schemas.content import (
    ContentGenerateRequest,
    ContentListResponse,
    ContentResponse,
    ContentUpdate,
)
from app.services.content_agent import ContentAgentService
from app.services.safety_agent import SafetyAgentService


router = APIRouter(tags=["AI Content"])


@router.get("/content/published", response_model=ContentResponse | None)
async def published_content(
    content_type: Annotated[
        str,
        Query(
            pattern=(
                r"^(homepage_hero|promotion|category|faq|social_post)$"
            )
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> ContentResponse | None:
    return await ContentAgentService(session).latest_published(content_type)


@router.get("/admin/ai/content", response_model=ContentListResponse)
async def list_content(
    _: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    content_type: Annotated[str | None, Query(max_length=40)] = None,
    content_status: Annotated[str | None, Query(max_length=20)] = None,
) -> ContentListResponse:
    return await ContentAgentService(session).list(
        page=page,
        page_size=page_size,
        content_type=content_type,
        content_status=content_status,
    )


@router.post("/admin/ai/content/generate", response_model=ContentResponse)
async def generate_content(
    data: ContentGenerateRequest,
    admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> ContentResponse:
    result = await ContentAgentService(session).generate(
        data,
        created_by=admin.id,
    )
    OperationsRepository(session).add_audit(
        actor_id=admin.id,
        actor_role=admin.role,
        action="ai.content.generated",
        entity_type="ai_content",
        entity_id=result.id,
        details={
            "content_type": result.content_type,
            "topic": result.topic,
            "model": result.model,
        },
    )
    await session.commit()
    return result


@router.patch("/admin/ai/content/{content_id}", response_model=ContentResponse)
async def update_content(
    content_id: int,
    data: ContentUpdate,
    admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> ContentResponse:
    result = await ContentAgentService(session).update(content_id, data)
    OperationsRepository(session).add_audit(
        actor_id=admin.id,
        actor_role=admin.role,
        action="ai.content.updated",
        entity_type="ai_content",
        entity_id=content_id,
        details={"fields": sorted(data.model_fields_set)},
    )
    await session.commit()
    return result


@router.post(
    "/admin/ai/content/{content_id}/publish",
    response_model=ContentResponse,
)
async def publish_content(
    content_id: int,
    admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> ContentResponse:
    service = ContentAgentService(session)
    content = await service.get(content_id)
    safety_text = "\n".join(
        value
        for value in (
            content.title,
            content.subtitle,
            content.body,
            content.cta_label,
            " ".join(content.hashtags),
        )
        if value
    )
    await SafetyAgentService(session).enforce(
        safety_text,
        source_type="content",
        source_id=content_id,
        action="content.publish",
        actor_id=admin.id,
        actor_role=admin.role,
    )
    result = await service.publish(content_id)
    OperationsRepository(session).add_audit(
        actor_id=admin.id,
        actor_role=admin.role,
        action="ai.content.published",
        entity_type="ai_content",
        entity_id=content_id,
        details={"content_type": result.content_type},
    )
    await session.commit()
    return result


@router.post(
    "/admin/ai/content/{content_id}/archive",
    response_model=ContentResponse,
)
async def archive_content(
    content_id: int,
    admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> ContentResponse:
    result = await ContentAgentService(session).archive(content_id)
    OperationsRepository(session).add_audit(
        actor_id=admin.id,
        actor_role=admin.role,
        action="ai.content.archived",
        entity_type="ai_content",
        entity_id=content_id,
        details={"content_type": result.content_type},
    )
    await session.commit()
    return result
