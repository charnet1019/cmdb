"""
Preferences API - User column configuration
"""
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models import User, UserPreference

router = APIRouter(prefix="/preferences", tags=["preferences"])


class ColumnConfigRequest(BaseModel):
    column_visibility: Optional[dict] = None
    column_order: Optional[list] = None
    version: Optional[int] = None


@router.get("/columns/{category}")
async def get_column_config(
    category: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get column configuration for a specific category"""
    result = await db.execute(
        select(UserPreference).where(
            UserPreference.user_id == current_user.id,
            UserPreference.category == category,
        )
    )
    pref = result.scalar_one_or_none()

    if pref is None:
        return {"code": 0, "data": {}}

    return {
        "code": 0,
        "data": {
            "column_visibility": pref.column_visibility,
            "column_order": pref.column_order,
            "version": pref.version,
        },
    }


@router.put("/columns/{category}")
async def update_column_config(
    category: str,
    data: ColumnConfigRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Upsert column configuration for a specific category"""
    result = await db.execute(
        select(UserPreference).where(
            UserPreference.user_id == current_user.id,
            UserPreference.category == category,
        )
    )
    pref = result.scalar_one_or_none()

    if pref is None:
        pref = UserPreference(
            user_id=current_user.id,
            category=category,
            column_visibility=data.column_visibility,
            column_order=data.column_order,
            version=data.version or 1,
        )
        db.add(pref)
    else:
        if data.column_visibility is not None:
            pref.column_visibility = data.column_visibility
        if data.column_order is not None:
            pref.column_order = data.column_order
        pref.version = data.version if data.version is not None else pref.version

    await db.commit()
    await db.refresh(pref)

    return {
        "code": 0,
        "data": {
            "column_visibility": pref.column_visibility,
            "column_order": pref.column_order,
            "version": pref.version,
        },
    }
