"""ancient_kalmyk_parser

Revision ID: 707b6ebc663f
Revises: 0fc45203d6ab
Create Date: 2024-05-14 21:50:12.512521

"""

# revision identifiers, used by Alembic.
revision = '707b6ebc663f'
down_revision = '0fc45203d6ab'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute('''
    INSERT INTO public.parser(additional_metadata, created_at, object_id, client_id, name, parameters, method)
    VALUES(null, '2024-05-14 21:50:12.512521', 13, 1, 'Парсер старокалмыцкой письменности (hfst)', '[]',
           'hfst_ancient_kalmyk');
    ''')

def downgrade():
    op.execute('''
    DELETE FROM parser WHERE method = 'hfst_ancient_kalmyk';
    ''')
