"""Adverb data
Revision ID: 9a82fe69ceee
Revises: be06149acd44
Create Date: 2023-03-22 21:47:10.366535
"""

# revision identifiers, used by Alembic.
revision = '9a82fe69ceee'
down_revision = 'be06149acd44'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():

    op.execute('''
        CREATE TABLE adverb_instance_data (
          id BIGSERIAL PRIMARY KEY,
          sentence_id BIGINT NOT NULL REFERENCES valency_sentence_data(id),
          index INT NOT NULL,
          adverb_lex TEXT NOT NULL,
          case_str TEXT NOT NULL
        );
        CREATE TABLE adverb_annotation_data (
          instance_id BIGINT NOT NULL REFERENCES adverb_instance_data(id),
          user_id BIGINT NOT NULL REFERENCES public.user(id),
          accepted BOOLEAN DEFAULT null,
          PRIMARY KEY (instance_id, user_id)
        );
        CREATE INDEX adverb_instance_data_sentence_id_index
          ON adverb_instance_data (sentence_id);
        CREATE INDEX adverb_instance_data_adverb_lex_index
          ON adverb_instance_data (adverb_lex);
        CREATE INDEX adverb_instance_data_case_str_index
          ON adverb_instance_data (case_str);
        ''')


def downgrade():

    op.execute('''
        DROP INDEX adverb_instance_data_sentence_id_index CASCADE;
        DROP INDEX adverb_instance_data_adverb_lex_index CASCADE;
        DROP INDEX adverb_instance_data_case_str_index CASCADE;
        DROP TABLE adverb_instance_data CASCADE;
        DROP TABLE adverb_annotation_data CASCADE;
        ''')
