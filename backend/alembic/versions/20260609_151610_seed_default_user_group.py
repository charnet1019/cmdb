"""seed default user group

Revision ID: 144036e4f912
Revises: c47f22a2faa6
Create Date: 2026-06-09 15:16:10.767622

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '144036e4f912'
down_revision: Union[str, None] = 'c47f22a2faa6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    now = sa.func.now()

    groups = sa.table('groups',
        sa.column('id', sa.Integer),
        sa.column('name', sa.String),
        sa.column('description', sa.Text),
        sa.column('is_default', sa.Boolean),
        sa.column('created_at', sa.DateTime),
        sa.column('updated_at', sa.DateTime),
    )
    user_groups = sa.table('user_groups',
        sa.column('user_id', sa.Integer),
        sa.column('group_id', sa.Integer),
        sa.column('created_at', sa.DateTime),
    )
    users = sa.table('users',
        sa.column('id', sa.Integer),
        sa.column('username', sa.String),
    )

    conn = op.get_bind()

    # Create default group if it doesn't exist
    existing = conn.execute(sa.select(groups).where(groups.c.is_default == True))
    if not existing.fetchone():
        conn.execute(groups.insert().values(
            name='默认用户组',
            description='系统默认用户组，所有新用户默认加入',
            is_default=True,
            created_at=now,
            updated_at=now,
        ))

    # Fetch the default group
    default_group = conn.execute(sa.select(groups).where(groups.c.is_default == True))
    default_row = default_group.fetchone()
    if not default_row:
        return
    default_group_id = default_row[0]

    # Ensure admin user is in the default group
    admin = conn.execute(sa.select(users).where(users.c.username == 'admin'))
    admin_row = admin.fetchone()
    if admin_row:
        admin_id = admin_row[0]
        already_member = conn.execute(
            sa.select(user_groups).where(
                user_groups.c.user_id == admin_id,
                user_groups.c.group_id == default_group_id,
            )
        )
        if not already_member.fetchone():
            conn.execute(user_groups.insert().values(
                user_id=admin_id,
                group_id=default_group_id,
                created_at=now,
            ))

    # Add all users without any group to the default group
    users_without_group = conn.execute(
        sa.select(users.c.id).where(
            ~sa.exists().where(
                user_groups.c.user_id == users.c.id,
            )
        )
    )
    for user_row in users_without_group:
        user_id = user_row[0]
        already_member = conn.execute(
            sa.select(user_groups).where(
                user_groups.c.user_id == user_id,
                user_groups.c.group_id == default_group_id,
            )
        )
        if not already_member.fetchone():
            conn.execute(user_groups.insert().values(
                user_id=user_id,
                group_id=default_group_id,
                created_at=now,
            ))


def downgrade() -> None:
    groups = sa.table('groups',
        sa.column('id', sa.Integer),
        sa.column('is_default', sa.Boolean),
    )
    user_groups = sa.table('user_groups',
        sa.column('group_id', sa.Integer),
    )

    conn = op.get_bind()
    default_group = conn.execute(sa.select(groups).where(groups.c.is_default == True))
    default_row = default_group.fetchone()
    if default_row:
        default_group_id = default_row[0]
        conn.execute(user_groups.delete().where(user_groups.c.group_id == default_group_id))
        conn.execute(groups.delete().where(groups.c.id == default_group_id))
