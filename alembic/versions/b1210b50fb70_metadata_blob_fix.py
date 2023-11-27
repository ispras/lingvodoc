
"""Metadata blob fix

Revision ID: b1210b50fb70
Revises: 2fd520393cc5
Create Date: 2023-11-25 03:23:07.621266

"""

# revision identifiers, used by Alembic.
revision = 'b1210b50fb70'
down_revision = '2fd520393cc5'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():

    op.execute('''

        update dictionary

        set
        additional_metadata =
          jsonb_set(
            additional_metadata,
            '{blobs}',
            '[{"client_id": 238, "object_id": 4},
              {"client_id": 238, "object_id": 3},
              {"client_id": 238, "object_id": 2}]')

        where
        additional_metadata -> 'blobs' =
          '[{"client_id": 238, "object_id": 3},
            {"client_id": 238, "object_id": 2},
            {"client_id": 238, "object_id": 1}]';

        update dictionary

        set
        additional_metadata =
          jsonb_set(
            additional_metadata,
            '{blobs}',
            '[{"client_id": 234, "object_id": 2},
              {"client_id": 234, "object_id": 3}]')

        where
        additional_metadata -> 'blobs' =
          '[{"client_id": 234, "object_id": 1},
            {"client_id": 234, "object_id": 2}]';

        update dictionary

        set
        additional_metadata =
          jsonb_set(
            additional_metadata,
            '{blobs}',
            '[{"client_id": 508, "object_id": 12}]')

        where
        additional_metadata -> 'blobs' =
          '[{"client_id": 508, "object_id": 11}]';

        update dictionary

        set
        additional_metadata =
          jsonb_set(
            additional_metadata,
            '{blobs}',
            '[{"client_id": 511, "object_id": 2},
              {"client_id": 518, "object_id": 2}]')

        where
        additional_metadata -> 'blobs' =
          '[{"client_id": 511, "object_id": 2},
            {"client_id": 518, "object_id": 1}]';

        update dictionary

        set
        additional_metadata =
          jsonb_set(
            additional_metadata,
            '{blobs}',
            '[{"client_id": 518, "object_id": 2}]')

        where
        additional_metadata -> 'blobs' =
          '[{"client_id": 518, "object_id": 1}]';

        ''')


def downgrade():

    pass

