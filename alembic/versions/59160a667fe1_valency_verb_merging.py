"""Valency verb merging

Revision ID: 59160a667fe1
Revises: 47b1055a43d8
Create Date: 2022-05-12 02:57:28.258373

"""

# revision identifiers, used by Alembic.
revision = '59160a667fe1'
down_revision = '47b1055a43d8'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():

    op.execute('''

        CREATE SEQUENCE valency_merge_id_seq;

        CREATE TABLE valency_merge_data (

          perspective_client_id BIGINT NOT NULL,
          perspective_object_id BIGINT NOT NULL,
          verb_lex TEXT NOT NULL,
          merge_id BIGINT NOT NULL,

          PRIMARY KEY (
            perspective_client_id, perspective_object_id, verb_lex),

          CONSTRAINT valency_merge_data_perspective_id_fkey
            FOREIGN KEY (perspective_client_id, perspective_object_id)
              REFERENCES dictionaryperspective(client_id, object_id)

        );

    ''')


def downgrade():

    op.execute('''

        DROP TABLE valency_merge_data;

        DROP SEQUENCE valency_merge_id_seq;

    ''')

