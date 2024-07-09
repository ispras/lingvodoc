"""add_hash_adverb
Revision ID: 483f9330348c
Revises: 9a82fe69ceee
Create Date: 2023-04-03 17:07:49.155801
"""

# revision identifiers, used by Alembic.
revision = '483f9330348c'
down_revision = '9a82fe69ceee'
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
