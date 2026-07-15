"""Helpers to remove dangling references from Authorization.target_ids
when the underlying asset/organization they point to is deleted."""
from typing import Iterable, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Authorization


async def cleanup_authorization_targets(db: AsyncSession, target_type: str, removed_ids: Iterable[str]) -> None:
    """Remove `removed_ids` from every Authorization.target_ids of the given target_type.

    Authorization rows left with an empty target_ids list are deleted outright,
    since an authorization with no targets grants nothing.
    Does not commit — caller controls the transaction boundary.
    """
    removed_ids = {str(rid) for rid in removed_ids}
    if not removed_ids:
        return

    result = await db.execute(
        select(Authorization).where(Authorization.target_type == target_type)
    )
    auths = result.scalars().all()

    for auth in auths:
        current_ids: List[str] = list(auth.target_ids or [])
        remaining = [tid for tid in current_ids if str(tid) not in removed_ids]
        if len(remaining) == len(current_ids):
            continue
        if remaining:
            auth.target_ids = remaining
        else:
            await db.delete(auth)
