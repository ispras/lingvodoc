"""Valency EAF data

Revision ID: 47b1055a43d8
Revises: e5c45b904c17
Create Date: 2022-04-07 16:22:32.527275

"""

# revision identifiers, used by Alembic.
revision = '47b1055a43d8'
down_revision = 'e5c45b904c17'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():

    # We are assuming exclusive access to the DB, there are pretty significant schema changes.

    op.execute('''

        ALTER SEQUENCE valency_result_data_id_seq 
          RENAME TO valency_source_data_id_seq;

        ALTER TABLE valency_result_data
          RENAME CONSTRAINT valency_result_data_perspective_id_fkey TO valency_source_data_perspective_id_fkey;

        ALTER TABLE valency_result_data
          RENAME TO valency_source_data;

        ALTER TABLE valency_sentence_data
          RENAME COLUMN result_id TO source_id;

        ALTER TABLE valency_sentence_data
          RENAME CONSTRAINT valency_sentence_data_result_id_fkey TO valency_sentence_data_source_id_fkey;

        ALTER INDEX valency_result_data_perspective_id_index
          RENAME TO valency_source_data_perspective_id_index;

        ALTER INDEX valency_sentence_data_result_id_index
          RENAME TO valency_sentence_data_source_id_index;

        CREATE TABLE valency_parser_data (

          id BIGINT PRIMARY KEY REFERENCES valency_source_data(id),
          parser_result_client_id BIGINT NOT NULL,
          parser_result_object_id BIGINT NOT NULL,
          hash TEXT NOT NULL,

          CONSTRAINT valency_result_data_parser_result_id_fkey
            FOREIGN KEY (parser_result_client_id, parser_result_object_id)
              REFERENCES parserresult(client_id, object_id)

        );

        INSERT INTO valency_parser_data
        SELECT id, parser_result_client_id, parser_result_object_id, hash
        FROM valency_source_data;

        ALTER TABLE valency_source_data
          DROP COLUMN parser_result_client_id,
          DROP COLUMN parser_result_object_id,
          DROP COLUMN hash;

        CREATE TABLE valency_eaf_data (

          id BIGINT PRIMARY KEY REFERENCES valency_source_data(id),
          entity_client_id BIGINT NOT NULL,
          entity_object_id BIGINT NOT NULL,
          hash TEXT NOT NULL,

          CONSTRAINT valency_result_data_entity_id_fkey
            FOREIGN KEY (entity_client_id, entity_object_id)
              REFERENCES public.entity(client_id, object_id)

        );

    ''')


def downgrade():

    # Again, assuming exclusive access due to significant schema changes.

    op.execute('''

        DROP TABLE valency_eaf_data CASCADE;

        ALTER TABLE valency_source_data
          ADD COLUMN parser_result_client_id BIGINT,
          ADD COLUMN parser_result_object_id BIGINT,
          ADD COLUMN hash TEXT;

        UPDATE valency_source_data S
        SET
        parser_result_client_id = P.parser_result_client_id,
        parser_result_object_id = P.parser_result_object_id,
        hash = P.hash
        FROM valency_parser_data P
        WHERE S.id = P.id;

        ALTER TABLE valency_source_data

          ALTER COLUMN parser_result_client_id SET NOT NULL,
          ALTER COLUMN parser_result_object_id SET NOT NULL,
          ALTER COLUMN hash SET NOT NULL,

          ADD CONSTRAINT valency_result_data_parser_result_id_fkey
            FOREIGN KEY (parser_result_client_id, parser_result_object_id)
              REFERENCES parserresult(client_id, object_id);

        DROP TABLE valency_parser_data CASCADE;

        ALTER INDEX valency_sentence_data_source_id_index
          RENAME TO valency_sentence_data_result_id_index;

        ALTER INDEX valency_source_data_perspective_id_index
          RENAME TO valency_result_data_perspective_id_index;

        ALTER TABLE valency_sentence_data
          RENAME CONSTRAINT valency_sentence_data_source_id_fkey TO valency_sentence_data_result_id_fkey;

        ALTER TABLE valency_sentence_data
          RENAME COLUMN source_id TO result_id;

        ALTER TABLE valency_source_data
          RENAME TO valency_result_data;

        ALTER TABLE valency_result_data
          RENAME CONSTRAINT valency_source_data_perspective_id_fkey TO valency_result_data_perspective_id_fkey;

        ALTER SEQUENCE valency_source_data_id_seq
          RENAME TO valency_result_data_id_seq;

    ''')

