"""karelian parser

Revision ID: f3a89eb0becc
Revises: f3a8a6cb9ef4
Create Date: 2025-06-30 15:40:52.929440

"""

# revision identifiers, used by Alembic.
revision = 'f3a89eb0becc'
down_revision = 'f3a8a6cb9ef4'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute('''
    INSERT INTO public.parser(additional_metadata, created_at, object_id, client_id, name, parameters, method)
    VALUES(null, '2025-06-30 20:14:14.579664', 18, 1, 'Парсер карельского языка Apertium', '[]',
           'apertium_krl');
    ''')

def downgrade():
    op.execute('''
    DELETE FROM parser WHERE method = 'apertium_krl';
    ''')
