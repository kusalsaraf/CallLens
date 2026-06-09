"""Idempotent seeding of the default support/collections topic taxonomy."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from calllens.db.models.topic import Topic
from calllens.db.session import get_session_factory

logger = logging.getLogger(__name__)

_TAXONOMY: list[dict[str, str | list[str]]] = [
    {
        "name": "Billing Dispute",
        "slug": "billing_dispute",
        "keywords": ["billing", "charge", "overcharge", "invoice", "bill", "fee", "charged"],
    },
    {
        "name": "Cancellation / Churn Risk",
        "slug": "cancellation_churn_risk",
        "keywords": ["cancel", "cancellation", "churn", "terminate", "close account", "leave"],
    },
    {
        "name": "Technical Issue",
        "slug": "technical_issue",
        "keywords": ["technical", "error", "bug", "not working", "broken", "outage", "crash"],
    },
    {
        "name": "Refund Request",
        "slug": "refund_request",
        "keywords": ["refund", "money back", "reimburse", "reimbursement", "credit"],
    },
    {
        "name": "Payment Arrangement",
        "slug": "payment_arrangement",
        "keywords": ["payment plan", "arrangement", "installment", "pay later", "extension"],
    },
    {
        "name": "Complaint Escalation",
        "slug": "complaint_escalation",
        "keywords": ["complaint", "escalate", "supervisor", "manager", "unacceptable"],
    },
    {
        "name": "Account Access",
        "slug": "account_access",
        "keywords": ["password", "login", "locked out", "access", "reset", "two-factor", "verify"],
    },
    {
        "name": "Product Question",
        "slug": "product_question",
        "keywords": ["feature", "how to", "product", "upgrade", "downgrade", "plan", "pricing"],
    },
    {
        "name": "Delivery / Shipping",
        "slug": "delivery_shipping",
        "keywords": ["delivery", "shipping", "tracking", "package", "shipment", "dispatch"],
    },
    {
        "name": "Retention / Save",
        "slug": "retention_save",
        "keywords": ["retention", "save", "loyalty", "discount", "offer", "keep"],
    },
]


async def seed_topics(db: AsyncSession) -> list[Topic]:
    """Seed the default topic taxonomy if topics are missing.

    Idempotent: checks by slug — existing topics are left untouched, new slugs
    are inserted. Running twice produces no duplicate rows.

    Args:
        db: An open async database session.

    Returns:
        The full list of Topic rows (both pre-existing and newly created).
    """
    existing = (await db.execute(select(Topic))).scalars().all()
    slug_set = {t.slug for t in existing}

    created = 0
    for entry in _TAXONOMY:
        if entry["slug"] in slug_set:
            continue
        topic = Topic(
            name=str(entry["name"]),
            slug=str(entry["slug"]),
            keywords=list(entry["keywords"]),
        )
        db.add(topic)
        created += 1

    if created:
        await db.commit()
        logger.info("Seeded %d new topics", created)
        existing = list((await db.execute(select(Topic))).scalars().all())
    else:
        logger.info("Topic taxonomy already seeded — no new rows")

    return list(existing)


async def _main() -> None:
    """Run topic seed as a standalone async task."""
    factory = get_session_factory()
    async with factory() as db:
        topics = await seed_topics(db)
        logger.info("Topic taxonomy: %d topics", len(topics))


if __name__ == "__main__":
    import asyncio

    asyncio.run(_main())
