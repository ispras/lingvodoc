"""Unstructured data

Revision ID: 01d944425263
Revises: d7a6389ac968
Create Date: 2021-01-06 23:44:05.468937

"""

# revision identifiers, used by Alembic.
revision = '01d944425263'
down_revision = 'd7a6389ac968'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():

    op.execute('''

        CREATE TABLE public.unstructured_data (
          id TEXT primary key,
          client_id BIGINT,
          created_at TIMESTAMP without time zone NOT NULL,
          additional_metadata JSONB,
          data JSONB
        );

        ''')


def downgrade():

    op.execute('''

        DROP TABLE public.unstructured_data;

        ''')

