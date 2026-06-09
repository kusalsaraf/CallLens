"""Rubric CRUD service — create, read, update, activate, clone, delete."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from calllens.db.models.audit import AuditLog
from calllens.db.models.call import Call
from calllens.db.models.rubric import Rubric, RubricDimension
from calllens.db.models.scoring import CallScore
from calllens.schemas.rubric import DimensionIn, RubricCreateIn, RubricUpdateIn

logger = logging.getLogger(__name__)


async def list_rubrics(db: AsyncSession) -> list[Rubric]:
    """Return all rubrics ordered by creation date (newest first).

    Args:
        db: Active database session.

    Returns:
        List of Rubric ORM instances.
    """
    result = await db.execute(select(Rubric).order_by(Rubric.created_at.desc()))
    return list(result.scalars().all())


async def get_rubric(db: AsyncSession, rubric_id: uuid.UUID) -> Rubric | None:
    """Return a rubric with its dimensions eagerly loaded.

    Args:
        db: Active database session.
        rubric_id: UUID of the rubric.

    Returns:
        Rubric with dimensions, or None if not found.
    """
    result = await db.execute(
        select(Rubric).where(Rubric.id == rubric_id).options(selectinload(Rubric.dimensions))
    )
    return result.scalar_one_or_none()


async def get_active_rubric(db: AsyncSession) -> Rubric | None:
    """Return the currently active rubric with dimensions.

    Args:
        db: Active database session.

    Returns:
        The active Rubric, or None.
    """
    result = await db.execute(
        select(Rubric).where(Rubric.is_active.is_(True)).options(selectinload(Rubric.dimensions))
    )
    return result.scalar_one_or_none()


def _build_dimensions(rubric_id: uuid.UUID, dims: list[DimensionIn]) -> list[RubricDimension]:
    """Build RubricDimension ORM objects from validated input.

    Args:
        rubric_id: Parent rubric UUID.
        dims: Validated dimension inputs.

    Returns:
        List of RubricDimension objects.
    """
    return [
        RubricDimension(
            rubric_id=rubric_id,
            key=d.key,
            name=d.name,
            weight=d.weight,
            kind=d.kind.value,
            config=d.config,
        )
        for d in dims
    ]


async def create_rubric(
    db: AsyncSession,
    data: RubricCreateIn,
    actor: str = "system",
) -> Rubric:
    """Create a new rubric with dimensions (inactive by default).

    Args:
        db: Active database session.
        data: Validated rubric creation input.
        actor: Audit actor string.

    Returns:
        The newly created Rubric (with dimensions).
    """
    rubric = Rubric(
        name=data.name,
        description=data.description,
        is_default=False,
        is_active=False,
    )
    db.add(rubric)
    await db.flush()

    for dim_orm in _build_dimensions(rubric.id, data.dimensions):
        db.add(dim_orm)
    await db.flush()

    db.add(
        AuditLog(
            actor=actor,
            action="rubric_create",
            entity="rubric",
            entity_id=rubric.id,
            payload={"name": rubric.name},
        )
    )
    await db.commit()

    return await get_rubric(db, rubric.id)  # type: ignore[return-value]


async def update_rubric(
    db: AsyncSession,
    rubric_id: uuid.UUID,
    data: RubricUpdateIn,
    actor: str = "system",
) -> Rubric | None:
    """Update a rubric's name/description and optionally replace dimensions.

    Args:
        db: Active database session.
        rubric_id: UUID of the rubric to update.
        data: Validated update input.
        actor: Audit actor string.

    Returns:
        Updated Rubric, or None if not found.
    """
    rubric = await get_rubric(db, rubric_id)
    if rubric is None:
        return None

    if data.name is not None:
        rubric.name = data.name
    if data.description is not None:
        rubric.description = data.description

    if data.dimensions is not None:
        # Delete existing dimensions via SQL to avoid stale identity map issues
        from sqlalchemy import delete as sa_delete

        await db.execute(sa_delete(RubricDimension).where(RubricDimension.rubric_id == rubric_id))
        await db.flush()

        for dim_orm in _build_dimensions(rubric.id, data.dimensions):
            db.add(dim_orm)
        await db.flush()

    db.add(
        AuditLog(
            actor=actor,
            action="rubric_update",
            entity="rubric",
            entity_id=rubric.id,
            payload={"name": rubric.name},
        )
    )
    await db.commit()

    # Re-fetch with a fresh query to pick up the new dimensions
    result = await db.execute(
        select(Rubric)
        .where(Rubric.id == rubric_id)
        .options(selectinload(Rubric.dimensions))
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def activate_rubric(
    db: AsyncSession,
    rubric_id: uuid.UUID,
    actor: str = "system",
) -> Rubric | None:
    """Activate a rubric and deactivate all others (exactly one active).

    Args:
        db: Active database session.
        rubric_id: UUID of the rubric to activate.
        actor: Audit actor string.

    Returns:
        The activated Rubric, or None if not found.
    """
    rubric = await get_rubric(db, rubric_id)
    if rubric is None:
        return None

    await db.execute(update(Rubric).values(is_active=False))
    rubric.is_active = True
    await db.flush()

    db.add(
        AuditLog(
            actor=actor,
            action="rubric_activate",
            entity="rubric",
            entity_id=rubric.id,
            payload={"name": rubric.name},
        )
    )
    await db.commit()

    return await get_rubric(db, rubric.id)


async def clone_rubric(
    db: AsyncSession,
    rubric_id: uuid.UUID,
    actor: str = "system",
) -> Rubric | None:
    """Duplicate a rubric + dimensions as a new inactive draft.

    Args:
        db: Active database session.
        rubric_id: UUID of the source rubric.
        actor: Audit actor string.

    Returns:
        The cloned Rubric, or None if source not found.
    """
    source = await get_rubric(db, rubric_id)
    if source is None:
        return None

    clone = Rubric(
        name=f"{source.name} (copy)",
        description=source.description,
        is_default=False,
        is_active=False,
    )
    db.add(clone)
    await db.flush()

    for dim in source.dimensions:
        db.add(
            RubricDimension(
                rubric_id=clone.id,
                key=dim.key,
                name=dim.name,
                weight=dim.weight,
                kind=dim.kind,
                config=dim.config,
            )
        )
    await db.flush()

    db.add(
        AuditLog(
            actor=actor,
            action="rubric_clone",
            entity="rubric",
            entity_id=clone.id,
            payload={"source_id": str(rubric_id), "name": clone.name},
        )
    )
    await db.commit()

    return await get_rubric(db, clone.id)


async def delete_rubric(
    db: AsyncSession,
    rubric_id: uuid.UUID,
    actor: str = "system",
) -> tuple[bool, str | None]:
    """Delete a rubric if it is not active and not referenced by calls.

    Args:
        db: Active database session.
        rubric_id: UUID of the rubric to delete.
        actor: Audit actor string.

    Returns:
        (True, None) on success, or (False, reason) if blocked.
    """
    rubric = await get_rubric(db, rubric_id)
    if rubric is None:
        return False, "Rubric not found"

    if rubric.is_active:
        return False, "Cannot delete the active rubric"

    has_calls = (await db.execute(select(exists().where(Call.rubric_id == rubric_id)))).scalar()
    if has_calls:
        return False, "Cannot delete a rubric referenced by existing calls"

    # Check if any dimension is referenced by a CallScore
    dim_ids = [d.id for d in rubric.dimensions]
    if dim_ids:
        has_scores = (
            await db.execute(select(exists().where(CallScore.dimension_id.in_(dim_ids))))
        ).scalar()
        if has_scores:
            return False, "Cannot delete a rubric referenced by existing calls"

    db.add(
        AuditLog(
            actor=actor,
            action="rubric_delete",
            entity="rubric",
            entity_id=rubric_id,
            payload={"name": rubric.name},
        )
    )
    await db.delete(rubric)
    await db.commit()
    return True, None
