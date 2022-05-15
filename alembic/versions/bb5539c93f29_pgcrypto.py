"""pgcrypto

Revision ID: bb5539c93f29
Revises: 59160a667fe1
Create Date: 2022-05-15 08:33:43.300580

"""

# revision identifiers, used by Alembic.
revision = 'bb5539c93f29'
down_revision = '59160a667fe1'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():

    op.execute('''

        CREATE EXTENSION IF NOT EXISTS pgcrypto;

    ''')


def downgrade():

    op.execute('''

        DROP EXTENSION IF EXISTS pgcrypto;

    ''')

