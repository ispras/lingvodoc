"""Valency data

Revision ID: e5c45b904c17
Revises: d88f47d819e0
Create Date: 2022-03-10 17:08:44.525326

"""

# revision identifiers, used by Alembic.
revision = 'e5c45b904c17'
down_revision = 'd88f47d819e0'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():

    op.execute('''

        ALTER TABLE parserresult ADD PRIMARY KEY (client_id, object_id);

        CREATE TABLE valency_result_data (

          id BIGSERIAL PRIMARY KEY,
          perspective_client_id BIGINT NOT NULL,
          perspective_object_id BIGINT NOT NULL,
          parser_result_client_id BIGINT NOT NULL,
          parser_result_object_id BIGINT NOT NULL,
          hash TEXT NOT NULL,

          CONSTRAINT valency_result_data_perspective_id_fkey
            FOREIGN KEY (perspective_client_id, perspective_object_id)
              REFERENCES dictionaryperspective(client_id, object_id),

          CONSTRAINT valency_result_data_parser_result_id_fkey
            FOREIGN KEY (parser_result_client_id, parser_result_object_id)
              REFERENCES parserresult(client_id, object_id)

        );

        CREATE TABLE valency_sentence_data (

          id BIGSERIAL PRIMARY KEY,
          result_id BIGINT NOT NULL REFERENCES valency_result_data(id),
          data JSONB,
          instance_count INT NOT NULL

        );

        CREATE TABLE valency_instance_data (

          id BIGSERIAL PRIMARY KEY,
          sentence_id BIGINT NOT NULL REFERENCES valency_sentence_data(id),
          index INT NOT NULL,
          verb_lex TEXT NOT NULL,
          case_str TEXT NOT NULL

        );

        CREATE TABLE valency_annotation_data (

          instance_id BIGINT NOT NULL REFERENCES valency_instance_data(id),
          user_id BIGINT NOT NULL REFERENCES public.user(id),
          accepted BOOLEAN DEFAULT null,

          PRIMARY KEY (instance_id, user_id)

        );

        CREATE INDEX valency_result_data_perspective_id_index
          ON valency_result_data (perspective_client_id, perspective_object_id);

        CREATE INDEX valency_sentence_data_result_id_index
          ON valency_sentence_data (result_id);

        CREATE INDEX valency_instance_data_sentence_id_index
          ON valency_instance_data (sentence_id);

        CREATE INDEX valency_instance_data_verb_lex_index
          ON valency_instance_data (verb_lex);

        CREATE INDEX valency_instance_data_case_str_index
          ON valency_instance_data (case_str);

        ''')


def downgrade():

    op.execute('''

        DROP INDEX valency_result_data_perspective_id_index CASCADE;
        DROP INDEX valency_sentence_data_result_id_index CASCADE;

        DROP INDEX valency_instance_data_sentence_id_index CASCADE;
        DROP INDEX valency_instance_data_verb_lex_index CASCADE;
        DROP INDEX valency_instance_data_case_ord_index CASCADE;

        DROP TABLE valency_result_data CASCADE;
        DROP TABLE valency_sentence_data CASCADE;
        DROP TABLE valency_instance_data CASCADE;
        DROP TABLE valency_annotation_data CASCADE;

        ALTER TABLE parserresult DROP CONSTRAINT parserresult_pkey;

        ''')

