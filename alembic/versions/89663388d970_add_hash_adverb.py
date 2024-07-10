"""add_hash_adverb

Revision ID: 89663388d970
Revises: 2ae3107f3c6b
Create Date: 2024-07-10 13:09:14.235377

"""

# revision identifiers, used by Alembic.
revision = '89663388d970'
down_revision = '2ae3107f3c6b'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute('''
        ALTER TABLE valency_parser_data
          ADD hash_adverb TEXT;
        UPDATE valency_parser_data
          SET hash_adverb = ''
          WHERE hash_adverb IS NULL;
        ALTER TABLE valency_parser_data
          ALTER COLUMN hash_adverb SET NOT NULL;
    ''')

def downgrade():
    op.execute('''
        ALTER TABLE valency_parser_data
          DROP COLUMN hash_adverb;
    ''')
