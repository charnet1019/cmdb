"""Shared pagination helpers."""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.schemas import PaginationMeta


async def get_pagination_meta(db: AsyncSession, query: Select, page: int, limit: int) -> PaginationMeta:
    """Count rows matching `query` (before offset/limit) and build PaginationMeta.

    Apply `.offset()`/`.limit()`/`.order_by()` on `query` separately for the
    actual page fetch — this only computes the total count and page metadata.
    """
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()
    return PaginationMeta(
        total=total,
        page=page,
        limit=limit,
        pages=(total + limit - 1) // limit,
    )
