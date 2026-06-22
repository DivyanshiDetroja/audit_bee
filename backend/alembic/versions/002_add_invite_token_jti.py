"""add invite_token_jti to clients

Revision ID: 002
Revises: 001
Create Date: 2026-06-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Opaque JTI stored on the client record; nulled after invite is redeemed.
    op.add_column("clients", sa.Column("invite_token_jti", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("clients", "invite_token_jti")
