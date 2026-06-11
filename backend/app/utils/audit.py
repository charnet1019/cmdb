"""Shared operation audit logging"""
from typing import Optional, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import OperationLog


async def log_operation(
    db: AsyncSession,
    user_id: int,
    action: str,
    resource_type: str,
    resource_id: int,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    status: str = "success",
):
    """Log an operation to the OperationLog table"""
    entry = OperationLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        status=status,
    )
    db.add(entry)
    await db.commit()
