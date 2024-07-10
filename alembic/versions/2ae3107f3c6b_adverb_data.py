"""adverb_data

Revision ID: 2ae3107f3c6b
Revises: 707b6ebc663f
Create Date: 2024-07-10 13:08:57.178607

"""

# revision identifiers, used by Alembic.
revision = '2ae3107f3c6b'
down_revision = '707b6ebc663f'
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
