"""Create objecttoc metadata

Revision ID: 2b852140e36e
Revises: b939aa2120fa
Create Date: 2018-10-07 17:55:01.523450

"""

# revision identifiers, used by Alembic.
revision = '2b852140e36e'
down_revision = 'b939aa2120fa'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.types import Text, String
from sqlalchemy.dialects import postgresql


def upgrade():
    op.add_column('objecttoc', sa.Column('additional_metadata', postgresql.JSONB(astext_type=Text()), nullable=True))
    pass


def downgrade():
    pass
