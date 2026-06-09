"""Idempotent seeding of the default Support QA rubric."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from calllens.db.models.rubric import Rubric, RubricDimension
from calllens.db.session import get_session_factory
from calllens.services.seed import seed_defaults

logger = logging.getLogger(__name__)

_DEFAULT_RUBRIC_NAME = "Support QA"

_DIMENSIONS: list[dict[str, Any]] = [
    {
        "key": "sentiment_empathy",
        "name": "Sentiment & Empathy",
        "weight": 0.25,
        "kind": "score",
        "config": None,
    },
    {
        "key": "script_adherence",
        "name": "Script Adherence",
        "weight": 0.20,
        "kind": "score",
        "config": None,
    },
    {
        "key": "compliance",
        "name": "Compliance",
        "weight": 0.20,
        "kind": "score",
        "config": {"required_phrases": ["I understand", "I apologize", "Is there anything else"]},
    },
    {
        "key": "objection_handling",
        "name": "Objection Handling",
        "weight": 0.15,
        "kind": "score",
        "config": None,
    },
    {
        "key": "talk_listen",
        "name": "Talk/Listen Ratio",
        "weight": 0.10,
        "kind": "ratio",
        "config": None,
    },
    {
        "key": "outcome",
        "name": "Call Outcome",
        "weight": 0.10,
        "kind": "bool",
        "config": None,
    },
]


async def seed_default_rubric(db: AsyncSession) -> Rubric:
    """Seed the default Support QA rubric if it does not already exist.

    Creates a Rubric named "Support QA" with is_default=True and the 6
    standard dimensions. Running this function twice must NOT duplicate rows —
    it checks for existence before inserting.

    Also ensures the default Team and Agent exist by calling seed_defaults
    before creating the rubric.

    Args:
        db: An open async database session.

    Returns:
        The (possibly newly created) Rubric row.
    """
    await seed_defaults(db)

    result = await db.execute(select(Rubric).where(Rubric.name == _DEFAULT_RUBRIC_NAME))
    rubric = result.scalar_one_or_none()

    if rubric is not None:
        logger.info(
            "Default rubric already exists, skipping seed",
            extra={"rubric_id": str(rubric.id), "rubric_name": rubric.name},
        )
        return rubric

    rubric = Rubric(name=_DEFAULT_RUBRIC_NAME, is_default=True, is_active=True)
    db.add(rubric)
    await db.flush()

    for dim_data in _DIMENSIONS:
        dimension = RubricDimension(
            rubric_id=rubric.id,
            key=dim_data["key"],
            name=dim_data["name"],
            weight=dim_data["weight"],
            kind=dim_data["kind"],
            config=dim_data["config"],
        )
        db.add(dimension)

    await db.commit()
    logger.info(
        "Seeded default rubric with dimensions",
        extra={
            "rubric_id": str(rubric.id),
            "rubric_name": rubric.name,
            "dimensions": len(_DIMENSIONS),
        },
    )
    return rubric


async def _main() -> None:
    """Run the rubric seed as a standalone async task."""
    factory = get_session_factory()
    async with factory() as db:
        rubric = await seed_default_rubric(db)
        logger.info(
            "Rubric seeded", extra={"rubric_id": str(rubric.id), "rubric_name": rubric.name}
        )


def _main_sync() -> None:
    """Synchronous entrypoint for the calllens-seed-rubric console script."""
    import asyncio

    asyncio.run(_main())


if __name__ == "__main__":
    import asyncio

    asyncio.run(_main())
