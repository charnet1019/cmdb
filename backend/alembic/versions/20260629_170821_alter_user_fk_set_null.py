"""alter_user_fk_set_null

Revision ID: 01e6ac10cbf0
Revises: 20260612_auth_target_ids
Create Date: 2026-06-29 17:08:21.685457

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '01e6ac10cbf0'
down_revision: Union[str, None] = '20260612_auth_target_ids'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# FK constraints to alter: (table, column, old_name, new_name)
_FK_ALTER = [
    ("login_logs", "user_id", "login_logs_user_id_fkey", "fk_login_logs_user_id"),
    ("operation_logs", "user_id", "operation_logs_user_id_fkey", "fk_operation_logs_user_id"),
    ("password_change_logs", "user_id", "password_change_logs_user_id_fkey", "fk_password_change_logs_user_id"),
    ("password_change_logs", "changed_by", "password_change_logs_changed_by_fkey", "fk_password_change_logs_changed_by"),
    ("assets", "created_by_id", "fk_assets_created_by", "fk_assets_created_by"),
    ("assets", "owner_id", "fk_assets_owner_id", "fk_assets_owner_id"),
    ("authorizations", "created_by", "authorizations_created_by_fkey", "fk_authorizations_created_by"),
]

SET_NULL_SQL = 'ALTER TABLE {table} DROP CONSTRAINT {old_name}, ADD CONSTRAINT {new_name} FOREIGN KEY ({column}) REFERENCES users(id) ON DELETE SET NULL'
NO_ACTION_SQL = 'ALTER TABLE {table} DROP CONSTRAINT {new_name}, ADD CONSTRAINT {old_name} FOREIGN KEY ({column}) REFERENCES users(id)'


def upgrade() -> None:
    for table, column, old_name, new_name in _FK_ALTER:
        op.execute(SET_NULL_SQL.format(table=table, old_name=old_name, new_name=new_name, column=column))


def downgrade() -> None:
    for table, column, old_name, new_name in _FK_ALTER:
        op.execute(NO_ACTION_SQL.format(table=table, old_name=old_name, new_name=new_name, column=column))