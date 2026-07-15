"""Shared name-formatting helpers for authorization target display."""
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset, Organization


def truncate_names(names: List[str], limit: int = 3) -> str:
    """Join up to `limit` names with ', ', appending '等N个' if there are more."""
    if len(names) <= limit:
        return ", ".join(names)
    return ", ".join(names[:limit]) + f" 等{len(names)}个"


def build_org_name_path(org: Organization, id_to_name: Dict[int, str]) -> str:
    """Resolve an organization's ID path (e.g. "7/12/13") to a name path
    (e.g. "Default/开发部/数据库") using a preloaded id→name map."""
    path_ids = org.path.split("/") if org.path else []
    names = []
    for pid in path_ids:
        try:
            names.append(id_to_name[int(pid)])
        except (KeyError, ValueError):
            break
    return "/".join(names) if names else org.name


async def resolve_target_names(db: AsyncSession, target_type: str, target_ids: Optional[List[str]]) -> str:
    """Resolve an authorization's target_ids to a display string, truncated to 3 names."""
    target_ids = target_ids or []
    if target_type == "asset":
        result = await db.execute(select(Asset.name).where(Asset.id.in_(target_ids)))
        names = [row[0] for row in result.all()]
        return truncate_names(names) if names else str(target_ids)
    else:
        names = []
        if "__all__" in target_ids:
            names.append("Default")
        org_ids = [int(tid) for tid in target_ids if str(tid).isdigit()]
        if org_ids:
            result = await db.execute(select(Organization.name).where(Organization.id.in_(org_ids)))
            names.extend(row[0] for row in result.all())
        return truncate_names(names) if names else str(target_ids)
