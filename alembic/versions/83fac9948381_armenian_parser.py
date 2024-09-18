"""armenian parser

Revision ID: 83fac9948381
Revises: cfc83ed88342
Create Date: 2024-09-18 20:14:14.579664

"""

# revision identifiers, used by Alembic.
revision = '83fac9948381'
down_revision = 'cfc83ed88342'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute('''
    INSERT INTO public.parser(additional_metadata, created_at, object_id, client_id, name, parameters, method)
    VALUES(null, '2024-09-18 20:14:14.579664', 16, 1, 'Парсер армянского языка Apertium', '[]',
           'apertium_hye');
    ''')

def downgrade():
    op.execute('''
    DELETE FROM parser WHERE method = 'apertium_hye';
    ''')
