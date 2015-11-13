"""additional metadata on perspectives and dictionaries

Revision ID: 34c4a3c687b
Revises: 28894fa7718
Create Date: 2015-11-13 13:53:15.258799

"""

# revision identifiers, used by Alembic.
revision = '34c4a3c687b'
down_revision = '28894fa7718'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('dictionaryperspective', sa.Column('additional_metadata', sa.UnicodeText(), nullable=True))
    op.add_column('dictionary', sa.Column('additional_metadata', sa.UnicodeText(), nullable=True))
    pass


def downgrade():
    op.drop_column('dictionary', 'additional_metadata')
    op.drop_column('dictionaryperspective', 'additional_metadata')
    pass
