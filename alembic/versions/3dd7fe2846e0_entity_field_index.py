"""Entity field index

Revision ID: 3dd7fe2846e0
Revises: 03621eb796f4
Create Date: 2022-06-18 11:39:44.347280

"""

# revision identifiers, used by Alembic.
revision = '3dd7fe2846e0'
down_revision = '03621eb796f4'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():

    op.execute('''

        CREATE INDEX entity_field_idx
          ON public.entity (field_client_id, field_object_id);

        ''')


def downgrade():

    op.execute('''

        DROP INDEX entity_field_idx;

        ''')

