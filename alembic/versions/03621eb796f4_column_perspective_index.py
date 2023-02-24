"""Column perspective index

Revision ID: 03621eb796f4
Revises: bb5539c93f29
Create Date: 2022-06-13 06:27:56.451358

"""

# revision identifiers, used by Alembic.
revision = '03621eb796f4'
down_revision = 'bb5539c93f29'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():

    op.execute('''

        CREATE INDEX dictionaryperspectivetofield_parent_idx
          ON dictionaryperspectivetofield (parent_client_id, parent_object_id);

        ''')


def downgrade():

    op.execute('''

        DROP INDEX dictionaryperspectivetofield_parent_idx;

        ''')

