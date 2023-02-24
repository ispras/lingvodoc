"""Revert entity field index

Revision ID: 442dd93eb35c
Revises: 3dd7fe2846e0
Create Date: 2022-08-07 14:42:03.794709

"""

# revision identifiers, used by Alembic.
revision = '442dd93eb35c'
down_revision = '3dd7fe2846e0'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():

    op.execute('''

        DROP INDEX entity_field_idx;

        ''')


def downgrade():

    op.execute('''

        CREATE INDEX entity_field_idx
          ON public.entity (field_client_id, field_object_id);

        ''')

